from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel


class RegimeEvaluationResponse(BaseModel):
    symbol: str
    evaluated_at: datetime
    primary_regime: str
    entry_permission: str
    confidence_score: Decimal
    trend_direction: str
    trend_strength_value: Decimal
    volatility_value: Decimal
    spread_value: Decimal | None
    data_fresh: bool
    btc_regime: str
    market_wide_block: bool
    reasons: list[str]
    safety_conditions: list[str]
    indicator_snapshot: dict[str, Any]
