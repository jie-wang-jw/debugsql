"""add conversation working state

Revision ID: 20260624_0005
Revises: 20260608_0004
Create Date: 2026-06-24
"""

from alembic import op
import sqlalchemy as sa


revision = "20260624_0005"
down_revision = "20260608_0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("conversations", sa.Column("working_state", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("conversations", "working_state")
