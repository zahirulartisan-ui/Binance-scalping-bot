from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel


class MarketDataStatusResponse(BaseModel):
    collection_enabled: bool
    runner_active: bool
    latest_cycle_status: str | None
    latest_cycle_started_at: datetime | None
    latest_cycle_finished_at: datetime | None
    latest_cycle_rejections: dict[str, str]


class SymbolResponse(BaseModel):
    symbol: str
    base_asset: str
    quote_asset: str
    trading_status: str
    tick_size: Decimal
    step_size: Decimal
    minimum_quantity: Decimal
    minimum_notional: Decimal
    price_precision: int
    quantity_precision: int
    refreshed_at: datetime


class CandleResponse(BaseModel):
    symbol: str
    timeframe: str
    open_time: datetime
    close_time: datetime
    open_price: Decimal
    high_price: Decimal
    low_price: Decimal
    close_price: Decimal
    volume: Decimal
    quote_volume: Decimal
    trade_count: int


class SnapshotResponse(BaseModel):
    symbol: str
    last_price: Decimal
    bid_price: Decimal
    ask_price: Decimal
    bid_quantity: Decimal
    ask_quantity: Decimal
    spread_bps: Decimal
    snapshot_at: datetime
