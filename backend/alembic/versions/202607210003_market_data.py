"""market data integration foundation

Revision ID: 202607210003
Revises: 202607210002
Create Date: 2026-07-21 00:00:03
"""
from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "202607210003"
down_revision = "202607210002"
branch_labels = None
depends_on = None

json_type = postgresql.JSONB(astext_type=sa.Text()).with_variant(sa.JSON(), "sqlite")


def upgrade() -> None:
    op.create_table(
        "exchange_symbols",
        sa.Column("symbol", sa.String(length=30), nullable=False),
        sa.Column("base_asset", sa.String(length=20), nullable=False),
        sa.Column("quote_asset", sa.String(length=20), nullable=False),
        sa.Column("trading_status", sa.String(length=30), nullable=False),
        sa.Column("tick_size", sa.Numeric(20, 10), nullable=False),
        sa.Column("step_size", sa.Numeric(20, 10), nullable=False),
        sa.Column("minimum_quantity", sa.Numeric(20, 10), nullable=False),
        sa.Column("minimum_notional", sa.Numeric(20, 10), nullable=False),
        sa.Column("price_precision", sa.Integer(), nullable=False),
        sa.Column("quantity_precision", sa.Integer(), nullable=False),
        sa.Column("refreshed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("metadata_json", json_type, nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("quote_asset = 'USDT'", name="ck_exchange_symbols_quote_usdt"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("symbol", name="uq_exchange_symbols_symbol"),
    )
    op.create_index(
        "ix_exchange_symbols_status_symbol",
        "exchange_symbols",
        ["trading_status", "symbol"],
    )

    op.create_table(
        "ohlcv_candles",
        sa.Column("symbol", sa.String(length=30), nullable=False),
        sa.Column("timeframe", sa.String(length=5), nullable=False),
        sa.Column("open_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("close_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("open_price", sa.Numeric(20, 8), nullable=False),
        sa.Column("high_price", sa.Numeric(20, 8), nullable=False),
        sa.Column("low_price", sa.Numeric(20, 8), nullable=False),
        sa.Column("close_price", sa.Numeric(20, 8), nullable=False),
        sa.Column("volume", sa.Numeric(28, 8), nullable=False),
        sa.Column("quote_volume", sa.Numeric(28, 8), nullable=False),
        sa.Column("trade_count", sa.Integer(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("timeframe IN ('1m', '5m')", name="ck_candles_timeframe"),
        sa.CheckConstraint("high_price >= low_price", name="ck_candles_high_low"),
        sa.CheckConstraint(
            "open_price > 0 AND high_price > 0 AND low_price > 0 AND close_price > 0",
            name="ck_candles_positive_prices",
        ),
        sa.CheckConstraint(
            "volume >= 0 AND quote_volume >= 0 AND trade_count >= 0",
            name="ck_candles_non_negative_activity",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "symbol",
            "timeframe",
            "open_time",
            name="uq_candles_symbol_timeframe_open",
        ),
    )
    op.create_index(
        "ix_candles_symbol_timeframe_open_time",
        "ohlcv_candles",
        ["symbol", "timeframe", "open_time"],
    )

    op.create_table(
        "market_snapshots",
        sa.Column("symbol", sa.String(length=30), nullable=False),
        sa.Column("last_price", sa.Numeric(20, 8), nullable=False),
        sa.Column("bid_price", sa.Numeric(20, 8), nullable=False),
        sa.Column("ask_price", sa.Numeric(20, 8), nullable=False),
        sa.Column("bid_quantity", sa.Numeric(28, 8), nullable=False),
        sa.Column("ask_quantity", sa.Numeric(28, 8), nullable=False),
        sa.Column("spread_bps", sa.Numeric(20, 8), nullable=False),
        sa.Column("snapshot_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "last_price > 0 AND bid_price > 0 AND ask_price > 0",
            name="ck_snapshots_positive_prices",
        ),
        sa.CheckConstraint(
            "bid_quantity > 0 AND ask_quantity > 0",
            name="ck_snapshots_positive_quantities",
        ),
        sa.CheckConstraint("ask_price >= bid_price", name="ck_snapshots_not_crossed"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("symbol", "snapshot_at", name="uq_snapshots_symbol_snapshot_at"),
    )
    op.create_index(
        "ix_snapshots_symbol_snapshot_at",
        "market_snapshots",
        ["symbol", "snapshot_at"],
    )

    op.create_table(
        "market_data_cycles",
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("symbols_requested", sa.Integer(), nullable=False),
        sa.Column("symbols_succeeded", sa.Integer(), nullable=False),
        sa.Column("symbols_failed", sa.Integer(), nullable=False),
        sa.Column("candles_stored", sa.Integer(), nullable=False),
        sa.Column("snapshots_stored", sa.Integer(), nullable=False),
        sa.Column("rejection_reasons", json_type, nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "status IN ('started', 'completed', 'partial_failure', 'failed', 'skipped')",
            name="ck_market_data_cycles_status",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_market_data_cycles_status_started_at",
        "market_data_cycles",
        ["status", "started_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_market_data_cycles_status_started_at", table_name="market_data_cycles")
    op.drop_table("market_data_cycles")
    op.drop_index("ix_snapshots_symbol_snapshot_at", table_name="market_snapshots")
    op.drop_table("market_snapshots")
    op.drop_index("ix_candles_symbol_timeframe_open_time", table_name="ohlcv_candles")
    op.drop_table("ohlcv_candles")
    op.drop_index("ix_exchange_symbols_status_symbol", table_name="exchange_symbols")
    op.drop_table("exchange_symbols")
