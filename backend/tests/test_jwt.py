"""Tests for JWT access/refresh tokens and revocation."""
import uuid


def _register(client):
    email = f"jwt-{uuid.uuid4().hex[:8]}@example.com"
    r = client.post("/api/auth/register", json={"email": email, "password": "password123"})
    assert r.status_code == 201, r.text
    return email, r.json()


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


def test_register_returns_access_and_refresh(client):
    _, body = _register(client)
    assert body["access_token"] and body["refresh_token"]
    assert body["access_token"] != body["refresh_token"]


def test_refresh_issues_working_access_token(client):
    _, body = _register(client)
    r = client.post("/api/auth/refresh", json={"refresh_token": body["refresh_token"]})
    assert r.status_code == 200, r.text
    new = r.json()
    assert client.get("/api/auth/me", headers=_auth(new["access_token"])).status_code == 200


def test_access_token_rejected_at_refresh(client):
    _, body = _register(client)
    # An access token is not a refresh token.
    r = client.post("/api/auth/refresh", json={"refresh_token": body["access_token"]})
    assert r.status_code == 401


def test_refresh_token_cannot_authorize_requests(client):
    _, body = _register(client)
    # A refresh token used as a Bearer must be rejected.
    assert client.get("/api/auth/me", headers=_auth(body["refresh_token"])).status_code == 401


def test_logout_all_revokes_old_tokens(client):
    _, body = _register(client)
    old = body["access_token"]
    assert client.get("/api/auth/me", headers=_auth(old)).status_code == 200
    r = client.post("/api/auth/logout-all", headers=_auth(old))
    assert r.status_code == 200
    fresh = r.json()
    # Old token is now revoked; the freshly-issued one works.
    assert client.get("/api/auth/me", headers=_auth(old)).status_code == 401
    assert client.get("/api/auth/me", headers=_auth(fresh["access_token"])).status_code == 200


def test_password_change_revokes_and_reissues(client):
    email, body = _register(client)
    old = body["access_token"]
    r = client.patch(
        "/api/auth/password",
        json={"current_password": "password123", "new_password": "newpassword456"},
        headers=_auth(old),
    )
    assert r.status_code == 200, r.text
    fresh = r.json()
    assert fresh["access_token"] and fresh["refresh_token"]
    # Old session revoked; new one works.
    assert client.get("/api/auth/me", headers=_auth(old)).status_code == 401
    assert client.get("/api/auth/me", headers=_auth(fresh["access_token"])).status_code == 200


def test_refresh_rejected_after_revocation(client):
    _, body = _register(client)
    old_refresh = body["refresh_token"]
    client.post("/api/auth/logout-all", headers=_auth(body["access_token"]))
    # The pre-revocation refresh token no longer works.
    assert client.post("/api/auth/refresh", json={"refresh_token": old_refresh}).status_code == 401
