"""market regime snapshots

Revision ID: 202607210004
Revises: 202607210003
Create Date: 2026-07-21 00:00:04
"""
from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "202607210004"
down_revision = "202607210003"
branch_labels = None
depends_on = None

json_type = postgresql.JSONB(astext_type=sa.Text()).with_variant(sa.JSON(), "sqlite")


def upgrade() -> None:
    op.create_table(
        "market_regime_snapshots",
        sa.Column("symbol", sa.String(length=30), nullable=False),
        sa.Column("evaluated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("regime", sa.String(length=40), nullable=False),
        sa.Column("entry_permission", sa.String(length=40), nullable=False),
        sa.Column("confidence_score", sa.Numeric(10, 4), nullable=False),
        sa.Column("trend_direction", sa.String(length=20), nullable=False),
        sa.Column("trend_strength", sa.Numeric(20, 8), nullable=False),
        sa.Column("volatility_value", sa.Numeric(20, 8), nullable=False),
        sa.Column("spread_bps", sa.Numeric(20, 8), nullable=True),
        sa.Column("data_fresh", sa.Boolean(), nullable=False),
        sa.Column("btc_regime", sa.String(length=40), nullable=False),
        sa.Column("market_wide_block", sa.Boolean(), nullable=False),
        sa.Column("reasons", json_type, nullable=False),
        sa.Column("safety_conditions", json_type, nullable=False),
        sa.Column("indicator_snapshot", json_type, nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "regime IN ('TRENDING_BULLISH', 'TRENDING_BEARISH', 'RANGING', "
            "'HIGH_VOLATILITY', 'ABNORMAL_MARKET', 'NO_TRADE', 'INSUFFICIENT_DATA')",
            name="ck_regime_snapshots_regime",
        ),
        sa.CheckConstraint(
            "entry_permission IN ('ALLOW_LONG', 'ALLOW_SHORT', 'ALLOW_BOTH', "
            "'BLOCK_NEW_ENTRIES')",
            name="ck_regime_snapshots_entry_permission",
        ),
        sa.CheckConstraint(
            "trend_direction IN ('bullish', 'bearish', 'flat')",
            name="ck_regime_snapshots_trend_direction",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("symbol", name="uq_regime_snapshots_symbol"),
    )
    op.create_index(
        "ix_regime_snapshots_symbol_evaluated_at",
        "market_regime_snapshots",
        ["symbol", "evaluated_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_regime_snapshots_symbol_evaluated_at",
        table_name="market_regime_snapshots",
    )
    op.drop_table("market_regime_snapshots")
