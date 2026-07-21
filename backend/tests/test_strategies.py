"""Tests for the rule-based strategy and the LLM strategy's safe fallback."""
from app.agents.base import StrategyContext
from app.agents.registry import build_strategy
from app.enums import SignalAction, StrategyType
from app.exchanges.base import Candle


def _candles_from_closes(closes: list[float]) -> list[Candle]:
    return [
        Candle(timestamp=i * 3600_000, open=c, high=c, low=c, close=c, volume=1.0)
        for i, c in enumerate(closes)
    ]


def _ctx(closes: list[float], position_qty: float = 0.0) -> StrategyContext:
    candles = _candles_from_closes(closes)
    return StrategyContext(
        symbol="BTC/USD",
        timeframe="1h",
        candles=candles,
        current_price=closes[-1],
        position_qty=position_qty,
        avg_entry_price=closes[0] if position_qty else 0.0,
        cash_quote=10_000.0,
    )


def test_rule_based_holds_without_enough_history():
    strat = build_strategy(StrategyType.RULE_BASED)
    decision = strat.decide(_ctx([100.0] * 10))
    assert decision.action == SignalAction.HOLD


def test_rule_based_uptrend_is_bullish():
    strat = build_strategy(StrategyType.RULE_BASED, {"use_rsi": False})
    closes = [100.0 + i for i in range(80)]  # steady uptrend
    decision = strat.decide(_ctx(closes))
    assert decision.action == SignalAction.BUY
    assert 0.0 <= decision.confidence <= 1.0


def test_rule_based_downtrend_with_position_sells():
    strat = build_strategy(StrategyType.RULE_BASED, {"use_rsi": False})
    closes = [200.0 - i for i in range(80)]  # steady downtrend
    decision = strat.decide(_ctx(closes, position_qty=1.0))
    assert decision.action == SignalAction.SELL


def test_rule_based_bullish_but_in_position_holds():
    strat = build_strategy(StrategyType.RULE_BASED, {"use_rsi": False})
    closes = [100.0 + i for i in range(80)]
    decision = strat.decide(_ctx(closes, position_qty=1.0))
    # Already long -> should not emit a redundant BUY.
    assert decision.action == SignalAction.HOLD


def test_llm_strategy_falls_back_to_hold_without_key(monkeypatch):
    from app.agents import llm_agent

    monkeypatch.setattr(llm_agent.settings, "anthropic_api_key", "")
    strat = build_strategy(StrategyType.LLM)
    closes = [100.0 + i for i in range(80)]
    decision = strat.decide(_ctx(closes))
    assert decision.action == SignalAction.HOLD
    assert "no ANTHROPIC_API_KEY" in decision.rationale.lower() or decision.confidence == 0.0
