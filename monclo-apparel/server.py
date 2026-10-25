"""Monclo Apparel's Flask entry point."""
import os
from flask import Flask, render_template, request
from store import get_db, close_db, init_db, serialize_product
from checkout import register_order_routes
from support import register_support_routes
from admin import register_admin_routes


def create_app(test_config=None):
    app = Flask(__name__)
    app.config.update(
        SECRET_KEY=os.environ.get("MONCLO_SECRET_KEY", "development-only-change-before-deploy"),
        DATABASE=os.environ.get("MONCLO_DB", os.path.join(app.instance_path, "monclo.db")),
        MAX_CONTENT_LENGTH=5 * 1024 * 1024,
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=os.environ.get("MONCLO_HTTPS") == "1",
    )
    if test_config:
        app.config.update(test_config)
    os.makedirs(os.path.dirname(app.config["DATABASE"]) or ".", exist_ok=True)

    app.teardown_appcontext(close_db)
    with app.app_context():
        init_db()

    @app.get("/api/products")
    def products():
        db = get_db()
        rows = db.execute("SELECT * FROM products WHERE active=1 ORDER BY featured DESC, id ASC").fetchall()
        return {"products": [serialize_product(row) for row in rows]}

    register_order_routes(app)
    register_support_routes(app)
    register_admin_routes(app)

    @app.get("/api/config")
    def public_config():
        return {"contact_email": os.environ.get("MONCLO_CONTACT_EMAIL", ""),
                "instagram_url": os.environ.get("MONCLO_INSTAGRAM_URL", "")}

    @app.get("/")
    def index():
        return render_template("index.html")

    @app.get("/api/health")
    def health():
        return {"status": "ok", "brand": "Monclo Apparel"}

    @app.after_request
    def headers(response):
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["X-Frame-Options"] = "DENY"
        if request.path.startswith("/api/admin"):
            response.headers["Cache-Control"] = "no-store"
        return response

    return app


if __name__ == "__main__":
    create_app().run(debug=os.environ.get("FLASK_DEBUG") == "1", port=int(os.environ.get("PORT", 5000)))
