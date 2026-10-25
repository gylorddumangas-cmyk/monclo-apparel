"""Cash on Delivery ordering with server-side validation, inventory locks and idempotency."""
import json
import re
import secrets
import sqlite3
from flask import request, jsonify
from store import get_db

DELIVERY_CENTS = 12000
PHONE = re.compile(r"^(?:\+63|0)9\d{9}$")
POSTAL = re.compile(r"^\d{4}$")


def error(message, status=400):
    return jsonify(error=message), status


def clean_field(data, key, maximum, minimum=1):
    v = data.get(key, "")
    if not isinstance(v, str): raise ValueError(f"Invalid {key.replace('_', ' ')}.")
    v = " ".join(v.split())
    if not minimum <= len(v) <= maximum:
        raise ValueError(f"{key.replace('_', ' ').capitalize()} must contain {minimum}–{maximum} characters.")
    return v


def get_order(db, key):
    order = db.execute("SELECT * FROM orders WHERE idempotency_key=?", (key,)).fetchone()
    if not order: return None
    lines = db.execute("SELECT name, size, color, quantity, unit_cents FROM order_items WHERE order_id=? ORDER BY id", (order["id"],)).fetchall()
    return {"reference": order["reference"], "customer_name": order["customer_name"], "phone": order["phone"], "address": order["address"], "city": order["city"], "province": order["province"], "postal_code": order["postal_code"], "instructions": order["instructions"], "subtotal_cents": order["subtotal_cents"], "delivery_cents": order["delivery_cents"], "total_cents": order["total_cents"], "payment_method": "COD", "status": order["status"], "items": [dict(x) for x in lines]}


def register_order_routes(app):
    @app.post("/api/orders")
    def create_order():
        data = request.get_json(silent=True)
        if not isinstance(data, dict): return error("Send a JSON order.")
        key = data.get("idempotency_key")
        if not isinstance(key, str) or not re.fullmatch(r"[0-9a-f\-]{32,50}", key):
            return error("Missing or invalid order request ID.")
        if data.get("payment_method") != "COD":
            return error("Cash on Delivery is the only supported payment method.")
        db = get_db()
        try:
            # Acquire a write lock before the stock check so simultaneous orders cannot oversell.
            db.execute("BEGIN IMMEDIATE")
            already_saved = get_order(db, key)
            if already_saved:
                db.commit()
                return jsonify(already_saved)
            info = {k: clean_field(data, k, maxlen, minlen) for k, maxlen, minlen in [
                ("customer_name", 90, 2), ("phone", 22, 10), ("address", 240, 8),
                ("city", 90, 2), ("province", 90, 2), ("postal_code", 4, 0),
                ("instructions", 500, 0),
            ]}
            phone = re.sub(r"[\s-]", "", info["phone"])
            if not PHONE.fullmatch(phone): raise ValueError("Enter a valid Philippine mobile number (09xxxxxxxxx or +639xxxxxxxxx).")
            info["phone"] = phone
            if info["postal_code"] and not POSTAL.fullmatch(info["postal_code"]):
                raise ValueError("Postal code must be exactly four digits.")
            items = data.get("items")
            if not isinstance(items, list) or not 1 <= len(items) <= 30:
                raise ValueError("Your order must include 1 to 30 selected items.")
            prepared, totals_by_product = [], {}
            subtotal = 0
            for item in items:
                if not isinstance(item, dict): raise ValueError("Invalid cart item.")
                pid, size, color, qty = (item.get(x) for x in ("product_id", "size", "color", "quantity"))
                if type(pid) is not int or type(qty) is not int or qty < 1 or qty > 50:
                    raise ValueError("Invalid product ID or quantity.")
                product = db.execute("SELECT * FROM products WHERE id=? AND active=1", (pid,)).fetchone()
                if not product: raise ValueError("A product in your cart is no longer available.")
                if size not in json.loads(product["sizes"]) or color not in json.loads(product["colors"]):
                    raise ValueError(f"Choose a valid size and color for {product['name']}.")
                totals_by_product[pid] = totals_by_product.get(pid, 0) + qty
                if totals_by_product[pid] > product["stock"]:
                    raise ValueError(f"Not enough stock available for {product['name']}.")
                subtotal += product["price_cents"] * qty
                prepared.append((pid, product["name"], size, color, qty, product["price_cents"]))
            for pid, qty in totals_by_product.items():
                db.execute("UPDATE products SET stock=stock-? WHERE id=? AND stock>=?", (qty, pid, qty))
                if db.execute("SELECT changes()").fetchone()[0] != 1:
                    raise ValueError("Stock changed while ordering. Refresh the collection and try again.")
            reference = "MNC-" + secrets.token_hex(5).upper()
            db.execute("INSERT INTO orders (reference,idempotency_key,customer_name,phone,address,city,province,postal_code,instructions,subtotal_cents,delivery_cents,total_cents,payment_method) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)", (reference,key,info["customer_name"],info["phone"],info["address"],info["city"],info["province"],info["postal_code"],info["instructions"],subtotal,DELIVERY_CENTS,subtotal+DELIVERY_CENTS,"COD"))
            order_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]
            for item in prepared:
                db.execute("INSERT INTO order_items (order_id,product_id,name,size,color,quantity,unit_cents) VALUES (?,?,?,?,?,?,?)", (order_id,*item))
            db.commit()
            return jsonify(get_order(db, key)), 201
        except ValueError as exc:
            db.rollback()
            return error(str(exc))
        except sqlite3.DatabaseError:
            db.rollback()
            app.logger.exception("Failed to save COD order")
            return error("Could not save your order. Please try again.", 500)
