"""Portfolio-level analytics: equity curve, allocation, and summary stats."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import case, func
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_current_user
from ..enums import OrderSide
from ..models import Agent, EquitySnapshot, Trade, User

router = APIRouter(prefix="/api/portfolio", tags=["portfolio"])

MAX_POINTS = 500


@router.get("/history")
def equity_history(
    days: int | None = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[dict]:
    """Total portfolio equity over time.

    Combines per-agent snapshots into a portfolio series: at each snapshot event
    we update that agent's latest equity and emit the sum across all agents.

    ``days`` optionally windows the series to the last N days. We select only the
    three scalar columns we need (not full ORM rows) to keep memory bounded, and
    seed each agent's carry-in equity from its last snapshot *before* the window
    so the portfolio total stays correct at the left edge.
    """
    agent_ids = [a.id for a in db.query(Agent).filter(Agent.user_id == user.id).all()]
    if not agent_ids:
        return []

    latest: dict[int, float] = {}
    q = db.query(
        EquitySnapshot.agent_id, EquitySnapshot.equity, EquitySnapshot.created_at
    ).filter(EquitySnapshot.agent_id.in_(agent_ids))

    if days and days > 0:
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).replace(tzinfo=None)
        # Carry-in: each agent's most recent equity strictly before the window.
        sub = (
            db.query(
                EquitySnapshot.agent_id.label("aid"),
                func.max(EquitySnapshot.created_at).label("mx"),
            )
            .filter(
                EquitySnapshot.agent_id.in_(agent_ids),
                EquitySnapshot.created_at < cutoff,
            )
            .group_by(EquitySnapshot.agent_id)
            .subquery()
        )
        for aid, eq in (
            db.query(EquitySnapshot.agent_id, EquitySnapshot.equity)
            .join(
                sub,
                (EquitySnapshot.agent_id == sub.c.aid)
                & (EquitySnapshot.created_at == sub.c.mx),
            )
            .all()
        ):
            latest[aid] = eq
        q = q.filter(EquitySnapshot.created_at >= cutoff)

    points: list[dict] = []
    for agent_id, equity, created_at in q.order_by(EquitySnapshot.created_at.asc()).all():
        latest[agent_id] = equity
        points.append({"t": created_at.isoformat(), "equity": round(sum(latest.values()), 2)})
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


def _returns(equities: list[float]) -> list[float]:
    out: list[float] = []
    for prev, cur in zip(equities, equities[1:]):
        if prev > 0:
            out.append((cur - prev) / prev)
    return out


def _stdev(xs: list[float]) -> float:
    n = len(xs)
    if n < 2:
        return 0.0
    mean = sum(xs) / n
    return (sum((x - mean) ** 2 for x in xs) / n) ** 0.5


@router.get("/optimize")
def optimize(
    method: str = "risk_parity",
    total: float | None = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """Suggest how to split capital across the user's agents.

    Advisory only — it never moves funds. Weights are computed from each agent's
    equity-curve history (no heavy deps; a lightweight take on risk-parity /
    mean-variance that stays within our serverless limits):

    - ``equal``        : 1/N across agents.
    - ``risk_parity``  : weight ∝ 1/volatility (lower-vol agents get more).
    - ``sharpe``       : weight ∝ max(mean_return / volatility, 0).
    """
    agents = db.query(Agent).filter(Agent.user_id == user.id).all()
    rows: list[dict] = []
    for a in agents:
        # Only the equity column, and only the most recent MAX_POINTS points —
        # enough for a volatility/return estimate without loading full history.
        recent = (
            db.query(EquitySnapshot.equity)
            .filter(EquitySnapshot.agent_id == a.id)
            .order_by(EquitySnapshot.created_at.desc())
            .limit(MAX_POINTS)
            .all()
        )
        equities = [r[0] for r in reversed(recent)]  # back to oldest-first
        rets = _returns(equities)
        vol = _stdev(rets)
        mean = sum(rets) / len(rets) if rets else 0.0
        cur_equity = equities[-1] if equities else (
            (a.position.cash_quote + a.position.quantity * a.position.avg_entry_price)
            if a.position else a.paper_balance_quote
        )
        rows.append({
            "agent_id": a.id, "name": a.name, "symbol": a.symbol,
            "current_equity": round(cur_equity, 2),
            "vol": vol, "mean": mean,
        })

    if not rows:
        return {"method": method, "total": 0.0, "allocations": [], "note": "No agents yet."}

    # Raw (unnormalized) weights per method.
    eps = 1e-9
    if method == "equal":
        raw = [1.0 for _ in rows]
    elif method == "sharpe":
        raw = [max(r["mean"] / (r["vol"] + eps), 0.0) for r in rows]
        if not any(raw):  # no positive risk-adjusted returns yet → fall back to equal
            raw = [1.0 for _ in rows]
    else:  # risk_parity (inverse-volatility)
        raw = [1.0 / (r["vol"] + eps) for r in rows]
        # Agents without enough history (vol==0) shouldn't dominate; cap to the median.
        finite = [w for w, r in zip(raw, rows) if r["vol"] > 0]
        if finite:
            cap = max(finite)
            raw = [min(w, cap) for w in raw]

    s = sum(raw) or 1.0
    weights = [w / s for w in raw]
    budget = total if total and total > 0 else sum(r["current_equity"] for r in rows)

    allocations = [
        {
            "agent_id": r["agent_id"],
            "name": r["name"],
            "symbol": r["symbol"],
            "current_equity": r["current_equity"],
            "weight": round(w, 4),
            "suggested_quote": round(budget * w, 2),
            "volatility": round(r["vol"], 5),
        }
        for r, w in zip(rows, weights)
    ]
    allocations.sort(key=lambda x: x["weight"], reverse=True)
    return {
        "method": method,
        "total": round(budget, 2),
        "allocations": allocations,
        "note": "Advisory suggestion based on each agent's equity-curve history.",
    }


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
    # Win/loss stats from position-closing sell trades. Aggregated in SQL with
    # conditional sums (portable across Postgres/SQLite) so we never pull the
    # full — and unbounded — trade history into memory.
    agent_ids = [a.id for a in agents]
    wins = losses = 0
    win_sum = loss_sum = 0.0
    if agent_ids:
        row = (
            db.query(
                func.sum(case((Trade.realized_pnl > 0, 1), else_=0)),
                func.sum(case((Trade.realized_pnl > 0, Trade.realized_pnl), else_=0.0)),
                func.sum(case((Trade.realized_pnl < 0, 1), else_=0)),
                func.sum(case((Trade.realized_pnl < 0, Trade.realized_pnl), else_=0.0)),
            )
            .filter(Trade.agent_id.in_(agent_ids), Trade.side == OrderSide.SELL)
            .one()
        )
        wins = int(row[0] or 0)
        win_sum = float(row[1] or 0.0)
        losses = int(row[2] or 0)
        loss_sum = float(row[3] or 0.0)
    closed = wins + losses
    return {
        "agents": len(agents),
        "running": sum(1 for a in agents if str(a.status) == "running"),
        "total_realized_pnl": round(total_realized, 2),
        "deployed": round(deployed, 2),
        "cash": round(cash, 2),
        "equity": round(deployed + cash, 2),
        "profitable_agents": profitable,
        "agents_with_trades": with_pnl,
        # Trade win/loss analytics.
        "closed_trades": closed,
        "wins": wins,
        "losses": losses,
        "win_rate": round(wins / closed, 3) if closed else None,
        "avg_win": round(win_sum / wins, 2) if wins else None,
        "avg_loss": round(loss_sum / losses, 2) if losses else None,
    }
