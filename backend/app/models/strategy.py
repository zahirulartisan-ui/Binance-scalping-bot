from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import CheckConstraint, Index, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base
from app.models.enums import StrategyDirection, StrategySetupState
from app.models.mixins import TimestampMixin, UTCDateTime, UuidPrimaryKeyMixin
from app.models.trading import enum_values, json_type


class StrategySetup(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "strategy_setups"
    __table_args__ = (
        CheckConstraint(
            f"direction IN ({enum_values(StrategyDirection)})",
            name="ck_strategy_setups_direction",
        ),
        CheckConstraint(
            f"setup_state IN ({enum_values(StrategySetupState)})",
            name="ck_strategy_setups_state",
        ),
        UniqueConstraint("setup_id", name="uq_strategy_setups_setup_id"),
        Index("ix_strategy_setups_symbol_state_evaluated", "symbol", "setup_state", "evaluated_at"),
        Index("ix_strategy_setups_eligible_expires", "eligible_for_signal", "expires_at"),
    )

    setup_id: Mapped[str] = mapped_column(String(160), nullable=False)
    symbol: Mapped[str] = mapped_column(String(30), nullable=False)
    strategy_name: Mapped[str] = mapped_column(String(80), nullable=False)
    strategy_version: Mapped[str] = mapped_column(String(80), nullable=False)
    direction: Mapped[StrategyDirection] = mapped_column(String(20), nullable=False)
    setup_state: Mapped[StrategySetupState] = mapped_column(String(40), nullable=False)
    evaluated_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    regime: Mapped[str] = mapped_column(String(40), nullable=False)
    entry_zone_low: Mapped[Decimal | None] = mapped_column(Numeric(20, 8))
    entry_zone_high: Mapped[Decimal | None] = mapped_column(Numeric(20, 8))
    preferred_entry: Mapped[Decimal | None] = mapped_column(Numeric(20, 8))
    stop_loss: Mapped[Decimal | None] = mapped_column(Numeric(20, 8))
    take_profit: Mapped[Decimal | None] = mapped_column(Numeric(20, 8))
    reward_to_risk: Mapped[Decimal | None] = mapped_column(Numeric(20, 8))
    pullback_depth: Mapped[Decimal | None] = mapped_column(Numeric(20, 8))
    volume_ratio: Mapped[Decimal | None] = mapped_column(Numeric(20, 8))
    liquidity_sweep_detected: Mapped[bool] = mapped_column(default=False, nullable=False)
    mss_detected: Mapped[bool] = mapped_column(default=False, nullable=False)
    eligible_for_signal: Mapped[bool] = mapped_column(default=False, nullable=False)
    reasons: Mapped[list[str]] = mapped_column(json_type, default=list, nullable=False)
    failed_conditions: Mapped[list[str]] = mapped_column(json_type, default=list, nullable=False)
    indicator_snapshot: Mapped[dict[str, Any]] = mapped_column(
        json_type, default=dict, nullable=False
    )
    invalidated_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    invalidation_reason: Mapped[str | None] = mapped_column(Text)
