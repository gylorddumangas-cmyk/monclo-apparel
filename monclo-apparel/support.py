"""Working support / feedback submission API."""
import re
from flask import request, jsonify
from store import get_db

CATEGORIES = ("General Inquiry", "Product Question", "Order Concern", "Website Feedback", "Suggestion", "Other")
EMAIL = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


def register_support_routes(app):
    @app.post("/api/feedback")
    def send_feedback():
        data = request.get_json(silent=True)
        if not isinstance(data, dict): return jsonify(error="Please submit the support form."), 400
        name, email, category, message = (data.get(k) for k in ("name", "email", "category", "message"))
        if not all(isinstance(x, str) for x in (name, email, category, message)):
            return jsonify(error="All fields are required."), 400
        name, email, message = name.strip(), email.strip().lower(), message.strip()
        if not 2 <= len(name) <= 90: return jsonify(error="Name must be 2–90 characters."), 400
        if len(email) > 254 or not EMAIL.fullmatch(email): return jsonify(error="Enter a valid email address."), 400
        if category not in CATEGORIES: return jsonify(error="Select a valid feedback category."), 400
        if not 10 <= len(message) <= 3000: return jsonify(error="Message must be 10–3000 characters."), 400
        db = get_db()
        cursor = db.execute("INSERT INTO feedback (name,email,category,message) VALUES (?,?,?,?)", (name,email,category,message))
        db.commit()
        return jsonify(saved=True, feedback_id=cursor.lastrowid, message="Your feedback has been saved. Thank you for reaching out!"), 201
