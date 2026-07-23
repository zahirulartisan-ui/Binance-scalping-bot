from __future__ import annotations

from datetime import datetime

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
    tick_size: float
    step_size: float
    minimum_quantity: float
    minimum_notional: float
    price_precision: int
    quantity_precision: int
    refreshed_at: datetime


class CandleResponse(BaseModel):
    symbol: str
    timeframe: str
    open_time: datetime
    close_time: datetime
    open_price: float
    high_price: float
    low_price: float
    close_price: float
    volume: float
    quote_volume: float
    trade_count: int


class SnapshotResponse(BaseModel):
    symbol: str
    last_price: float
    bid_price: float
    ask_price: float
    bid_quantity: float
    ask_quantity: float
    spread_bps: float
    snapshot_at: datetime
