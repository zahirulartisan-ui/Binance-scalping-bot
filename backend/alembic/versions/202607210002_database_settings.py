"""database settings and trading foundation

Revision ID: 202607210002
Revises: 202607210001
Create Date: 2026-07-21 00:00:02
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "202607210002"
down_revision = "202607210001"
branch_labels = None
depends_on = None

json_type = postgresql.JSONB(astext_type=sa.Text()).with_variant(sa.JSON(), "sqlite")


def upgrade() -> None:
    op.create_table(
        "app_settings",
        sa.Column("key", sa.String(length=100), nullable=False),
        sa.Column("value", json_type, nullable=False),
        sa.Column("value_type", sa.String(length=20), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "value_type IN ('boolean', 'integer', 'decimal', 'string', 'json')",
            name="ck_app_settings_value_type",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("key", name="uq_app_settings_key"),
    )
    op.create_index("ix_app_settings_key", "app_settings", ["key"])

    op.create_table(
        "scanner_runs",
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("idempotency_key", sa.String(length=120), nullable=False),
        sa.Column("metadata_json", json_type, nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "status IN ('started', 'completed', 'failed')",
            name="ck_scanner_runs_status",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("idempotency_key", name="uq_scanner_runs_idempotency_key"),
    )
    op.create_index("ix_scanner_runs_status_started_at", "scanner_runs", ["status", "started_at"])

    op.create_table(
        "positions",
        sa.Column("symbol", sa.String(length=30), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("side", sa.String(length=10), nullable=False),
        sa.Column("quantity", sa.Numeric(20, 8), nullable=False),
        sa.Column("average_entry_price", sa.Numeric(20, 8), nullable=False),
        sa.Column("realized_pnl", sa.Numeric(20, 8), nullable=False),
        sa.Column("unrealized_pnl", sa.Numeric(20, 8), nullable=False),
        sa.Column("opened_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("metadata_json", json_type, nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "status IN ('open', 'closing', 'closed')",
            name="ck_positions_status",
        ),
        sa.CheckConstraint("side IN ('buy', 'sell')", name="ck_positions_side"),
        sa.CheckConstraint("quantity >= 0", name="ck_positions_quantity_non_negative"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_positions_symbol_status_opened_at",
        "positions",
        ["symbol", "status", "opened_at"],
    )

    op.create_table(
        "scanner_decisions",
        sa.Column("scanner_run_id", sa.Uuid(), nullable=False),
        sa.Column("symbol", sa.String(length=30), nullable=False),
        sa.Column("decision", sa.String(length=30), nullable=False),
        sa.Column("reason_code", sa.String(length=80), nullable=False),
        sa.Column("metadata_json", json_type, nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "decision IN ('watch', 'ignore', 'signal_candidate')",
            name="ck_scanner_decisions_decision",
        ),
        sa.ForeignKeyConstraint(["scanner_run_id"], ["scanner_runs.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("scanner_run_id", "symbol", name="uq_scanner_decisions_run_symbol"),
    )
    op.create_index(
        "ix_scanner_decisions_symbol_decision",
        "scanner_decisions",
        ["symbol", "decision"],
    )

    op.create_table(
        "position_events",
        sa.Column("position_id", sa.Uuid(), nullable=False),
        sa.Column("event_type", sa.String(length=30), nullable=False),
        sa.Column("quantity_delta", sa.Numeric(20, 8), nullable=False),
        sa.Column("price", sa.Numeric(20, 8), nullable=True),
        sa.Column("realized_pnl_delta", sa.Numeric(20, 8), nullable=False),
        sa.Column("event_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("metadata_json", json_type, nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "event_type IN ('opened', 'increased', 'reduced', 'closed', 'stop_updated')",
            name="ck_position_events_event_type",
        ),
        sa.ForeignKeyConstraint(["position_id"], ["positions.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_position_events_position_id_event_at",
        "position_events",
        ["position_id", "event_at"],
    )

    op.create_table(
        "trade_journal_entries",
        sa.Column("position_id", sa.Uuid(), nullable=True),
        sa.Column("symbol", sa.String(length=30), nullable=True),
        sa.Column("entry_type", sa.String(length=20), nullable=False),
        sa.Column("title", sa.String(length=160), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("entry_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("metadata_json", json_type, nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "entry_type IN ('note', 'review', 'incident')",
            name="ck_trade_journal_entries_entry_type",
        ),
        sa.ForeignKeyConstraint(["position_id"], ["positions.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_trade_journal_entries_symbol_entry_at",
        "trade_journal_entries",
        ["symbol", "entry_at"],
    )

    op.create_table(
        "signals",
        sa.Column("scanner_decision_id", sa.Uuid(), nullable=True),
        sa.Column("symbol", sa.String(length=30), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("side", sa.String(length=10), nullable=False),
        sa.Column("entry_price", sa.Numeric(20, 8), nullable=False),
        sa.Column("stop_loss_price", sa.Numeric(20, 8), nullable=True),
        sa.Column("take_profit_price", sa.Numeric(20, 8), nullable=True),
        sa.Column("risk_amount", sa.Numeric(20, 8), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("idempotency_key", sa.String(length=120), nullable=False),
        sa.Column("metadata_json", json_type, nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "status IN ('new', 'accepted', 'rejected', 'expired')",
            name="ck_signals_status",
        ),
        sa.CheckConstraint("side IN ('buy', 'sell')", name="ck_signals_side"),
        sa.ForeignKeyConstraint(["scanner_decision_id"], ["scanner_decisions.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("idempotency_key", name="uq_signals_idempotency_key"),
    )
    op.create_index(
        "ix_signals_symbol_status_created_at",
        "signals",
        ["symbol", "status", "created_at"],
    )

    op.create_table(
        "orders",
        sa.Column("signal_id", sa.Uuid(), nullable=True),
        sa.Column("position_id", sa.Uuid(), nullable=True),
        sa.Column("client_order_id", sa.String(length=120), nullable=False),
        sa.Column("exchange_order_id", sa.String(length=120), nullable=True),
        sa.Column("symbol", sa.String(length=30), nullable=False),
        sa.Column("side", sa.String(length=10), nullable=False),
        sa.Column("order_type", sa.String(length=20), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("price", sa.Numeric(20, 8), nullable=True),
        sa.Column("quantity", sa.Numeric(20, 8), nullable=False),
        sa.Column("filled_quantity", sa.Numeric(20, 8), nullable=False),
        sa.Column("fee", sa.Numeric(20, 8), nullable=False),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("metadata_json", json_type, nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("side IN ('buy', 'sell')", name="ck_orders_side"),
        sa.CheckConstraint(
            "order_type IN ('market', 'limit', 'stop_limit')",
            name="ck_orders_order_type",
        ),
        sa.CheckConstraint(
            "status IN ("
            "'created', 'submitted', 'acknowledged', 'partially_filled', "
            "'filled', 'canceled', 'rejected', 'failed'"
            ")",
            name="ck_orders_status",
        ),
        sa.ForeignKeyConstraint(["position_id"], ["positions.id"]),
        sa.ForeignKeyConstraint(["signal_id"], ["signals.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("client_order_id", name="uq_orders_client_order_id"),
    )
    op.create_index(
        "ix_orders_symbol_status_created_at",
        "orders",
        ["symbol", "status", "created_at"],
    )

    op.create_table(
        "risk_decisions",
        sa.Column("signal_id", sa.Uuid(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("risk_per_trade", sa.Numeric(10, 6), nullable=False),
        sa.Column("daily_loss_limit", sa.Numeric(20, 8), nullable=False),
        sa.Column("max_open_trades", sa.Integer(), nullable=False),
        sa.Column("reason_code", sa.String(length=80), nullable=False),
        sa.Column("idempotency_key", sa.String(length=120), nullable=False),
        sa.Column("metadata_json", json_type, nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "status IN ('approved', 'rejected', 'blocked')",
            name="ck_risk_decisions_status",
        ),
        sa.ForeignKeyConstraint(["signal_id"], ["signals.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("idempotency_key", name="uq_risk_decisions_idempotency_key"),
    )
    op.create_index(
        "ix_risk_decisions_status_created_at",
        "risk_decisions",
        ["status", "created_at"],
    )

    op.create_table(
        "fills",
        sa.Column("order_id", sa.Uuid(), nullable=False),
        sa.Column("exchange_trade_id", sa.String(length=120), nullable=False),
        sa.Column("price", sa.Numeric(20, 8), nullable=False),
        sa.Column("quantity", sa.Numeric(20, 8), nullable=False),
        sa.Column("fee", sa.Numeric(20, 8), nullable=False),
        sa.Column("fee_asset", sa.String(length=20), nullable=True),
        sa.Column("filled_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("metadata_json", json_type, nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["order_id"], ["orders.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("exchange_trade_id", name="uq_fills_exchange_trade_id"),
    )
    op.create_index("ix_fills_order_id_filled_at", "fills", ["order_id", "filled_at"])

    op.create_table(
        "system_events",
        sa.Column("level", sa.String(length=20), nullable=False),
        sa.Column("source", sa.String(length=80), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("idempotency_key", sa.String(length=120), nullable=False),
        sa.Column("event_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("metadata_json", json_type, nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.CheckConstraint(
            "level IN ('info', 'warning', 'error', 'critical')",
            name="ck_system_events_level",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("idempotency_key", name="uq_system_events_idempotency_key"),
    )
    op.create_index("ix_system_events_level_event_at", "system_events", ["level", "event_at"])


def downgrade() -> None:
    op.drop_index("ix_system_events_level_event_at", table_name="system_events")
    op.drop_table("system_events")
    op.drop_index("ix_fills_order_id_filled_at", table_name="fills")
    op.drop_table("fills")
    op.drop_index("ix_risk_decisions_status_created_at", table_name="risk_decisions")
    op.drop_table("risk_decisions")
    op.drop_index("ix_orders_symbol_status_created_at", table_name="orders")
    op.drop_table("orders")
    op.drop_index("ix_signals_symbol_status_created_at", table_name="signals")
    op.drop_table("signals")
    op.drop_index("ix_trade_journal_entries_symbol_entry_at", table_name="trade_journal_entries")
    op.drop_table("trade_journal_entries")
    op.drop_index("ix_position_events_position_id_event_at", table_name="position_events")
    op.drop_table("position_events")
    op.drop_index("ix_scanner_decisions_symbol_decision", table_name="scanner_decisions")
    op.drop_table("scanner_decisions")
    op.drop_index("ix_positions_symbol_status_opened_at", table_name="positions")
    op.drop_table("positions")
    op.drop_index("ix_scanner_runs_status_started_at", table_name="scanner_runs")
    op.drop_table("scanner_runs")
    op.drop_index("ix_app_settings_key", table_name="app_settings")
    op.drop_table("app_settings")
