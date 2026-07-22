"""batch 6 signal grading

Revision ID: 202607220006
Revises: 202607210005
Create Date: 2026-07-22 00:00:06
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "202607220006"
down_revision = "202607210005"
branch_labels = None
depends_on = None

json_type = postgresql.JSONB(astext_type=sa.Text()).with_variant(sa.JSON(), "sqlite")


def upgrade() -> None:
    with op.batch_alter_table("strategy_setups", recreate="always") as batch_op:
        batch_op.add_column(sa.Column("signal_grade", sa.String(length=4), nullable=True))
        batch_op.add_column(sa.Column("signal_score", sa.Integer(), nullable=True))
        batch_op.add_column(
            sa.Column("grade_reasons", json_type, nullable=False, server_default="[]")
        )
        batch_op.add_column(
            sa.Column("grading_factors", json_type, nullable=False, server_default="{}")
        )
        batch_op.create_check_constraint(
            "ck_strategy_setups_signal_grade",
            "signal_grade IS NULL OR signal_grade IN ('A', 'B', 'C')",
        )
        batch_op.create_index(
            "ix_strategy_setups_signal_grade_evaluated",
            ["signal_grade", "evaluated_at"],
            unique=False,
        )

    op.execute("UPDATE strategy_setups SET grade_reasons = '[]' WHERE grade_reasons IS NULL")
    op.execute("UPDATE strategy_setups SET grading_factors = '{}' WHERE grading_factors IS NULL")


def downgrade() -> None:
    with op.batch_alter_table("strategy_setups", recreate="always") as batch_op:
        batch_op.drop_index("ix_strategy_setups_signal_grade_evaluated")
        batch_op.drop_constraint("ck_strategy_setups_signal_grade", type_="check")
        batch_op.drop_column("grading_factors")
        batch_op.drop_column("grade_reasons")
        batch_op.drop_column("signal_score")
        batch_op.drop_column("signal_grade")
