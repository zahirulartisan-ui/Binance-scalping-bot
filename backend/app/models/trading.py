from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from app.database.base import Base
from app.models.enums import (
    AppSettingValueType,
    JournalEntryType,
    OrderSide,
    OrderStatus,
    OrderType,
    PositionEventType,
    PositionStatus,
    RiskDecisionStatus,
    ScannerDecisionType,
    ScannerRunStatus,
    SignalStatus,
    SystemEventLevel,
)
from app.models.mixins import TimestampMixin, UTCDateTime, UuidPrimaryKeyMixin, utc_now

json_type = JSON().with_variant(JSONB, "postgresql")


def enum_values(enum_type: type[StrEnum]) -> str:
    return ", ".join(f"'{item.value}'" for item in enum_type)


class AppSetting(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "app_settings"
    __table_args__ = (
        CheckConstraint(
            f"value_type IN ({enum_values(AppSettingValueType)})",
            name="ck_app_settings_value_type",
        ),
        UniqueConstraint("key", name="uq_app_settings_key"),
        Index("ix_app_settings_key", "key"),
    )

    key: Mapped[str] = mapped_column(String(100), nullable=False)
    value: Mapped[dict[str, Any]] = mapped_column(json_type, nullable=False)
    value_type: Mapped[AppSettingValueType] = mapped_column(String(20), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)


class ScannerRun(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "scanner_runs"
    __table_args__ = (
        CheckConstraint(
            f"status IN ({enum_values(ScannerRunStatus)})",
            name="ck_scanner_runs_status",
        ),
        Index("ix_scanner_runs_status_started_at", "status", "started_at"),
        UniqueConstraint("idempotency_key", name="uq_scanner_runs_idempotency_key"),
    )

    status: Mapped[ScannerRunStatus] = mapped_column(String(20), nullable=False)
    started_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now, nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    idempotency_key: Mapped[str] = mapped_column(String(120), nullable=False)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(json_type, default=dict, nullable=False)

    decisions: Mapped[list[ScannerDecision]] = relationship(back_populates="scanner_run")


class ScannerDecision(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "scanner_decisions"
    __table_args__ = (
        CheckConstraint(
            f"decision IN ({enum_values(ScannerDecisionType)})",
            name="ck_scanner_decisions_decision",
        ),
        Index("ix_scanner_decisions_symbol_decision", "symbol", "decision"),
        UniqueConstraint("scanner_run_id", "symbol", name="uq_scanner_decisions_run_symbol"),
    )

    scanner_run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("scanner_runs.id"), nullable=False)
    symbol: Mapped[str] = mapped_column(String(30), nullable=False)
    decision: Mapped[ScannerDecisionType] = mapped_column(String(30), nullable=False)
    reason_code: Mapped[str] = mapped_column(String(80), nullable=False)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(json_type, default=dict, nullable=False)

    scanner_run: Mapped[ScannerRun] = relationship(back_populates="decisions")
    signals: Mapped[list[Signal]] = relationship(back_populates="scanner_decision")


class Signal(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "signals"
    __table_args__ = (
        CheckConstraint(f"status IN ({enum_values(SignalStatus)})", name="ck_signals_status"),
        CheckConstraint(f"side IN ({enum_values(OrderSide)})", name="ck_signals_side"),
        Index("ix_signals_symbol_status_created_at", "symbol", "status", "created_at"),
        UniqueConstraint("idempotency_key", name="uq_signals_idempotency_key"),
    )

    scanner_decision_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("scanner_decisions.id")
    )
    symbol: Mapped[str] = mapped_column(String(30), nullable=False)
    status: Mapped[SignalStatus] = mapped_column(String(20), nullable=False)
    side: Mapped[OrderSide] = mapped_column(String(10), nullable=False)
    entry_price: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False)
    stop_loss_price: Mapped[Decimal | None] = mapped_column(Numeric(20, 8))
    take_profit_price: Mapped[Decimal | None] = mapped_column(Numeric(20, 8))
    risk_amount: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False)
    expires_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    idempotency_key: Mapped[str] = mapped_column(String(120), nullable=False)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(json_type, default=dict, nullable=False)

    scanner_decision: Mapped[ScannerDecision | None] = relationship(back_populates="signals")
    risk_decisions: Mapped[list[RiskDecision]] = relationship(back_populates="signal")
    orders: Mapped[list[Order]] = relationship(back_populates="signal")


class RiskDecision(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "risk_decisions"
    __table_args__ = (
        CheckConstraint(
            f"status IN ({enum_values(RiskDecisionStatus)})",
            name="ck_risk_decisions_status",
        ),
        Index("ix_risk_decisions_status_created_at", "status", "created_at"),
        UniqueConstraint("idempotency_key", name="uq_risk_decisions_idempotency_key"),
    )

    signal_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("signals.id"))
    status: Mapped[RiskDecisionStatus] = mapped_column(String(20), nullable=False)
    risk_per_trade: Mapped[Decimal] = mapped_column(Numeric(10, 6), nullable=False)
    daily_loss_limit: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False)
    max_open_trades: Mapped[int] = mapped_column(nullable=False)
    reason_code: Mapped[str] = mapped_column(String(80), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(120), nullable=False)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(json_type, default=dict, nullable=False)

    signal: Mapped[Signal | None] = relationship(back_populates="risk_decisions")


class Order(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "orders"
    __table_args__ = (
        CheckConstraint(f"side IN ({enum_values(OrderSide)})", name="ck_orders_side"),
        CheckConstraint(f"order_type IN ({enum_values(OrderType)})", name="ck_orders_order_type"),
        CheckConstraint(f"status IN ({enum_values(OrderStatus)})", name="ck_orders_status"),
        Index("ix_orders_symbol_status_created_at", "symbol", "status", "created_at"),
        UniqueConstraint("client_order_id", name="uq_orders_client_order_id"),
    )

    signal_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("signals.id"))
    position_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("positions.id"))
    client_order_id: Mapped[str] = mapped_column(String(120), nullable=False)
    exchange_order_id: Mapped[str | None] = mapped_column(String(120))
    symbol: Mapped[str] = mapped_column(String(30), nullable=False)
    side: Mapped[OrderSide] = mapped_column(String(10), nullable=False)
    order_type: Mapped[OrderType] = mapped_column(String(20), nullable=False)
    status: Mapped[OrderStatus] = mapped_column(String(30), nullable=False)
    price: Mapped[Decimal | None] = mapped_column(Numeric(20, 8))
    quantity: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False)
    filled_quantity: Mapped[Decimal] = mapped_column(
        Numeric(20, 8),
        default=Decimal("0"),
        nullable=False,
    )
    fee: Mapped[Decimal] = mapped_column(Numeric(20, 8), default=Decimal("0"), nullable=False)
    submitted_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    metadata_json: Mapped[dict[str, Any]] = mapped_column(json_type, default=dict, nullable=False)

    signal: Mapped[Signal | None] = relationship(back_populates="orders")
    position: Mapped[Position | None] = relationship(back_populates="orders")
    fills: Mapped[list[Fill]] = relationship(back_populates="order")


class Fill(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "fills"
    __table_args__ = (
        Index("ix_fills_order_id_filled_at", "order_id", "filled_at"),
        UniqueConstraint("exchange_trade_id", name="uq_fills_exchange_trade_id"),
    )

    order_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orders.id"), nullable=False)
    exchange_trade_id: Mapped[str] = mapped_column(String(120), nullable=False)
    price: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False)
    fee: Mapped[Decimal] = mapped_column(Numeric(20, 8), default=Decimal("0"), nullable=False)
    fee_asset: Mapped[str | None] = mapped_column(String(20))
    filled_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now, nullable=False)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(json_type, default=dict, nullable=False)

    order: Mapped[Order] = relationship(back_populates="fills")


class Position(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "positions"
    __table_args__ = (
        Index("ix_positions_symbol_status_opened_at", "symbol", "status", "opened_at"),
        CheckConstraint("quantity >= 0", name="ck_positions_quantity_non_negative"),
        CheckConstraint(f"status IN ({enum_values(PositionStatus)})", name="ck_positions_status"),
        CheckConstraint(f"side IN ({enum_values(OrderSide)})", name="ck_positions_side"),
    )

    symbol: Mapped[str] = mapped_column(String(30), nullable=False)
    status: Mapped[PositionStatus] = mapped_column(String(20), nullable=False)
    side: Mapped[OrderSide] = mapped_column(String(10), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False)
    average_entry_price: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False)
    realized_pnl: Mapped[Decimal] = mapped_column(
        Numeric(20, 8),
        default=Decimal("0"),
        nullable=False,
    )
    unrealized_pnl: Mapped[Decimal] = mapped_column(
        Numeric(20, 8),
        default=Decimal("0"),
        nullable=False,
    )
    opened_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now, nullable=False)
    closed_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    metadata_json: Mapped[dict[str, Any]] = mapped_column(json_type, default=dict, nullable=False)

    orders: Mapped[list[Order]] = relationship(back_populates="position")
    events: Mapped[list[PositionEvent]] = relationship(back_populates="position")
    journal_entries: Mapped[list[TradeJournalEntry]] = relationship(back_populates="position")


class PositionEvent(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "position_events"
    __table_args__ = (
        CheckConstraint(
            f"event_type IN ({enum_values(PositionEventType)})",
            name="ck_position_events_event_type",
        ),
        Index("ix_position_events_position_id_event_at", "position_id", "event_at"),
    )

    position_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("positions.id"), nullable=False)
    event_type: Mapped[PositionEventType] = mapped_column(String(30), nullable=False)
    quantity_delta: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False)
    price: Mapped[Decimal | None] = mapped_column(Numeric(20, 8))
    realized_pnl_delta: Mapped[Decimal] = mapped_column(
        Numeric(20, 8),
        default=Decimal("0"),
        nullable=False,
    )
    event_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now, nullable=False)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(json_type, default=dict, nullable=False)

    position: Mapped[Position] = relationship(back_populates="events")


class TradeJournalEntry(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "trade_journal_entries"
    __table_args__ = (
        CheckConstraint(
            f"entry_type IN ({enum_values(JournalEntryType)})",
            name="ck_trade_journal_entries_entry_type",
        ),
        Index("ix_trade_journal_entries_symbol_entry_at", "symbol", "entry_at"),
    )

    position_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("positions.id"))
    symbol: Mapped[str | None] = mapped_column(String(30))
    entry_type: Mapped[JournalEntryType] = mapped_column(String(20), nullable=False)
    title: Mapped[str] = mapped_column(String(160), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    entry_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now, nullable=False)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(json_type, default=dict, nullable=False)

    position: Mapped[Position | None] = relationship(back_populates="journal_entries")


class SystemEvent(UuidPrimaryKeyMixin, Base):
    __tablename__ = "system_events"
    __table_args__ = (
        CheckConstraint(
            f"level IN ({enum_values(SystemEventLevel)})",
            name="ck_system_events_level",
        ),
        Index("ix_system_events_level_event_at", "level", "event_at"),
        UniqueConstraint("idempotency_key", name="uq_system_events_idempotency_key"),
    )

    level: Mapped[SystemEventLevel] = mapped_column(String(20), nullable=False)
    source: Mapped[str] = mapped_column(String(80), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(120), nullable=False)
    event_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now, nullable=False)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(json_type, default=dict, nullable=False)
