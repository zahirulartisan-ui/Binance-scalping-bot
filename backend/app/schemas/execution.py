from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, Field


class ExecutionStatusResponse(BaseModel):
    execution_enabled: bool
    demo_trading_mode: bool
    emergency_stop: bool
    demo_account_balance: Decimal
    risk_per_trade: Decimal
    daily_loss_limit: Decimal
    daily_loss_limit_amount: Decimal
    maximum_open_trades: int
    open_positions: int
    unsupported_open_positions: int
    realized_pnl_today: Decimal
    executable: bool
    reasons: list[str]


class ExecuteSignalRequest(BaseModel):
    quantity_override: Decimal | None = Field(default=None, gt=0)
    entry_price_override: Decimal | None = Field(default=None, gt=0)
    note: str | None = Field(default=None, max_length=250)


class ClosePositionRequest(BaseModel):
    exit_price: Decimal = Field(gt=0)
    note: str | None = Field(default=None, max_length=250)


class PartialClosePositionRequest(BaseModel):
    exit_price: Decimal = Field(gt=0)
    quantity: Decimal = Field(gt=0)
    note: str | None = Field(default=None, max_length=250)


class MoveStopRequest(BaseModel):
    new_stop_price: Decimal = Field(gt=0)
    note: str | None = Field(default=None, max_length=250)


class MonitorPriceInput(BaseModel):
    symbol: str
    price: Decimal = Field(gt=0)


class MonitorRunRequest(BaseModel):
    prices: list[MonitorPriceInput]
    note: str | None = Field(default=None, max_length=250)


class RiskDecisionResponse(BaseModel):
    risk_decision_id: str
    status: str
    reason_code: str
    risk_per_trade: Decimal
    daily_loss_limit: Decimal
    max_open_trades: int
    created_at: datetime
    metadata_json: dict[str, Any]


class OrderResponse(BaseModel):
    order_id: str
    signal_id: str | None
    position_id: str | None
    client_order_id: str
    exchange_order_id: str | None
    symbol: str
    side: str
    order_type: str
    status: str
    price: Decimal | None
    quantity: Decimal
    filled_quantity: Decimal
    fee: Decimal
    submitted_at: datetime | None
    created_at: datetime
    metadata_json: dict[str, Any]


class PositionResponse(BaseModel):
    position_id: str
    symbol: str
    status: str
    side: str
    quantity: Decimal
    average_entry_price: Decimal
    realized_pnl: Decimal
    unrealized_pnl: Decimal
    opened_at: datetime
    closed_at: datetime | None
    signal_id: str | None
    created_at: datetime
    metadata_json: dict[str, Any]


class PositionEventResponse(BaseModel):
    event_id: str
    position_id: str
    event_type: str
    quantity_delta: Decimal
    price: Decimal | None
    realized_pnl_delta: Decimal
    event_at: datetime
    created_at: datetime
    metadata_json: dict[str, Any]


class SignalExecutionResponse(BaseModel):
    signal_id: str
    reused: bool
    mode: str
    risk_decision: RiskDecisionResponse
    order: OrderResponse
    position: PositionResponse


class PositionManagementResponse(BaseModel):
    action: str
    position: PositionResponse
    order: OrderResponse | None
    events: list[PositionEventResponse]
    details: dict[str, Any]


class MonitorSweepResponse(BaseModel):
    checked_count: int
    action_count: int
    actions: list[PositionManagementResponse]
