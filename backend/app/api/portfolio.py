"""Portfolio-level analytics: equity curve, allocation, and summary stats."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_current_user
from ..models import Agent, EquitySnapshot, User

router = APIRouter(prefix="/api/portfolio", tags=["portfolio"])

MAX_POINTS = 500


@router.get("/history")
def equity_history(
    user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> list[dict]:
    """Total portfolio equity over time.

    Combines per-agent snapshots into a portfolio series: at each snapshot event
    we update that agent's latest equity and emit the sum across all agents.
    """
    agent_ids = [a.id for a in db.query(Agent).filter(Agent.user_id == user.id).all()]
    if not agent_ids:
        return []
    snaps = (
        db.query(EquitySnapshot)
        .filter(EquitySnapshot.agent_id.in_(agent_ids))
        .order_by(EquitySnapshot.created_at.asc())
        .all()
    )
    latest: dict[int, float] = {}
    points: list[dict] = []
    for s in snaps:
        latest[s.agent_id] = s.equity
        points.append({"t": s.created_at.isoformat(), "equity": round(sum(latest.values()), 2)})
    # Downsample to keep the payload small while preserving the shape.
    if len(points) > MAX_POINTS:
        step = len(points) / MAX_POINTS
        points = [points[int(i * step)] for i in range(MAX_POINTS)] + [points[-1]]
    return points


@router.get("/allocation")
def allocation(
    user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> list[dict]:
    """Deployed capital per agent (position value at entry) + free cash."""
    agents = db.query(Agent).filter(Agent.user_id == user.id).all()
    slices: list[dict] = []
    cash = 0.0
    for a in agents:
        if not a.position:
            continue
        deployed = a.position.quantity * a.position.avg_entry_price
        cash += a.position.cash_quote
        if deployed > 0:
            slices.append({"label": a.name, "value": round(deployed, 2), "symbol": a.symbol})
    if cash > 0:
        slices.append({"label": "Free cash", "value": round(cash, 2), "symbol": ""})
    return slices


@router.get("/stats")
def stats(
    user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> dict:
    """Headline numbers for the dashboard."""
    agents = db.query(Agent).filter(Agent.user_id == user.id).all()
    total_realized = 0.0
    deployed = 0.0
    cash = 0.0
    profitable = 0
    with_pnl = 0
    for a in agents:
        if not a.position:
            continue
        total_realized += a.position.realized_pnl
        deployed += a.position.quantity * a.position.avg_entry_price
        cash += a.position.cash_quote
        if a.position.realized_pnl != 0:
            with_pnl += 1
            if a.position.realized_pnl > 0:
                profitable += 1
    return {
        "agents": len(agents),
        "running": sum(1 for a in agents if str(a.status) == "running"),
        "total_realized_pnl": round(total_realized, 2),
        "deployed": round(deployed, 2),
        "cash": round(cash, 2),
        "equity": round(deployed + cash, 2),
        "profitable_agents": profitable,
        "agents_with_trades": with_pnl,
    }
