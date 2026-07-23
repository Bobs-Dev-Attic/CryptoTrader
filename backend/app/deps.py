"""Shared FastAPI dependencies (current-user resolution)."""
from __future__ import annotations

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from .database import get_db
from .models import User
from .security import decode_token

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    credentials_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    claims = decode_token(token)
    if claims is None:
        raise credentials_error
    # A refresh token must not authorize normal requests.
    if claims.get("type") == "refresh":
        raise credentials_error
    try:
        user_id = int(claims.get("sub"))
    except (TypeError, ValueError):
        raise credentials_error
    user = db.get(User, user_id)
    if user is None:
        raise credentials_error
    # Revocation: a token whose version is behind the user's current one is dead.
    tv = claims.get("tv")
    if tv is not None and tv != user.token_version:
        raise credentials_error
    return user
