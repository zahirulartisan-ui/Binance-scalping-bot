from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import CheckConstraint, Index, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base
from app.models.enums import CandleTimeframe, MarketDataCycleStatus
from app.models.mixins import TimestampMixin, UTCDateTime, UuidPrimaryKeyMixin, utc_now
from app.models.trading import enum_values, json_type


class ExchangeSymbol(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "exchange_symbols"
    __table_args__ = (
        CheckConstraint("quote_asset = 'USDT'", name="ck_exchange_symbols_quote_usdt"),
        UniqueConstraint("symbol", name="uq_exchange_symbols_symbol"),
        Index("ix_exchange_symbols_status_symbol", "trading_status", "symbol"),
    )

    symbol: Mapped[str] = mapped_column(String(30), nullable=False)
    base_asset: Mapped[str] = mapped_column(String(20), nullable=False)
    quote_asset: Mapped[str] = mapped_column(String(20), nullable=False)
    trading_status: Mapped[str] = mapped_column(String(30), nullable=False)
    tick_size: Mapped[Decimal] = mapped_column(Numeric(20, 10), nullable=False)
    step_size: Mapped[Decimal] = mapped_column(Numeric(20, 10), nullable=False)
    minimum_quantity: Mapped[Decimal] = mapped_column(Numeric(20, 10), nullable=False)
    minimum_notional: Mapped[Decimal] = mapped_column(Numeric(20, 10), nullable=False)
    price_precision: Mapped[int] = mapped_column(nullable=False)
    quantity_precision: Mapped[int] = mapped_column(nullable=False)
    refreshed_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now, nullable=False)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(json_type, default=dict, nullable=False)


class OhlcvCandle(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "ohlcv_candles"
    __table_args__ = (
        CheckConstraint(
            f"timeframe IN ({enum_values(CandleTimeframe)})",
            name="ck_candles_timeframe",
        ),
        CheckConstraint("high_price >= low_price", name="ck_candles_high_low"),
        CheckConstraint(
            "open_price > 0 AND high_price > 0 AND low_price > 0 AND close_price > 0",
            name="ck_candles_positive_prices",
        ),
        CheckConstraint(
            "volume >= 0 AND quote_volume >= 0 AND trade_count >= 0",
            name="ck_candles_non_negative_activity",
        ),
        UniqueConstraint(
            "symbol",
            "timeframe",
            "open_time",
            name="uq_candles_symbol_timeframe_open",
        ),
        Index("ix_candles_symbol_timeframe_open_time", "symbol", "timeframe", "open_time"),
    )

    symbol: Mapped[str] = mapped_column(String(30), nullable=False)
    timeframe: Mapped[CandleTimeframe] = mapped_column(String(5), nullable=False)
    open_time: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    close_time: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    open_price: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False)
    high_price: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False)
    low_price: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False)
    close_price: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False)
    volume: Mapped[Decimal] = mapped_column(Numeric(28, 8), nullable=False)
    quote_volume: Mapped[Decimal] = mapped_column(Numeric(28, 8), nullable=False)
    trade_count: Mapped[int] = mapped_column(nullable=False)


class MarketSnapshot(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "market_snapshots"
    __table_args__ = (
        CheckConstraint(
            "last_price > 0 AND bid_price > 0 AND ask_price > 0",
            name="ck_snapshots_positive_prices",
        ),
        CheckConstraint(
            "bid_quantity > 0 AND ask_quantity > 0",
            name="ck_snapshots_positive_quantities",
        ),
        CheckConstraint("ask_price >= bid_price", name="ck_snapshots_not_crossed"),
        UniqueConstraint("symbol", "snapshot_at", name="uq_snapshots_symbol_snapshot_at"),
        Index("ix_snapshots_symbol_snapshot_at", "symbol", "snapshot_at"),
    )

    symbol: Mapped[str] = mapped_column(String(30), nullable=False)
    last_price: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False)
    bid_price: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False)
    ask_price: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False)
    bid_quantity: Mapped[Decimal] = mapped_column(Numeric(28, 8), nullable=False)
    ask_quantity: Mapped[Decimal] = mapped_column(Numeric(28, 8), nullable=False)
    spread_bps: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False)
    snapshot_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)


class MarketDataCycle(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "market_data_cycles"
    __table_args__ = (
        CheckConstraint(
            f"status IN ({enum_values(MarketDataCycleStatus)})",
            name="ck_market_data_cycles_status",
        ),
        Index("ix_market_data_cycles_status_started_at", "status", "started_at"),
    )

    status: Mapped[MarketDataCycleStatus] = mapped_column(String(30), nullable=False)
    started_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now, nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    duration_ms: Mapped[int | None] = mapped_column()
    symbols_requested: Mapped[int] = mapped_column(default=0, nullable=False)
    symbols_succeeded: Mapped[int] = mapped_column(default=0, nullable=False)
    symbols_failed: Mapped[int] = mapped_column(default=0, nullable=False)
    candles_stored: Mapped[int] = mapped_column(default=0, nullable=False)
    snapshots_stored: Mapped[int] = mapped_column(default=0, nullable=False)
    rejection_reasons: Mapped[dict[str, Any]] = mapped_column(
        json_type,
        default=dict,
        nullable=False,
    )
    error_message: Mapped[str | None] = mapped_column(Text)
