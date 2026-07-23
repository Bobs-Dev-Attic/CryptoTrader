"""Tests for secret validation and encryption-key rotation safety."""
import base64
import hashlib

from cryptography.fernet import Fernet

from app import security
from app.config import DEFAULT_JWT_SECRET, Settings


def test_security_warnings_flag_defaults():
    s = Settings(jwt_secret=DEFAULT_JWT_SECRET, encryption_key="")
    warnings = s.security_warnings()
    assert any("JWT_SECRET" in w for w in warnings)
    assert any("ENCRYPTION_KEY" in w for w in warnings)


def test_security_warnings_clear_when_configured():
    s = Settings(jwt_secret="a-strong-random-secret", encryption_key=Fernet.generate_key().decode())
    assert s.security_warnings() == []


def test_is_production_only_when_explicit():
    assert Settings(environment="development").is_production is False
    assert Settings(environment="production").is_production is True
    assert Settings(environment="PROD").is_production is True


def test_roundtrip_with_derived_key():
    token = security.encrypt_secret("super-secret-api-key")
    assert token and token != "super-secret-api-key"
    assert security.decrypt_secret(token) == "super-secret-api-key"


def test_rotation_keeps_old_ciphertext_readable(monkeypatch):
    """Data encrypted under the legacy JWT-derived key must still decrypt once an
    explicit ENCRYPTION_KEY is introduced (MultiFernet fallback)."""
    # 1) Encrypt with only the derived key (no explicit key set).
    monkeypatch.setattr(security.settings, "encryption_key", "")
    legacy_ciphertext = security.encrypt_secret("legacy-key")

    # 2) Introduce an explicit primary key.
    monkeypatch.setattr(security.settings, "encryption_key", Fernet.generate_key().decode())

    # Old ciphertext still opens (derived key retained as fallback)...
    assert security.decrypt_secret(legacy_ciphertext) == "legacy-key"
    # ...and new writes use the explicit primary key.
    new_ciphertext = security.encrypt_secret("new-key")
    derived = Fernet(
        base64.urlsafe_b64encode(hashlib.sha256(security.settings.jwt_secret.encode()).digest())
    )
    try:
        derived.decrypt(new_ciphertext.encode())
        assert False, "new ciphertext should NOT be decryptable by the derived key alone"
    except Exception:
        pass
    assert security.decrypt_secret(new_ciphertext) == "new-key"
