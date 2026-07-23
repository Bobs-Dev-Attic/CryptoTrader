"""Web Push subscription endpoints (VAPID public key + subscribe/unsubscribe)."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_current_user
from ..models import PushSubscription, User
from ..push import public_key

router = APIRouter(prefix="/api/push", tags=["push"])


class SubscriptionIn(BaseModel):
    endpoint: str
    keys: dict = {}


@router.get("/public-key")
def get_public_key(
    user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> dict:
    """The VAPID application-server key the browser subscribes with."""
    return {"key": public_key(db)}


@router.post("/subscribe", status_code=201)
def subscribe(
    payload: SubscriptionIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """Store (or refresh) a browser push subscription for the current user."""
    existing = (
        db.query(PushSubscription)
        .filter(PushSubscription.user_id == user.id, PushSubscription.endpoint == payload.endpoint)
        .first()
    )
    if existing:
        existing.keys_p256dh = payload.keys.get("p256dh", "")
        existing.keys_auth = payload.keys.get("auth", "")
    else:
        db.add(
            PushSubscription(
                user_id=user.id,
                endpoint=payload.endpoint,
                keys_p256dh=payload.keys.get("p256dh", ""),
                keys_auth=payload.keys.get("auth", ""),
            )
        )
    db.commit()
    return {"ok": True}


@router.post("/unsubscribe")
def unsubscribe(
    payload: SubscriptionIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    db.query(PushSubscription).filter(
        PushSubscription.user_id == user.id, PushSubscription.endpoint == payload.endpoint
    ).delete()
    db.commit()
    return {"ok": True}
