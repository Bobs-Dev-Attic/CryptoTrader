"""LLM-powered strategy inspired by the TradingAgents multi-analyst framework.

A single Claude call role-plays a small trading desk: it is given a compact
market snapshot (recent prices + computed indicators + current position) and
asked to weigh a technical view, a momentum/risk view, and position context,
then return a structured decision. This keeps the multi-perspective spirit of
TradingAgents while remaining a single, cheap, testable call.

If no ``anthropic_api_key`` is configured (or the SDK/network is unavailable),
the strategy degrades gracefully to HOLD with an explanatory rationale so an
agent never crashes for lack of an LLM.
"""
from __future__ import annotations

import json

from ..config import settings
from ..enums import SignalAction
from . import indicators as ind
from .base import Strategy, StrategyContext, StrategyDecision

SYSTEM_PROMPT = """You are the decision layer of a cryptocurrency trading desk.
You receive a market snapshot and a current position, and you weigh three
perspectives before deciding:
  - Technical analyst: trend, momentum (RSI/MACD), moving averages.
  - Risk manager: volatility, drawdown, and whether a position should be exited.
  - Portfolio manager: final BUY / SELL / HOLD call and sizing confidence.

Respond with STRICT JSON only, no prose, in exactly this shape:
{"action": "buy" | "sell" | "hold", "confidence": <0..1>, "rationale": "<one or two sentences>"}
Only recommend BUY if there is no existing position, and SELL only if a position
is held, unless the user's guidance says otherwise."""


class LLMStrategy(Strategy):
    name = "LLM desk (Claude multi-analyst)"

    def decide(self, ctx: StrategyContext) -> StrategyDecision:
        snapshot = self._build_snapshot(ctx)

        api_key = settings.anthropic_api_key
        if not api_key:
            return StrategyDecision(
                SignalAction.HOLD,
                confidence=0.0,
                rationale="LLM strategy inactive: no ANTHROPIC_API_KEY configured.",
                details=snapshot,
            )

        try:
            decision = self._call_claude(api_key, ctx, snapshot)
        except Exception as exc:  # network / parse / SDK errors -> safe HOLD
            return StrategyDecision(
                SignalAction.HOLD,
                confidence=0.0,
                rationale=f"LLM call failed, holding. ({type(exc).__name__}: {exc})",
                details=snapshot,
            )
        return decision

    # ------------------------------------------------------------------ #
    def _build_snapshot(self, ctx: StrategyContext) -> dict:
        closes = ctx.closes
        m = ind.macd(closes) if len(closes) >= 35 else None
        return {
            "symbol": ctx.symbol,
            "timeframe": ctx.timeframe,
            "current_price": ctx.current_price,
            "rsi_14": ind.rsi(closes, 14),
            "sma_20": ind.sma(closes, 20),
            "sma_50": ind.sma(closes, 50),
            "macd": (
                {"macd": m[0], "signal": m[1], "hist": m[2]} if m else None
            ),
            "recent_closes": [round(c, 4) for c in closes[-10:]],
            "position_qty": ctx.position_qty,
            "avg_entry_price": ctx.avg_entry_price,
            "cash_quote": ctx.cash_quote,
        }

    def _call_claude(
        self, api_key: str, ctx: StrategyContext, snapshot: dict
    ) -> StrategyDecision:
        import anthropic

        client = anthropic.Anthropic(api_key=api_key)
        user_guidance = self.config.get("guidance", "")
        user_msg = (
            f"Market snapshot:\n{json.dumps(snapshot, default=str)}\n\n"
            f"Extra guidance from the operator: {user_guidance or '(none)'}\n\n"
            "Return your JSON decision now."
        )
        resp = client.messages.create(
            model=self.config.get("model", settings.llm_model),
            max_tokens=400,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_msg}],
        )
        text = "".join(
            block.text for block in resp.content if getattr(block, "type", "") == "text"
        ).strip()
        parsed = self._parse_json(text)

        action = SignalAction(parsed.get("action", "hold").lower())
        confidence = float(parsed.get("confidence", 0.5))
        rationale = str(parsed.get("rationale", "")).strip()

        # Guard rails identical to the rule-based strategy.
        if action == SignalAction.BUY and ctx.has_position:
            action, rationale = SignalAction.HOLD, "LLM bullish but already in position."
        elif action == SignalAction.SELL and not ctx.has_position:
            action, rationale = SignalAction.HOLD, "LLM bearish but no position held."

        return StrategyDecision(
            action=action,
            confidence=max(0.0, min(1.0, confidence)),
            rationale=rationale or "LLM decision.",
            details=snapshot,
        )

    @staticmethod
    def _parse_json(text: str) -> dict:
        # Be tolerant of code fences or leading prose.
        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end == -1:
            raise ValueError(f"No JSON object found in LLM response: {text[:200]}")
        return json.loads(text[start : end + 1])
