"""Paper-trading (simulated) execution engine.

Pure, side-effect-free ledger math so it is trivial to unit test. The agent
runner is responsible for loading a :class:`Ledger` from the DB, calling the
broker, and persisting the resulting position + trade.
"""
from __future__ import annotations

from dataclasses import dataclass

from .base import OrderResult


@dataclass
class Ledger:
    """Mutable simulated account state for a single agent."""

    cash_quote: float
    quantity: float = 0.0
    avg_entry_price: float = 0.0
    realized_pnl: float = 0.0

    def equity(self, mark_price: float) -> float:
        """Total account value marked to the current price."""
        return self.cash_quote + self.quantity * mark_price

    def unrealized_pnl(self, mark_price: float) -> float:
        return (mark_price - self.avg_entry_price) * self.quantity


class PaperBroker:
    """Executes simulated market orders against a :class:`Ledger`."""

    def __init__(self, fee_rate: float = 0.001) -> None:
        self.fee_rate = fee_rate

    def buy(
        self, ledger: Ledger, symbol: str, price: float, notional_quote: float
    ) -> OrderResult | None:
        """Buy ``notional_quote`` worth of base asset. Returns None if unaffordable."""
        if price <= 0 or notional_quote <= 0:
            return None
        fee = notional_quote * self.fee_rate
        total_cost = notional_quote + fee
        if total_cost > ledger.cash_quote:
            return None  # insufficient simulated cash

        qty = notional_quote / price
        prev_qty = ledger.quantity
        new_qty = prev_qty + qty
        # Volume-weighted average entry price.
        ledger.avg_entry_price = (
            (ledger.avg_entry_price * prev_qty + price * qty) / new_qty
            if new_qty > 0
            else 0.0
        )
        ledger.quantity = new_qty
        ledger.cash_quote -= total_cost

        return OrderResult(
            side="buy",
            symbol=symbol,
            quantity=qty,
            price=price,
            cost=notional_quote,
            fee=fee,
            status="filled",
            note="paper",
        )

    def sell_all(
        self, ledger: Ledger, symbol: str, price: float
    ) -> OrderResult | None:
        """Liquidate the entire position at ``price``. Returns None if flat."""
        qty = ledger.quantity
        if qty <= 0 or price <= 0:
            return None

        proceeds = qty * price
        fee = proceeds * self.fee_rate
        realized = (price - ledger.avg_entry_price) * qty - fee

        ledger.cash_quote += proceeds - fee
        ledger.realized_pnl += realized
        ledger.quantity = 0.0
        ledger.avg_entry_price = 0.0

        return OrderResult(
            side="sell",
            symbol=symbol,
            quantity=qty,
            price=price,
            cost=proceeds,
            fee=fee,
            status="filled",
            note=f"paper; realized_pnl={realized:.2f}",
        )
