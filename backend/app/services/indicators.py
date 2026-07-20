from __future__ import annotations

from decimal import Decimal
from math import isfinite, sqrt


def ema(values: list[Decimal], period: int) -> Decimal | None:
    if len(values) < period:
        return None
    multiplier = Decimal("2") / Decimal(period + 1)
    current = sum(values[:period]) / Decimal(period)
    for value in values[period:]:
        current = (value - current) * multiplier + current
    return current


def atr(
    highs: list[Decimal],
    lows: list[Decimal],
    closes: list[Decimal],
    period: int = 14,
) -> Decimal | None:
    if len(highs) < period + 1 or len(lows) < period + 1 or len(closes) < period + 1:
        return None
    true_ranges: list[Decimal] = []
    for index in range(1, len(closes)):
        high = highs[index]
        low = lows[index]
        previous_close = closes[index - 1]
        true_ranges.append(max(high - low, abs(high - previous_close), abs(low - previous_close)))
    recent = true_ranges[-period:]
    return sum(recent) / Decimal(period)


def realized_volatility_percent(closes: list[Decimal], period: int = 20) -> Decimal | None:
    if len(closes) < period + 1:
        return None
    returns: list[float] = []
    for previous, current in zip(closes[-period - 1 : -1], closes[-period:], strict=True):
        if previous <= 0:
            return None
        returns.append(float((current - previous) / previous))
    mean = sum(returns) / len(returns)
    variance = sum((item - mean) ** 2 for item in returns) / len(returns)
    value = sqrt(variance) * 100
    if not isfinite(value):
        return None
    return Decimal(str(value))


def trend_strength_proxy(closes: list[Decimal], lookback: int = 20) -> Decimal:
    if len(closes) < lookback + 1:
        return Decimal("0")
    start = closes[-lookback - 1]
    end = closes[-1]
    if start <= 0:
        return Decimal("0")
    return abs((end - start) / start) * Decimal("100")
