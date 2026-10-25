"""Password-gated inventory, order and feedback management."""
import hmac
import io
import json
import os
import secrets
import uuid
from decimal import Decimal, InvalidOperation
from functools import wraps
from urllib.parse import urlsplit
from PIL import Image, UnidentifiedImageError
from flask import current_app, jsonify, request, session
from store import get_db, serialize_product

STATUSES = ("Pending", "Confirmed", "Processing", "Shipped", "Delivered")
CATEGORIES = ("T-Shirts", "Oversized Shirts", "Polo Shirts", "Hoodies", "Other Apparel")


def fail(message, code=400):
    return jsonify(error=message), code


def admin_auth():
    return bool(session.get("monclo_admin"))


def admin_required(csrf=False):
    def decorate(view):
        @wraps(view)
        def checked(*args, **kwargs):
            if not admin_auth(): return fail("Administrator login required.", 401)
            if csrf and not hmac.compare_digest(str(request.headers.get("X-CSRF-Token", "")), str(session.get("monclo_csrf", "missing"))):
                return fail("Security token is missing or expired.", 403)
            return view(*args, **kwargs)
        return checked
    return decorate


def validate_product(data):
    if not isinstance(data, dict): raise ValueError("Invalid product data.")
    name, description, category, image_url = (data.get(x) for x in ("name", "description", "category", "image_url"))
    if not isinstance(name, str) or not 2 <= len(name.strip()) <= 100: raise ValueError("Product name must contain 2–100 characters.")
    if not isinstance(description, str) or not 3 <= len(description.strip()) <= 500: raise ValueError("Description must contain 3–500 characters.")
    if category not in CATEGORIES: raise ValueError("Invalid category.")
    if not isinstance(image_url, str) or len(image_url) > 500: raise ValueError("Enter an image URL.")
    parts = urlsplit(image_url)
    if not (parts.scheme == "https" and parts.netloc) and not image_url.startswith("/static/uploads/"):
        raise ValueError("Use an HTTPS image URL or an image uploaded through the admin panel.")
    try:
        price = Decimal(str(data.get("price_pesos")))
        if not price.is_finite() or price < Decimal("0.01") or price > Decimal("999999.99") or price.as_tuple().exponent < -2:
            raise ValueError("Enter a valid product price with at most two decimals.")
        price_cents = int(price * 100)
    except (InvalidOperation, TypeError):
        raise ValueError("Enter a valid price in pesos.")
    stock = data.get("stock")
    if type(stock) is not int or not 0 <= stock <= 100000: raise ValueError("Stock must be a non-negative whole number.")
    sizes, colors = data.get("sizes"), data.get("colors")
    if not (isinstance(sizes, list) and 1 <= len(sizes) <= 10 and all(isinstance(x, str) and 1 <= len(x.strip()) <= 30 for x in sizes)):
        raise ValueError("Provide 1–10 sizes.")
    if not (isinstance(colors, list) and 1 <= len(colors) <= 15 and all(isinstance(x, str) and 1 <= len(x.strip()) <= 30 for x in colors)):
        raise ValueError("Provide 1–15 colors.")
    if len(set(sizes)) != len(sizes) or len(set(colors)) != len(colors): raise ValueError("Sizes and colors must not repeat.")
    return (name.strip(),category,description.strip(),price_cents,json.dumps(sizes),json.dumps(colors),stock,image_url,int(bool(data.get("featured"))),int(bool(data.get("active", True))))


def register_admin_routes(app):
    @app.get("/api/admin/session")
    def admin_session():
        enabled = bool(os.environ.get("MONCLO_ADMIN_PASSWORD")) and bool(os.environ.get("MONCLO_SECRET_KEY"))
        return jsonify(authenticated=admin_auth() and enabled, enabled=enabled, csrf=session.get("monclo_csrf", "") if admin_auth() and enabled else "")

    @app.post("/api/admin/login")
    def admin_login():
        password = os.environ.get("MONCLO_ADMIN_PASSWORD", "")
        if not password or not os.environ.get("MONCLO_SECRET_KEY"):
            return fail("Admin login is disabled. Configure MONCLO_ADMIN_PASSWORD and MONCLO_SECRET_KEY.", 503)
        data = request.get_json(silent=True) or {}
        provided_user = str(data.get("username", ""))
        provided_pass = str(data.get("password", ""))
        username = os.environ.get("MONCLO_ADMIN_USERNAME", "admin")
        if not (hmac.compare_digest(provided_user, username) and hmac.compare_digest(provided_pass, password)):
            return fail("Incorrect admin credentials.", 401)
        session.clear()
        session["monclo_admin"] = True
        session["monclo_csrf"] = secrets.token_urlsafe(32)
        return jsonify(authenticated=True, csrf=session["monclo_csrf"])

    @app.post("/api/admin/logout")
    @admin_required(csrf=True)
    def admin_logout():
        session.clear()
        return jsonify(logged_out=True)

    @app.get("/api/admin/products")
    @admin_required()
    def admin_products():
        return jsonify(products=[serialize_product(p) for p in get_db().execute("SELECT * FROM products ORDER BY id DESC")])

    @app.post("/api/admin/products")
    @admin_required(csrf=True)
    def add_product():
        try: fields = validate_product(request.get_json(silent=True))
        except ValueError as exc: return fail(str(exc))
        db = get_db()
        cursor = db.execute("INSERT INTO products (name,category,description,price_cents,sizes,colors,stock,image_url,featured,active) VALUES (?,?,?,?,?,?,?,?,?,?)", fields)
        db.commit()
        return jsonify(created=True,id=cursor.lastrowid), 201

    @app.put("/api/admin/products/<int:product_id>")
    @admin_required(csrf=True)
    def edit_product(product_id):
        try: fields = validate_product(request.get_json(silent=True))
        except ValueError as exc: return fail(str(exc))
        db = get_db()
        cursor = db.execute("UPDATE products SET name=?,category=?,description=?,price_cents=?,sizes=?,colors=?,stock=?,image_url=?,featured=?,active=? WHERE id=?", (*fields,product_id))
        if not cursor.rowcount: return fail("Product not found.", 404)
        db.commit()
        return jsonify(updated=True)

    @app.delete("/api/admin/products/<int:product_id>")
    @admin_required(csrf=True)
    def remove_product(product_id):
        # Soft delete preserves historical order records.
        db = get_db()
        cursor = db.execute("UPDATE products SET active=0 WHERE id=?", (product_id,))
        if not cursor.rowcount: return fail("Product not found.", 404)
        db.commit()
        return jsonify(removed=True)

    @app.post("/api/admin/upload")
    @admin_required(csrf=True)
    def upload_image():
        file = request.files.get("image")
        if not file or not file.filename: return fail("Select an image file.")
        if not file.filename.lower().endswith((".jpg", ".jpeg", ".png", ".webp")):
            return fail("Upload JPG, PNG or WEBP images only.")
        try:
            data = file.read(5 * 1024 * 1024 + 1)
            if len(data) > 5 * 1024 * 1024: return fail("Maximum image size is 5 MB.", 413)
            Image.MAX_IMAGE_PIXELS = 20_000_000
            with Image.open(io.BytesIO(data)) as original:
                original.verify()
            with Image.open(io.BytesIO(data)) as original:
                if original.width > 6000 or original.height > 6000:
                    return fail("Image dimensions must be under 6000 × 6000.")
                output = original.convert("RGB")
                output.thumbnail((1200, 1500))
                folder = os.path.join(app.static_folder, "uploads")
                os.makedirs(folder, exist_ok=True)
                filename = uuid.uuid4().hex + ".webp"
                output.save(os.path.join(folder, filename), format="WEBP", quality=82, method=5)
        except (OSError, ValueError, UnidentifiedImageError, Image.DecompressionBombError):
            return fail("This is not a valid, safe image file.")
        return jsonify(image_url="/static/uploads/"+filename), 201

    @app.get("/api/admin/orders")
    @admin_required()
    def admin_orders():
        db = get_db()
        orders = []
        for order in db.execute("SELECT * FROM orders ORDER BY id DESC LIMIT 200"):
            value = dict(order)
            value.pop("idempotency_key", None)
            value["items"] = [dict(x) for x in db.execute("SELECT name,size,color,quantity,unit_cents FROM order_items WHERE order_id=?", (order["id"],))]
            orders.append(value)
        return jsonify(orders=orders)

    @app.patch("/api/admin/orders/<int:order_id>")
    @admin_required(csrf=True)
    def update_status(order_id):
        data = request.get_json(silent=True) or {}
        status = data.get("status")
        if status not in STATUSES: return fail("Invalid order status.")
        db = get_db()
        cursor = db.execute("UPDATE orders SET status=? WHERE id=?", (status,order_id))
        if not cursor.rowcount: return fail("Order not found.", 404)
        db.commit()
        return jsonify(updated=True,status=status)

    @app.get("/api/admin/feedback")
    @admin_required()
    def admin_feedback():
        return jsonify(feedback=[dict(x) for x in get_db().execute("SELECT * FROM feedback ORDER BY id DESC LIMIT 200")])
