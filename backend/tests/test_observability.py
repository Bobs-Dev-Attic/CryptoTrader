"""Tests for structured logging, the audit trail, and Sentry gating."""
import json
import logging

import pytest

from app import observability as obs
from app.database import SessionLocal, init_db
from app.enums import OrderSide, SignalAction, StrategyType, TradeMode
from app.models import Agent, Position, Signal, User


class _Capture(logging.Handler):
    """Collect LogRecords emitted on a given logger (bypasses propagate=False)."""

    def __init__(self):
        super().__init__()
        self.records: list[logging.LogRecord] = []

    def emit(self, record):
        self.records.append(record)


@pytest.fixture
def capture_audit():
    handler = _Capture()
    lg = logging.getLogger("cryptotrader.audit")
    lg.addHandler(handler)
    lg.setLevel(logging.INFO)
    try:
        yield handler
    finally:
        lg.removeHandler(handler)


def test_json_formatter_merges_extra_and_is_valid_json():
    rec = logging.LogRecord("cryptotrader", logging.INFO, __file__, 1, "hello", None, None)
    rec.agent_id = 7
    rec.event = "trade.executed"
    out = obs._JsonFormatter().format(rec)
    parsed = json.loads(out)
    assert parsed["msg"] == "hello"
    assert parsed["level"] == "INFO"
    assert parsed["agent_id"] == 7
    assert parsed["event"] == "trade.executed"


def test_audit_emits_structured_record(capture_audit):
    obs.audit("trade.executed", agent_id=42, side="buy", price=100.5)
    assert len(capture_audit.records) == 1
    rec = capture_audit.records[0]
    assert rec.getMessage() == "trade.executed"
    assert rec.event == "trade.executed" and rec.agent_id == 42 and rec.side == "buy"
    assert rec.audit is True


def test_capture_exception_logs_without_sentry():
    # No DSN configured -> _sentry_enabled False -> just logs, never raises.
    handler = _Capture()
    lg = logging.getLogger("cryptotrader")
    lg.addHandler(handler)
    try:
        obs.capture_exception(ValueError("boom"), where="unit-test", agent_id=5)
    finally:
        lg.removeHandler(handler)
    errs = [r for r in handler.records if r.levelno == logging.ERROR]
    assert errs and errs[0].where == "unit-test" and errs[0].agent_id == 5
    assert errs[0].exc_info is not None  # exception attached for the tracker


def test_init_observability_noop_without_dsn(monkeypatch):
    monkeypatch.setattr(obs.settings, "sentry_dsn", "")
    assert obs.init_observability() is False


def test_init_observability_enables_with_dsn(monkeypatch):
    calls = {}
    import sentry_sdk

    monkeypatch.setattr(obs.settings, "sentry_dsn", "https://public@example.com/1")
    monkeypatch.setattr(sentry_sdk, "init", lambda **kw: calls.update(kw))
    try:
        assert obs.init_observability() is True
        assert calls["dsn"] == "https://public@example.com/1"
        assert calls["send_default_pii"] is False
    finally:
        obs._sentry_enabled = False  # reset global for other tests


@pytest.fixture
def db():
    init_db()
    s = SessionLocal()
    try:
        yield s
    finally:
        s.close()


def test_paper_trade_writes_audit_record(db, capture_audit):
    """An executed paper order emits a `trade.executed` audit event."""
    from app.agents.runner import self_execute

    user = User(email="obs@example.com", hashed_password="x")
    db.add(user)
    db.commit()
    db.refresh(user)
    agent = Agent(
        user_id=user.id, name="obs-agent", exchange="kraken", symbol="BTC/USD",
        strategy_type=StrategyType.RULE_BASED, trade_mode=TradeMode.PAPER,
        order_size_quote=100.0,
    )
    db.add(agent)
    db.commit()
    db.refresh(agent)
    position = Position(agent_id=agent.id, quantity=0.0, avg_entry_price=0.0,
                        cash_quote=1000.0, realized_pnl=0.0)
    signal = Signal(agent_id=agent.id, action=SignalAction.BUY, price=100.0)
    db.add_all([position, signal])
    db.commit()
    db.refresh(signal)

    self_execute(db, agent, position, SignalAction.BUY, 100.0, signal, order_quote=100.0)

    events = [r for r in capture_audit.records if getattr(r, "event", None) == "trade.executed"]
    assert len(events) == 1
    rec = events[0]
    assert rec.agent_id == agent.id
    assert rec.side == OrderSide.BUY.value  # "buy"
    assert rec.trade_mode == TradeMode.PAPER.value  # "paper"
    assert rec.symbol == "BTC/USD" and rec.quantity > 0
