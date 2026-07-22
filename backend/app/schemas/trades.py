from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel


class TradesSummaryResponse(BaseModel):
    total_positions: int
    total_orders: int
    total_open_quantity: Decimal
    total_unrealized_pnl: Decimal
    total_realized_pnl: Decimal
    last_synced_at: datetime | None


class ActiveTradePositionResponse(BaseModel):
    id: str
    symbol: str
    direction: str
    quantity: Decimal
    entry_price: Decimal
    current_price: Decimal
    stop_loss: Decimal | None
    take_profit: Decimal | None
    pnl: Decimal
    opened_at: datetime
    status: str


class ActiveTradeOrderResponse(BaseModel):
    id: str
    symbol: str
    direction: str
    type: str
    price: Decimal | None
    quantity: Decimal
    filled_quantity: Decimal
    fee: Decimal
    created_at: datetime
    status: str
    mode: str


class ActiveTradesResponse(BaseModel):
    summary: TradesSummaryResponse
    positions: list[ActiveTradePositionResponse]
    orders: list[ActiveTradeOrderResponse]


class TradeJournalEntryResponse(BaseModel):
    entry_id: str
    entry_type: str
    title: str
    body: str
    entry_at: datetime
    metadata_json: dict[str, Any]


class TradeJournalItemResponse(BaseModel):
    id: str
    symbol: str | None
    strategy: str
    direction: str
    entry_price: Decimal
    exit_price: Decimal
    stop_loss: Decimal | None
    take_profit: Decimal | None
    risk_reward: str
    pnl: Decimal
    result: str
    opened_at: datetime | None
    closed_at: datetime | None
    duration_minutes: int | None
    signal_grade: str | None
    setup_id: str | None
    exit_reason: str | None
    mode: str
    journal_entries: list[TradeJournalEntryResponse]


class TradeJournalSummaryResponse(BaseModel):
    total_trades: int
    wins: int
    losses: int
    win_rate: Decimal
    net_pnl: Decimal
    average_pnl: Decimal


class TradeJournalResponse(BaseModel):
    summary: TradeJournalSummaryResponse
    trades: list[TradeJournalItemResponse]


class TelemetryEventResponse(BaseModel):
    event_id: str
    level: str
    source: str
    message: str
    event_at: datetime
    metadata_json: dict[str, Any]


class TelemetryFeedResponse(BaseModel):
    summary: TradesSummaryResponse
    recent_system_events: list[TelemetryEventResponse]
    recent_trade_notes: list[TradeJournalEntryResponse]
    recent_closed_trades: list[TradeJournalItemResponse]
    active_positions: list[ActiveTradePositionResponse]
    pending_orders: list[ActiveTradeOrderResponse]
