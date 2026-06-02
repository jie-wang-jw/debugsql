"""add node previews and repair evaluation cases

Revision ID: 20260601_0003
Revises: 20260525_0002
Create Date: 2026-06-01
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260601_0003"
down_revision = "20260525_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("execution_runs", sa.Column("node_previews", sa.JSON(), nullable=True))
    op.create_table(
        "repair_cases",
        sa.Column("id", sa.String(length=128), primary_key=True),
        sa.Column("user_id", sa.String(length=64), sa.ForeignKey("users.id", ondelete="CASCADE")),
        sa.Column("plan_id", sa.String(length=128), nullable=False),
        sa.Column("original_run_id", sa.String(length=128), nullable=True),
        sa.Column("post_edit_run_id", sa.String(length=128), nullable=True),
        sa.Column("gold_sql", sa.Text(), nullable=True),
        sa.Column("gold_result", sa.JSON(), nullable=True),
        sa.Column("metrics", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_repair_cases_user_id", "repair_cases", ["user_id"])
    op.create_index("ix_repair_cases_plan_id", "repair_cases", ["plan_id"])


def downgrade() -> None:
    op.drop_index("ix_repair_cases_plan_id", table_name="repair_cases")
    op.drop_index("ix_repair_cases_user_id", table_name="repair_cases")
    op.drop_table("repair_cases")
    op.drop_column("execution_runs", "node_previews")
