"""Run with pytest after pip install -r requirements.txt."""
import io
import uuid
import pytest
from PIL import Image
from server import create_app


@pytest.fixture()
def app(tmp_path, monkeypatch):
    monkeypatch.setenv("MONCLO_ADMIN_USERNAME", "admin")
    monkeypatch.setenv("MONCLO_ADMIN_PASSWORD", "very-long-local-admin-test-password")
    monkeypatch.setenv("MONCLO_SECRET_KEY", "long-random-local-test-key-not-for-production")
    app = create_app({"TESTING": True, "DATABASE": str(tmp_path / "test.sqlite")})
    yield app


@pytest.fixture()
def client(app):
    return app.test_client()


def make_order(product_id, quantity=2, key=None):
    return {"idempotency_key": key or str(uuid.uuid4()), "payment_method": "COD", "customer_name": "Maria Santos", "phone": "09171234567", "address": "Unit 20, Main Street", "city": "Cebu City", "province": "Cebu", "postal_code": "6000", "instructions": "Gate at the back", "items": [{"product_id": product_id, "size": "M", "color": "White", "quantity": quantity}]}


def test_home_and_catalog(client):
    assert client.get("/").status_code == 200
    data = client.get("/api/products").json
    assert len(data["products"]) >= 6
    assert all(p["price_cents"] > 0 for p in data["products"])
    assert all(p["image_url"] for p in data["products"])


def test_real_cod_order_and_idempotency(client):
    product_id = 1
    original = next(x for x in client.get("/api/products").json["products"] if x["id"] == product_id)
    payload = make_order(product_id)
    resp = client.post("/api/orders", json=payload)
    assert resp.status_code == 201
    order = resp.json
    assert order["reference"].startswith("MNC-")
    assert order["payment_method"] == "COD"
    assert order["subtotal_cents"] == original["price_cents"] * 2
    assert order["delivery_cents"] == 12000
    assert order["total_cents"] == order["subtotal_cents"] + 12000
    new = next(x for x in client.get("/api/products").json["products"] if x["id"] == product_id)
    assert new["stock"] == original["stock"] - 2
    duplicate = client.post("/api/orders", json=payload)
    assert duplicate.status_code == 200
    assert duplicate.json["reference"] == order["reference"]
    after_retry = next(x for x in client.get("/api/products").json["products"] if x["id"] == product_id)
    assert after_retry["stock"] == new["stock"]


def test_invalid_orders_not_stored(client):
    payload = make_order(1, quantity=9999)
    assert client.post("/api/orders", json=payload).status_code == 400
    payload = make_order(1)
    payload["payment_method"] = "CREDIT_CARD"
    assert client.post("/api/orders", json=payload).status_code == 400
    payload = make_order(1)
    payload["phone"] = "invalid"
    assert client.post("/api/orders", json=payload).status_code == 400
    payload = make_order(1)
    payload["items"][0]["color"] = "Wrong color"
    assert client.post("/api/orders", json=payload).status_code == 400
    payload = make_order(1)
    payload["items"].append({"product_id": 1,"size": "L","color": "Black","quantity": 22})
    assert client.post("/api/orders", json=payload).status_code == 400


def test_support_saves_feedback(client):
    data = {"name": "Customer Example", "email": "contact@example.com", "category": "Order Concern", "message": "I have a question about my delivery address."}
    response = client.post("/api/feedback",json=data)
    assert response.status_code == 201
    assert response.json["saved"] is True
    data["email"] = "invalid"
    assert client.post("/api/feedback",json=data).status_code == 400


def login(client):
    assert client.post("/api/admin/login",json={"username":"admin","password":"very-long-local-admin-test-password"}).status_code == 200
    return client.get("/api/admin/session").json["csrf"]


def test_admin_auth_csrf_and_product_management(client):
    assert client.get("/api/admin/orders").status_code == 401
    assert client.post("/api/admin/login",json={"username":"admin","password":"wrong"}).status_code == 401
    token = login(client)
    assert client.get("/api/admin/orders").status_code == 200
    assert client.post("/api/admin/products",json={"name":"shirt"}).status_code == 403
    payload = {"name":"New Test Shirt","category":"T-Shirts","description":"An example shirt for automated testing.","price_pesos":"899.00","sizes":["S","M"],"colors":["Black"],"stock":6,"image_url":"https://example.com/shirt.jpg","featured":True,"active":True}
    result = client.post("/api/admin/products",json=payload,headers={"X-CSRF-Token":token})
    assert result.status_code == 201
    pid = result.json["id"]
    assert any(x["id"] == pid for x in client.get("/api/products").json["products"])
    result = client.delete(f"/api/admin/products/{pid}",headers={"X-CSRF-Token":token})
    assert result.status_code == 200
    assert not any(x["id"] == pid for x in client.get("/api/products").json["products"])


def test_admin_orders_and_feedback(client):
    client.post("/api/feedback",json={"name":"Ada Lovelace","email":"ada@example.com","category":"Suggestion","message":"Please add more colors and sizes."})
    placed = client.post("/api/orders",json=make_order(1))
    assert placed.status_code == 201
    token = login(client)
    feedback = client.get("/api/admin/feedback").json["feedback"]
    assert feedback[0]["email"] == "ada@example.com"
    orders = client.get("/api/admin/orders").json["orders"]
    assert orders[0]["customer_name"] == "Maria Santos"
    assert "idempotency_key" not in orders[0]
    result = client.patch(f"/api/admin/orders/{orders[0]['id']}",json={"status":"Shipped"},headers={"X-CSRF-Token":token})
    assert result.status_code == 200
    assert client.get("/api/admin/orders").json["orders"][0]["status"] == "Shipped"


def test_image_upload(client):
    token = login(client)
    im = Image.new("RGB", (60,60), "grey")
    raw = io.BytesIO()
    im.save(raw,format="PNG")
    raw.seek(0)
    resp = client.post("/api/admin/upload",data={"image":(raw,"test.png")},headers={"X-CSRF-Token":token},content_type="multipart/form-data")
    assert resp.status_code == 201
    assert resp.json["image_url"].endswith(".webp")
