"""Authentication routes: register + login."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_current_user
from ..models import User
from ..ratelimit import enforce as rate_limit
from ..schemas import (
    EmailUpdate,
    PasswordUpdate,
    RefreshRequest,
    Token,
    UserCreate,
    UserOut,
)
from ..security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _issue_tokens(user: User) -> Token:
    """Mint an access + refresh token pair bound to the user's token version."""
    return Token(
        access_token=create_access_token(user.id, user.token_version),
        refresh_token=create_refresh_token(user.id, user.token_version),
        user=UserOut.model_validate(user),
    )


@router.post("/register", response_model=Token, status_code=status.HTTP_201_CREATED)
def register(payload: UserCreate, request: Request, db: Session = Depends(get_db)) -> Token:
    rate_limit(request, db, "register", limit=10, window_seconds=3600)  # 10/hour/IP
    existing = db.query(User).filter(User.email == payload.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")
    user = User(
        email=payload.email,
        hashed_password=hash_password(payload.password),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return _issue_tokens(user)


@router.post("/login", response_model=Token)
def login(
    request: Request,
    form: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
) -> Token:
    rate_limit(request, db, "login", limit=10, window_seconds=60)  # 10/min/IP
    # OAuth2PasswordRequestForm uses "username"; we treat it as the email.
    user = db.query(User).filter(User.email == form.username).first()
    if not user or not verify_password(form.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
        )
    return _issue_tokens(user)


@router.post("/refresh", response_model=Token)
def refresh(payload: RefreshRequest, request: Request, db: Session = Depends(get_db)) -> Token:
    """Exchange a valid refresh token for a fresh access + refresh pair (rotating)."""
    rate_limit(request, db, "refresh", limit=60, window_seconds=60)
    invalid = HTTPException(status_code=401, detail="Invalid or expired refresh token")
    claims = decode_token(payload.refresh_token)
    if not claims or claims.get("type") != "refresh":
        raise invalid
    try:
        user = db.get(User, int(claims.get("sub")))
    except (TypeError, ValueError):
        raise invalid
    if user is None:
        raise invalid
    tv = claims.get("tv")
    if tv is not None and tv != user.token_version:
        raise invalid  # revoked
    return _issue_tokens(user)


@router.post("/logout-all", response_model=Token)
def logout_all(
    user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> Token:
    """Revoke every outstanding token for this user (all other devices/sessions).

    Returns a fresh pair so the *current* session stays signed in.
    """
    user.token_version = (user.token_version or 0) + 1
    db.commit()
    db.refresh(user)
    return _issue_tokens(user)


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)) -> UserOut:
    return UserOut.model_validate(user)


@router.patch("/email", response_model=UserOut)
def update_email(
    payload: EmailUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> UserOut:
    """Change the signed-in user's email (requires the current password)."""
    if not verify_password(payload.current_password, user.hashed_password):
        raise HTTPException(status_code=400, detail="Current password is incorrect")
    taken = (
        db.query(User)
        .filter(User.email == payload.new_email, User.id != user.id)
        .first()
    )
    if taken:
        raise HTTPException(status_code=400, detail="Email already registered")
    user.email = payload.new_email
    db.commit()
    db.refresh(user)
    return UserOut.model_validate(user)


@router.patch("/password", response_model=Token)
def update_password(
    payload: PasswordUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Token:
    """Change the signed-in user's password (requires the current password).

    Bumps the token version so any other outstanding sessions are revoked, and
    returns a fresh token pair so the current session continues.
    """
    if not verify_password(payload.current_password, user.hashed_password):
        raise HTTPException(status_code=400, detail="Current password is incorrect")
    if payload.new_password == payload.current_password:
        raise HTTPException(
            status_code=400, detail="New password must differ from the current one"
        )
    user.hashed_password = hash_password(payload.new_password)
    user.token_version = (user.token_version or 0) + 1
    db.commit()
    db.refresh(user)
    return _issue_tokens(user)
