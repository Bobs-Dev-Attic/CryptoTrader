"""Agent CRUD, lifecycle (start/stop), manual run, and detail views."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..agents.registry import available_strategies
from ..agents.runner import run_agent_once
from ..database import get_db
from ..deps import get_current_user
from ..enums import AgentStatus, ExchangeId, TradeMode
from ..exchanges import get_adapter
from ..models import Agent, EquitySnapshot, ExchangeAccount, Signal, Trade, User
from ..schemas import (
    AgentCreate,
    AgentDetail,
    AgentOut,
    AgentUpdate,
    SignalOut,
    TradeOut,
)

router = APIRouter(prefix="/api/agents", tags=["agents"])


def _owned_agent(db: Session, user: User, agent_id: int) -> Agent:
    agent = db.get(Agent, agent_id)
    if not agent or agent.user_id != user.id:
        raise HTTPException(status_code=404, detail="Agent not found")
    return agent


def _validate_live(db: Session, user: User, exchange: ExchangeId, account_id: int | None):
    """Ensure a live agent has a usable, credentialed, live-capable account."""
    if account_id is None:
        raise HTTPException(
            status_code=400,
            detail="Live trading requires a linked exchange account (account_id).",
        )
    acc = db.get(ExchangeAccount, account_id)
    if not acc or acc.user_id != user.id:
        raise HTTPException(status_code=400, detail="Linked account not found.")
    if acc.exchange != exchange:
        raise HTTPException(
            status_code=400,
            detail=f"Account is for {acc.exchange}, not {exchange}.",
        )
    adapter = get_adapter(exchange)
    if not adapter.supports_live:
        raise HTTPException(
            status_code=400,
            detail=f"{exchange.value} does not support live trading in this build.",
        )


@router.get("/strategies")
def list_strategies() -> list[dict]:
    """Public metadata for the client's strategy picker."""
    return available_strategies()


@router.get("", response_model=list[AgentOut])
def list_agents(
    user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> list[Agent]:
    return db.query(Agent).filter(Agent.user_id == user.id).all()


@router.post("", response_model=AgentOut, status_code=201)
def create_agent(
    payload: AgentCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Agent:
    if payload.trade_mode == TradeMode.LIVE:
        _validate_live(db, user, payload.exchange, payload.account_id)

    agent = Agent(
        user_id=user.id,
        account_id=payload.account_id,
        name=payload.name,
        exchange=payload.exchange,
        symbol=payload.symbol,
        timeframe=payload.timeframe,
        strategy_type=payload.strategy_type,
        strategy_config=payload.strategy_config,
        trade_mode=payload.trade_mode,
        order_size_quote=payload.order_size_quote,
        paper_balance_quote=payload.paper_balance_quote,
        interval_seconds=max(payload.interval_seconds, 30),
        status=AgentStatus.STOPPED,
    )
    db.add(agent)
    db.commit()
    db.refresh(agent)
    return agent


@router.get("/{agent_id}", response_model=AgentDetail)
def get_agent(
    agent_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AgentDetail:
    agent = _owned_agent(db, user, agent_id)
    signals = (
        db.query(Signal)
        .filter(Signal.agent_id == agent.id)
        .order_by(Signal.created_at.desc())
        .limit(25)
        .all()
    )
    trades = (
        db.query(Trade)
        .filter(Trade.agent_id == agent.id)
        .order_by(Trade.created_at.desc())
        .limit(25)
        .all()
    )
    detail = AgentDetail.model_validate(agent)
    detail.recent_signals = [SignalOut.model_validate(s) for s in signals]
    detail.recent_trades = [TradeOut.model_validate(t) for t in trades]

    # Mark-to-market equity using the latest signal price if available.
    if agent.position and signals:
        mark = signals[0].price or agent.position.avg_entry_price
        detail.equity = agent.position.cash_quote + agent.position.quantity * mark
        detail.unrealized_pnl = (
            (mark - agent.position.avg_entry_price) * agent.position.quantity
        )
    return detail


@router.patch("/{agent_id}", response_model=AgentOut)
def update_agent(
    agent_id: int,
    payload: AgentUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Agent:
    agent = _owned_agent(db, user, agent_id)
    data = payload.model_dump(exclude_unset=True)

    new_mode = data.get("trade_mode", agent.trade_mode)
    new_account = data.get("account_id", agent.account_id)
    if new_mode == TradeMode.LIVE:
        _validate_live(db, user, agent.exchange, new_account)

    for key, value in data.items():
        if key == "interval_seconds" and value is not None:
            value = max(int(value), 30)
        setattr(agent, key, value)
    db.commit()
    db.refresh(agent)
    return agent


@router.delete("/{agent_id}", status_code=204)
def delete_agent(
    agent_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # No `-> None` return annotation: some FastAPI versions treat it as a
    # NoneType response body and reject it on a 204 (no-body) status.
    agent = _owned_agent(db, user, agent_id)
    db.delete(agent)
    db.commit()


@router.post("/{agent_id}/start", response_model=AgentOut)
def start_agent(
    agent_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Agent:
    agent = _owned_agent(db, user, agent_id)
    if agent.trade_mode == TradeMode.LIVE:
        _validate_live(db, user, agent.exchange, agent.account_id)
    agent.status = AgentStatus.RUNNING
    agent.last_error = ""
    db.commit()
    db.refresh(agent)
    return agent


@router.post("/{agent_id}/stop", response_model=AgentOut)
def stop_agent(
    agent_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Agent:
    agent = _owned_agent(db, user, agent_id)
    agent.status = AgentStatus.STOPPED
    db.commit()
    db.refresh(agent)
    return agent


@router.get("/{agent_id}/equity")
def agent_equity(
    agent_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[dict]:
    """This agent's equity curve (oldest first)."""
    agent = _owned_agent(db, user, agent_id)
    snaps = (
        db.query(EquitySnapshot)
        .filter(EquitySnapshot.agent_id == agent.id)
        .order_by(EquitySnapshot.created_at.asc())
        .all()
    )
    return [{"t": s.created_at.isoformat(), "equity": round(s.equity, 2)} for s in snaps]


@router.post("/{agent_id}/run", response_model=SignalOut)
def run_now(
    agent_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Signal:
    """Evaluate the agent immediately (one tick), regardless of schedule."""
    agent = _owned_agent(db, user, agent_id)
    return run_agent_once(db, agent)
