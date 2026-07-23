"""Security helpers: password hashing, JWT tokens, and credential encryption."""
from __future__ import annotations

import base64
import hashlib
from datetime import datetime, timedelta, timezone
from typing import Any

import bcrypt
from cryptography.fernet import Fernet, MultiFernet
from jose import JWTError, jwt

from .config import settings


# --------------------------------------------------------------------------- #
# Passwords
# --------------------------------------------------------------------------- #
# bcrypt operates on at most 72 bytes; truncate defensively so long passphrases
# don't raise (matching bcrypt's own documented behavior).
def _pw_bytes(password: str) -> bytes:
    return password.encode("utf-8")[:72]


def hash_password(password: str) -> str:
    return bcrypt.hashpw(_pw_bytes(password), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(_pw_bytes(plain), hashed.encode("utf-8"))
    except (ValueError, TypeError):
        return False


# --------------------------------------------------------------------------- #
# JWT
# --------------------------------------------------------------------------- #
def create_access_token(subject: str | int, expires_minutes: int | None = None) -> str:
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=expires_minutes or settings.access_token_expire_minutes
    )
    payload: dict[str, Any] = {"sub": str(subject), "exp": expire}
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> str | None:
    """Return the subject (user id) or None if the token is invalid/expired."""
    try:
        payload = jwt.decode(
            token, settings.jwt_secret, algorithms=[settings.jwt_algorithm]
        )
        return payload.get("sub")
    except JWTError:
        return None


# --------------------------------------------------------------------------- #
# Credential encryption (Fernet)
# --------------------------------------------------------------------------- #
def _derived_key() -> str:
    """Stable 32-byte Fernet key derived from the JWT secret (legacy/dev)."""
    digest = hashlib.sha256(settings.jwt_secret.encode()).digest()
    return base64.urlsafe_b64encode(digest).decode()


def _fernet() -> MultiFernet:
    """Encryption engine for stored secrets.

    A ``MultiFernet`` encrypts with the FIRST key and decrypts with ANY key, so:
    - When ``ENCRYPTION_KEY`` is set, it becomes the primary (new writes use it)
      while the legacy JWT-derived key stays as a decrypt fallback — existing
      ciphertext keeps opening, enabling a zero-downtime migration/rotation.
    - When it's unset (dev), only the derived key is used (unchanged behavior).
    """
    keys: list[Fernet] = []
    explicit = settings.encryption_key.strip()
    if explicit:
        keys.append(Fernet(explicit.encode()))
    keys.append(Fernet(_derived_key().encode()))
    return MultiFernet(keys)


def encrypt_secret(plaintext: str) -> str:
    if plaintext is None:
        return ""
    return _fernet().encrypt(plaintext.encode()).decode()


def decrypt_secret(ciphertext: str) -> str:
    if not ciphertext:
        return ""
    return _fernet().decrypt(ciphertext.encode()).decode()
