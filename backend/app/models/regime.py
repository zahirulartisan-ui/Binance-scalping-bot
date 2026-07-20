from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import CheckConstraint, Index, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base
from app.models.enums import EntryPermission, MarketRegime, TrendDirection
from app.models.mixins import TimestampMixin, UTCDateTime, UuidPrimaryKeyMixin
from app.models.trading import enum_values, json_type


class MarketRegimeSnapshot(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "market_regime_snapshots"
    __table_args__ = (
        CheckConstraint(
            f"regime IN ({enum_values(MarketRegime)})",
            name="ck_regime_snapshots_regime",
        ),
        CheckConstraint(
            f"entry_permission IN ({enum_values(EntryPermission)})",
            name="ck_regime_snapshots_entry_permission",
        ),
        CheckConstraint(
            f"trend_direction IN ({enum_values(TrendDirection)})",
            name="ck_regime_snapshots_trend_direction",
        ),
        UniqueConstraint("symbol", name="uq_regime_snapshots_symbol"),
        Index("ix_regime_snapshots_symbol_evaluated_at", "symbol", "evaluated_at"),
    )

    symbol: Mapped[str] = mapped_column(String(30), nullable=False)
    evaluated_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    regime: Mapped[MarketRegime] = mapped_column(String(40), nullable=False)
    entry_permission: Mapped[EntryPermission] = mapped_column(String(40), nullable=False)
    confidence_score: Mapped[Decimal] = mapped_column(Numeric(10, 4), nullable=False)
    trend_direction: Mapped[TrendDirection] = mapped_column(String(20), nullable=False)
    trend_strength: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False)
    volatility_value: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False)
    spread_bps: Mapped[Decimal | None] = mapped_column(Numeric(20, 8))
    data_fresh: Mapped[bool] = mapped_column(nullable=False)
    btc_regime: Mapped[MarketRegime] = mapped_column(String(40), nullable=False)
    market_wide_block: Mapped[bool] = mapped_column(nullable=False)
    reasons: Mapped[list[str]] = mapped_column(json_type, nullable=False)
    safety_conditions: Mapped[list[str]] = mapped_column(json_type, nullable=False)
    indicator_snapshot: Mapped[dict[str, Any]] = mapped_column(json_type, nullable=False)
