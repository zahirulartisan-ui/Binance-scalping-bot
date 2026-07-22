from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel


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
    created_at: datetime
    status: str


class ActiveTradesResponse(BaseModel):
    positions: list[ActiveTradePositionResponse]
    orders: list[ActiveTradeOrderResponse]


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


class TradeJournalResponse(BaseModel):
    trades: list[TradeJournalItemResponse]
