"""Tests for changing the signed-in user's email and password."""
import uuid


def _register(client, password="password123"):
    email = f"user-{uuid.uuid4().hex[:8]}@example.com"
    resp = client.post("/api/auth/register", json={"email": email, "password": password})
    assert resp.status_code == 201, resp.text
    token = resp.json()["access_token"]
    return email, password, {"Authorization": f"Bearer {token}"}


def test_change_email_success(client):
    _, password, headers = _register(client)
    new_email = f"new-{uuid.uuid4().hex[:8]}@example.com"
    resp = client.patch(
        "/api/auth/email",
        json={"new_email": new_email, "current_password": password},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["email"] == new_email
    # The new email can be used to log in.
    login = client.post(
        "/api/auth/login", data={"username": new_email, "password": password}
    )
    assert login.status_code == 200, login.text


def test_change_email_wrong_password(client):
    _, _, headers = _register(client)
    resp = client.patch(
        "/api/auth/email",
        json={"new_email": "x@example.com", "current_password": "wrong-password"},
        headers=headers,
    )
    assert resp.status_code == 400


def test_change_email_duplicate(client):
    other_email, _, _ = _register(client)
    _, password, headers = _register(client)
    resp = client.patch(
        "/api/auth/email",
        json={"new_email": other_email, "current_password": password},
        headers=headers,
    )
    assert resp.status_code == 400


def test_change_password_success(client):
    email, password, headers = _register(client)
    resp = client.patch(
        "/api/auth/password",
        json={"current_password": password, "new_password": "brand-new-pass"},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    # Old password no longer works; new one does.
    old = client.post("/api/auth/login", data={"username": email, "password": password})
    assert old.status_code == 401
    new = client.post(
        "/api/auth/login", data={"username": email, "password": "brand-new-pass"}
    )
    assert new.status_code == 200, new.text


def test_change_password_wrong_current(client):
    _, _, headers = _register(client)
    resp = client.patch(
        "/api/auth/password",
        json={"current_password": "nope", "new_password": "brand-new-pass"},
        headers=headers,
    )
    assert resp.status_code == 400


def test_settings_endpoints_require_auth(client):
    assert client.patch("/api/auth/email", json={}).status_code == 401
    assert client.patch("/api/auth/password", json={}).status_code == 401
