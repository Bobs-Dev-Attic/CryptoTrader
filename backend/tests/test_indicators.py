"""Unit tests for technical indicators."""
from app.agents import indicators as ind


def test_sma_basic():
    assert ind.sma([1, 2, 3, 4, 5], 5) == 3.0
    assert ind.sma([1, 2, 3, 4, 5], 2) == 4.5
    assert ind.sma([1, 2], 5) is None


def test_ema_converges_to_constant():
    # EMA of a constant series is that constant.
    assert ind.ema([10.0] * 30, 10) == 10.0


def test_rsi_all_gains_is_100():
    rising = [float(i) for i in range(1, 40)]
    assert ind.rsi(rising, 14) == 100.0


def test_rsi_all_losses_is_low():
    falling = [float(i) for i in range(40, 1, -1)]
    r = ind.rsi(falling, 14)
    assert r is not None and r < 1.0


def test_rsi_needs_enough_data():
    assert ind.rsi([1, 2, 3], 14) is None


def test_macd_shape():
    values = [float(i % 10) + i * 0.1 for i in range(60)]
    result = ind.macd(values)
    assert result is not None
    macd_line, signal_line, hist = result
    assert abs(hist - (macd_line - signal_line)) < 1e-9
