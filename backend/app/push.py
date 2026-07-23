"""Web Push (VAPID) helpers: key management and sending.

The VAPID keypair is generated once with ``cryptography`` and stored in the DB
(no manual configuration). Sending uses ``pywebpush`` if it's installed; the
import is lazy and everything is defensive so a missing dependency or a failed
push never breaks the caller (e.g. the alert-evaluation tick).
"""
from __future__ import annotations

import base64
import json
import logging

from sqlalchemy.orm import Session

from .models import PushConfig, PushSubscription

logger = logging.getLogger("cryptotrader.push")

# Contact address embedded in the VAPID claim (required by push services).
VAPID_SUBJECT = "mailto:alerts@cryptotrader.app"


def _b64url(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def get_or_create_config(db: Session) -> PushConfig:
    """Return the singleton VAPID config, generating it on first call."""
    cfg = db.query(PushConfig).first()
    if cfg:
        return cfg
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import ec

    priv = ec.generate_private_key(ec.SECP256R1())
    d = priv.private_numbers().private_value.to_bytes(32, "big")
    raw_pub = priv.public_key().public_bytes(
        serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint
    )
    cfg = PushConfig(vapid_private=_b64url(d), vapid_public=_b64url(raw_pub))
    db.add(cfg)
    db.commit()
    db.refresh(cfg)
    return cfg


def public_key(db: Session) -> str:
    """The base64url application-server key browsers subscribe with."""
    return get_or_create_config(db).vapid_public


def send_push(db: Session, user_id: int, payload: dict) -> int:
    """Send ``payload`` to all of a user's push subscriptions. Returns count sent.

    Stale subscriptions (404/410) are pruned. Never raises.
    """
    try:
        from pywebpush import WebPushException, webpush
    except Exception:
        return 0  # dependency not available in this environment

    cfg = get_or_create_config(db)
    subs = db.query(PushSubscription).filter(PushSubscription.user_id == user_id).all()
    if not subs:
        return 0

    sent = 0
    stale: list[PushSubscription] = []
    data = json.dumps(payload)
    for s in subs:
        info = {"endpoint": s.endpoint, "keys": {"p256dh": s.keys_p256dh, "auth": s.keys_auth}}
        try:
            webpush(
                subscription_info=info,
                data=data,
                vapid_private_key=cfg.vapid_private,
                vapid_claims={"sub": VAPID_SUBJECT},
            )
            sent += 1
        except WebPushException as exc:
            resp = getattr(exc, "response", None)
            if resp is not None and getattr(resp, "status_code", None) in (404, 410):
                stale.append(s)
        except Exception:
            logger.debug("push send failed", exc_info=True)

    for s in stale:
        db.delete(s)
    if stale:
        db.commit()
    return sent
