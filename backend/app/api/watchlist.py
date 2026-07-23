"""Volatility watch (alert) management + the evaluation routine used by the tick."""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_current_user
from ..marketscan import ALL_METRICS, symbol_value
from ..models import User, VolatilityWatch
from ..schemas import WatchCreate, WatchOut

router = APIRouter(prefix="/api/watchlist", tags=["watchlist"])


@router.get("", response_model=list[WatchOut])
def list_watches(
    user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> list[VolatilityWatch]:
    return (
        db.query(VolatilityWatch)
        .filter(VolatilityWatch.user_id == user.id)
        .order_by(VolatilityWatch.created_at.desc())
        .all()
    )


@router.post("", response_model=WatchOut, status_code=201)
def create_watch(
    payload: WatchCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> VolatilityWatch:
    metric = payload.metric if payload.metric in ALL_METRICS else "range_24h"
    watch = VolatilityWatch(
        user_id=user.id,
        exchange=payload.exchange,
        symbol=payload.symbol.strip().upper(),
        metric=metric,
        threshold=payload.threshold,
    )
    db.add(watch)
    db.commit()
    db.refresh(watch)
    return watch


@router.delete("/{watch_id}", status_code=204)
def delete_watch(
    watch_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    watch = db.get(VolatilityWatch, watch_id)
    if not watch or watch.user_id != user.id:
        raise HTTPException(status_code=404, detail="Watch not found")
    db.delete(watch)
    db.commit()


def evaluate_watches(db: Session) -> int:
    """Recompute each active watch's metric and update its triggered state.

    Rising-edge: ``last_triggered_at`` advances only when a watch crosses from
    below to at/above its threshold. Ticker-based metrics reuse one batch stats
    call per exchange; candle-based metrics fetch per symbol. Never raises.
    """
    now = datetime.now(timezone.utc)
    watches = db.query(VolatilityWatch).filter(VolatilityWatch.is_active.is_(True)).all()
    if not watches:
        return 0

    # Cache batch stats per exchange so N watches don't trigger N fetches.
    from ..marketscan import _stats  # local import avoids a cycle at module load

    stats_cache: dict[str, dict] = {}
    checked = 0
    for w in watches:
        try:
            if w.exchange not in stats_cache:
                stats_cache[w.exchange] = _stats(w.exchange)
            value = symbol_value(w.exchange, w.symbol, w.metric, stats_cache[w.exchange])
            if value is None:
                continue
            was = w.triggered
            now_triggered = value >= w.threshold
            w.last_value = value
            w.last_checked_at = now
            w.triggered = now_triggered
            if now_triggered and not was:
                w.last_triggered_at = now
            checked += 1
        except Exception:
            continue
    db.commit()
    return checked
