"""strategy setup persistence

Revision ID: 202607210005
Revises: 202607210004
Create Date: 2026-07-21 00:00:05
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "202607210005"
down_revision = "202607210004"
branch_labels = None
depends_on = None

json_type = postgresql.JSONB(astext_type=sa.Text()).with_variant(sa.JSON(), "sqlite")


def upgrade() -> None:
    if op.get_bind().dialect.name == "sqlite":
        with op.batch_alter_table("ohlcv_candles", recreate="always") as batch_op:
            batch_op.drop_constraint("ck_candles_timeframe", type_="check")
            batch_op.create_check_constraint(
                "ck_candles_timeframe",
                "timeframe IN ('1m', '5m', '15m')",
            )
    else:
        op.drop_constraint("ck_candles_timeframe", "ohlcv_candles", type_="check")
        op.create_check_constraint(
            "ck_candles_timeframe",
            "ohlcv_candles",
            "timeframe IN ('1m', '5m', '15m')",
        )

    op.create_table(
        "strategy_setups",
        sa.Column("setup_id", sa.String(length=160), nullable=False),
        sa.Column("symbol", sa.String(length=30), nullable=False),
        sa.Column("strategy_name", sa.String(length=80), nullable=False),
        sa.Column("strategy_version", sa.String(length=80), nullable=False),
        sa.Column("direction", sa.String(length=20), nullable=False),
        sa.Column("setup_state", sa.String(length=40), nullable=False),
        sa.Column("evaluated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("regime", sa.String(length=40), nullable=False),
        sa.Column("entry_zone_low", sa.Numeric(20, 8), nullable=True),
        sa.Column("entry_zone_high", sa.Numeric(20, 8), nullable=True),
        sa.Column("preferred_entry", sa.Numeric(20, 8), nullable=True),
        sa.Column("stop_loss", sa.Numeric(20, 8), nullable=True),
        sa.Column("take_profit", sa.Numeric(20, 8), nullable=True),
        sa.Column("reward_to_risk", sa.Numeric(20, 8), nullable=True),
        sa.Column("pullback_depth", sa.Numeric(20, 8), nullable=True),
        sa.Column("volume_ratio", sa.Numeric(20, 8), nullable=True),
        sa.Column("liquidity_sweep_detected", sa.Boolean(), nullable=False),
        sa.Column("mss_detected", sa.Boolean(), nullable=False),
        sa.Column("eligible_for_signal", sa.Boolean(), nullable=False),
        sa.Column("reasons", json_type, nullable=False),
        sa.Column("failed_conditions", json_type, nullable=False),
        sa.Column("indicator_snapshot", json_type, nullable=False),
        sa.Column("invalidated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("invalidation_reason", sa.Text(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "direction IN ('LONG', 'SHORT', 'NONE')",
            name="ck_strategy_setups_direction",
        ),
        sa.CheckConstraint(
            "setup_state IN ('NO_SETUP', 'FORMING', 'READY', 'INVALIDATED', 'EXPIRED', "
            "'INSUFFICIENT_DATA', 'BLOCKED_BY_REGIME')",
            name="ck_strategy_setups_state",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("setup_id", name="uq_strategy_setups_setup_id"),
    )
    op.create_index(
        "ix_strategy_setups_symbol_state_evaluated",
        "strategy_setups",
        ["symbol", "setup_state", "evaluated_at"],
    )
    op.create_index(
        "ix_strategy_setups_eligible_expires",
        "strategy_setups",
        ["eligible_for_signal", "expires_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_strategy_setups_eligible_expires", table_name="strategy_setups")
    op.drop_index("ix_strategy_setups_symbol_state_evaluated", table_name="strategy_setups")
    op.drop_table("strategy_setups")
    if op.get_bind().dialect.name == "sqlite":
        with op.batch_alter_table("ohlcv_candles", recreate="always") as batch_op:
            batch_op.drop_constraint("ck_candles_timeframe", type_="check")
            batch_op.create_check_constraint(
                "ck_candles_timeframe",
                "timeframe IN ('1m', '5m')",
            )
    else:
        op.drop_constraint("ck_candles_timeframe", "ohlcv_candles", type_="check")
        op.create_check_constraint(
            "ck_candles_timeframe",
            "ohlcv_candles",
            "timeframe IN ('1m', '5m')",
        )
