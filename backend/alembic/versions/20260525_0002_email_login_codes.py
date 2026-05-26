"""add email login codes

Revision ID: 20260525_0002
Revises: 20260521_0001
Create Date: 2026-05-25
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260525_0002"
down_revision = "20260521_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "email_login_codes",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("code_hash", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("attempt_count", sa.Integer(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("request_ip", sa.String(length=128), nullable=True),
        sa.Column("user_agent", sa.String(length=1000), nullable=True),
    )
    op.create_index("ix_email_login_codes_email", "email_login_codes", ["email"])
    op.create_index("ix_email_login_codes_status", "email_login_codes", ["status"])
    op.create_index("ix_email_login_codes_expires_at", "email_login_codes", ["expires_at"])


def downgrade() -> None:
    op.drop_index("ix_email_login_codes_expires_at", table_name="email_login_codes")
    op.drop_index("ix_email_login_codes_status", table_name="email_login_codes")
    op.drop_index("ix_email_login_codes_email", table_name="email_login_codes")
    op.drop_table("email_login_codes")
