"""SQLite persistence and the starter product catalog."""
import json
import sqlite3
from flask import current_app, g

PRODUCTS = [
    ("Monclo Essential Tee", "T-Shirts", "A timeless everyday cotton essential.", 69900, ["S", "M", "L", "XL"], ["White", "Black", "Stone"], 22, "photo-1521572163474-6864f9cf17ab", 1),
    ("Foundation Oversized Tee", "Oversized Shirts", "Easy proportions. Confident silhouette.", 84900, ["S", "M", "L", "XL"], ["Charcoal", "Silver", "Cream"], 17, "photo-1503342217505-b0a15ec3261c", 1),
    ("Studio Heavyweight Tee", "T-Shirts", "A substantial feel, refined details.", 99900, ["S", "M", "L", "XL"], ["Black", "Ash"], 15, "photo-1503341504253-dff4815485f1", 1),
    ("Everyday Knit Polo", "Polo Shirts", "A clean take on smart casual comfort.", 119900, ["S", "M", "L", "XL"], ["Navy", "Grey", "Cream"], 12, "photo-1625910513413-5fc45a947ec6", 0),
    ("Monclo Club Hoodie", "Hoodies", "Soft layers for slower days.", 189900, ["S", "M", "L", "XL"], ["Slate", "Black"], 10, "photo-1556821840-3a63f95609a7", 1),
    ("Relaxed Oxford Shirt", "Other Apparel", "Relaxed tailoring meets street-ready style.", 129900, ["S", "M", "L", "XL"], ["Sky", "White"], 11, "photo-1598032895397-b9472444bf93", 0),
    ("Minimal Logo Tee", "T-Shirts", "Understated branding, everyday comfort.", 74900, ["S", "M", "L", "XL"], ["Grey", "White", "Black"], 24, "photo-1562157873-818bc0726f68", 1),
    ("Weekend Zip Hoodie", "Hoodies", "Zip up and head out.", 209900, ["M", "L", "XL"], ["Silver", "Midnight"], 8, "photo-1578681994506-b8f463449011", 0),
    ("Urban Utility Overshirt", "Other Apparel", "The perfect finishing layer.", 159900, ["S", "M", "L", "XL"], ["Slate", "Sand"], 7, "photo-1591047139829-d91aecb6caea", 0),
]

SCHEMA = """
CREATE TABLE IF NOT EXISTS products (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 name TEXT NOT NULL, category TEXT NOT NULL, description TEXT NOT NULL,
 price_cents INTEGER NOT NULL CHECK(price_cents>=0),
 sizes TEXT NOT NULL, colors TEXT NOT NULL,
 stock INTEGER NOT NULL CHECK(stock>=0), image_url TEXT NOT NULL,
 featured INTEGER NOT NULL DEFAULT 0, active INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS orders (
 id INTEGER PRIMARY KEY AUTOINCREMENT, reference TEXT UNIQUE NOT NULL,
 idempotency_key TEXT UNIQUE NOT NULL, customer_name TEXT NOT NULL,
 phone TEXT NOT NULL, address TEXT NOT NULL, city TEXT NOT NULL,
 province TEXT NOT NULL, postal_code TEXT NOT NULL, instructions TEXT NOT NULL,
 subtotal_cents INTEGER NOT NULL, delivery_cents INTEGER NOT NULL,
 total_cents INTEGER NOT NULL, payment_method TEXT NOT NULL DEFAULT 'COD',
 status TEXT NOT NULL DEFAULT 'Pending', created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS order_items (
 id INTEGER PRIMARY KEY AUTOINCREMENT, order_id INTEGER NOT NULL REFERENCES orders(id),
 product_id INTEGER, name TEXT NOT NULL, size TEXT NOT NULL, color TEXT NOT NULL,
 quantity INTEGER NOT NULL, unit_cents INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS feedback (
 id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL,
 email TEXT NOT NULL, category TEXT NOT NULL, message TEXT NOT NULL,
 created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
"""


def get_db():
    if "db" not in g:
        db = sqlite3.connect(current_app.config["DATABASE"], timeout=10)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        db.execute("PRAGMA busy_timeout=10000")
        g.db = db
    return g.db


def close_db(error=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    db = get_db()
    db.executescript(SCHEMA)
    if db.execute("SELECT COUNT(*) FROM products").fetchone()[0] == 0:
        for name, category, description, cents, sizes, colors, stock, photo, featured in PRODUCTS:
            image = f"https://images.unsplash.com/{photo}?w=840&h=1000&fit=crop&auto=format&q=80"
            db.execute("INSERT INTO products (name, category, description, price_cents, sizes, colors, stock, image_url, featured) VALUES (?,?,?,?,?,?,?,?,?)", (name, category, description, cents, json.dumps(sizes), json.dumps(colors), stock, image, featured))
    db.commit()


def serialize_product(row):
    result = dict(row)
    result["sizes"] = json.loads(result["sizes"])
    result["colors"] = json.loads(result["colors"])
    result["featured"] = bool(result["featured"])
    result["active"] = bool(result["active"])
    return result
