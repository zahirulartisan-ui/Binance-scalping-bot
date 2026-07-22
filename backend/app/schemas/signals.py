from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel


class SignalResponse(BaseModel):
    signal_id: str
    scanner_decision_id: str | None
    symbol: str
    status: str
    side: str
    entry_price: Decimal
    stop_loss_price: Decimal | None
    take_profit_price: Decimal | None
    risk_amount: Decimal
    expires_at: datetime | None
    created_at: datetime
    signal_grade: str | None
    signal_score: int | None
    setup_id: str | None
    setup_state: str | None
    strategy_name: str | None
    strategy_version: str | None
    reason_code: str | None
    reasons: list[str]
    metadata_json: dict[str, Any]


class SignalPromotionResponse(BaseModel):
    promoted_count: int
    reused_count: int
    signals: list[SignalResponse]
