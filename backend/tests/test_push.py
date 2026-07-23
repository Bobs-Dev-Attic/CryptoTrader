"""Tests for Web Push key management and subscription endpoints."""
import base64


def test_public_key_is_generated_and_stable(client, auth_headers):
    r1 = client.get("/api/push/public-key", headers=auth_headers)
    assert r1.status_code == 200, r1.text
    key = r1.json()["key"]
    assert key
    # base64url of an uncompressed EC point is 65 bytes -> 87 chars (no padding).
    raw = base64.urlsafe_b64decode(key + "=" * (-len(key) % 4))
    assert len(raw) == 65 and raw[0] == 0x04
    # Stable across calls (singleton config).
    r2 = client.get("/api/push/public-key", headers=auth_headers)
    assert r2.json()["key"] == key


def test_public_key_requires_auth(client):
    assert client.get("/api/push/public-key").status_code == 401


def test_subscribe_and_unsubscribe(client, auth_headers):
    sub = {
        "endpoint": "https://push.example.com/abc123",
        "keys": {"p256dh": "BPk...", "auth": "xyz"},
    }
    assert client.post("/api/push/subscribe", json=sub, headers=auth_headers).status_code == 201
    # Re-subscribing the same endpoint is idempotent (upsert), still 201.
    assert client.post("/api/push/subscribe", json=sub, headers=auth_headers).status_code == 201
    assert (
        client.post("/api/push/unsubscribe", json={"endpoint": sub["endpoint"]}, headers=auth_headers).status_code
        == 200
    )


def test_send_push_no_subscriptions_is_zero(client, auth_headers):
    # With no subscriptions, send_push returns 0 and never raises.
    from app.database import SessionLocal
    from app.models import User
    from app.push import send_push

    db = SessionLocal()
    try:
        uid = db.query(User).first().id
        assert send_push(db, uid, {"title": "t", "body": "b"}) == 0
    finally:
        db.close()
