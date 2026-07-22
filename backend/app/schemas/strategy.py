from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict


class StrategyInfoResponse(BaseModel):
    name: str
    version: str
    enabled: bool
    trading_mode: str
    entry_timeframe: str
    confirmation_timeframe: str
    context_timeframe: str


class StrategyEvaluationResponse(BaseModel):
    setup_id: str
    symbol: str
    strategy_name: str
    strategy_version: str
    evaluated_at: datetime
    setup_created_at: datetime
    setup_expires_at: datetime
    direction: str
    setup_state: str
    eligible_for_signal: bool
    regime: str
    regime_permission: str
    btc_regime: str
    market_wide_block: bool
    one_minute_trend_summary: dict[str, Any]
    five_minute_trend_summary: dict[str, Any]
    fifteen_minute_context_summary: dict[str, Any]
    ema_snapshot: dict[str, Any]
    pullback_detected: bool
    pullback_depth: Decimal | None
    pullback_duration: int | None
    preceding_impulse_size: Decimal | None
    entry_zone_lower: Decimal | None
    entry_zone_upper: Decimal | None
    preferred_entry: Decimal | None
    current_price: Decimal | None
    distance_from_entry: Decimal | None
    entry_zone_position: str
    entry_zone_method: str
    volume_ratio: Decimal | None
    rejection_confirmation: dict[str, Any]
    liquidity_sweep: dict[str, Any]
    market_structure_shift: dict[str, Any]
    stop_loss: Decimal | None
    stop_calculation_method: str | None
    take_profit: Decimal | None
    target_calculation_method: str | None
    risk_amount: Decimal | None
    reward_amount: Decimal | None
    reward_to_risk: Decimal | None
    signal_grade: str | None
    signal_score: int | None
    grade_reasons: list[str]
    grading_factors: dict[str, Any]
    setup_age_seconds: int
    data_freshness: dict[str, Any]
    reasons: list[str]
    failed_conditions: list[str]
    triggered_safety_conditions: list[str]
    indicator_snapshot: dict[str, Any]


class StrategySetupResponse(BaseModel):
    setup_id: str
    symbol: str
    strategy_name: str
    strategy_version: str
    direction: str
    setup_state: str
    evaluated_at: datetime
    expires_at: datetime
    regime: str
    entry_zone_low: Decimal | None
    entry_zone_high: Decimal | None
    preferred_entry: Decimal | None
    stop_loss: Decimal | None
    take_profit: Decimal | None
    reward_to_risk: Decimal | None
    pullback_depth: Decimal | None
    volume_ratio: Decimal | None
    liquidity_sweep_detected: bool
    mss_detected: bool
    eligible_for_signal: bool
    signal_grade: str | None
    signal_score: int | None
    grade_reasons: list[str]
    grading_factors: dict[str, Any]
    reasons: list[str]
    failed_conditions: list[str]
    indicator_snapshot: dict[str, Any]
    invalidated_at: datetime | None
    invalidation_reason: str | None

    model_config = ConfigDict(from_attributes=True)
