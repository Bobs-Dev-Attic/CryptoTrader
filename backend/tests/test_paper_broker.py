"""Unit tests for the paper-trading ledger + broker."""
from app.exchanges.paper import Ledger, PaperBroker


def test_buy_reduces_cash_and_adds_quantity():
    broker = PaperBroker(fee_rate=0.0)
    ledger = Ledger(cash_quote=1000.0)
    result = broker.buy(ledger, "BTC/USD", price=100.0, notional_quote=500.0)

    assert result is not None
    assert result.quantity == 5.0
    assert ledger.quantity == 5.0
    assert ledger.cash_quote == 500.0
    assert ledger.avg_entry_price == 100.0


def test_buy_rejected_when_insufficient_cash():
    broker = PaperBroker(fee_rate=0.001)
    ledger = Ledger(cash_quote=100.0)
    result = broker.buy(ledger, "BTC/USD", price=100.0, notional_quote=500.0)
    assert result is None
    assert ledger.quantity == 0.0
    assert ledger.cash_quote == 100.0


def test_average_entry_price_across_two_buys():
    broker = PaperBroker(fee_rate=0.0)
    ledger = Ledger(cash_quote=10_000.0)
    broker.buy(ledger, "BTC/USD", price=100.0, notional_quote=1000.0)  # 10 units @100
    broker.buy(ledger, "BTC/USD", price=200.0, notional_quote=2000.0)  # 10 units @200
    assert ledger.quantity == 20.0
    assert ledger.avg_entry_price == 150.0


def test_sell_all_realizes_profit():
    broker = PaperBroker(fee_rate=0.0)
    ledger = Ledger(cash_quote=1000.0)
    broker.buy(ledger, "BTC/USD", price=100.0, notional_quote=1000.0)  # 10 @100
    result = broker.sell_all(ledger, "BTC/USD", price=150.0)

    assert result is not None
    assert result.side == "sell"
    assert ledger.quantity == 0.0
    assert ledger.realized_pnl == 500.0  # (150-100)*10
    assert ledger.cash_quote == 1500.0


def test_sell_all_when_flat_returns_none():
    broker = PaperBroker()
    ledger = Ledger(cash_quote=1000.0)
    assert broker.sell_all(ledger, "BTC/USD", price=150.0) is None


def test_fees_are_deducted():
    broker = PaperBroker(fee_rate=0.01)  # 1%
    ledger = Ledger(cash_quote=1010.0)
    result = broker.buy(ledger, "BTC/USD", price=100.0, notional_quote=1000.0)
    assert result is not None
    assert result.fee == 10.0
    assert ledger.cash_quote == 0.0  # 1000 notional + 10 fee
