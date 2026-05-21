"""create core persistence tables

Revision ID: 20260521_0001
Revises:
Create Date: 2026-05-21
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260521_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("display_name", sa.String(length=255), nullable=True),
        sa.Column("avatar_url", sa.String(length=1000), nullable=True),
        sa.Column("auth_mode", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    op.create_table(
        "oauth_accounts",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("user_id", sa.String(length=64), sa.ForeignKey("users.id", ondelete="CASCADE")),
        sa.Column("provider", sa.String(length=64), nullable=False),
        sa.Column("provider_user_id", sa.String(length=255), nullable=False),
        sa.Column("provider_email", sa.String(length=320), nullable=True),
        sa.Column("profile", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("provider", "provider_user_id", name="uq_oauth_provider_user"),
    )
    op.create_index("ix_oauth_accounts_user_id", "oauth_accounts", ["user_id"])

    op.create_table(
        "sessions",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("user_id", sa.String(length=64), sa.ForeignKey("users.id", ondelete="CASCADE")),
        sa.Column("session_token_hash", sa.String(length=255), nullable=False, unique=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_sessions_user_id", "sessions", ["user_id"])

    op.create_table(
        "conversations",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("user_id", sa.String(length=64), sa.ForeignKey("users.id", ondelete="CASCADE")),
        sa.Column("session_id", sa.String(length=255), nullable=False),
        sa.Column("title", sa.String(length=500), nullable=True),
        sa.Column("dataset_context", sa.JSON(), nullable=True),
        sa.Column("active_plan_id", sa.String(length=128), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_conversations_user_id", "conversations", ["user_id"])
    op.create_index("ix_conversations_session_id", "conversations", ["session_id"])

    op.create_table(
        "messages",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column(
            "conversation_id",
            sa.String(length=64),
            sa.ForeignKey("conversations.id", ondelete="CASCADE"),
        ),
        sa.Column("user_id", sa.String(length=64), sa.ForeignKey("users.id", ondelete="CASCADE")),
        sa.Column("role", sa.String(length=32), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("intent_type", sa.String(length=64), nullable=True),
        sa.Column("plan_id", sa.String(length=128), nullable=True),
        sa.Column("sql", sa.Text(), nullable=True),
        sa.Column("dataset_context", sa.JSON(), nullable=True),
        sa.Column("extra", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_messages_conversation_id", "messages", ["conversation_id"])
    op.create_index("ix_messages_user_id", "messages", ["user_id"])

    op.create_table(
        "query_plans",
        sa.Column("id", sa.String(length=128), primary_key=True),
        sa.Column("user_id", sa.String(length=64), sa.ForeignKey("users.id", ondelete="CASCADE")),
        sa.Column(
            "conversation_id",
            sa.String(length=64),
            sa.ForeignKey("conversations.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("session_id", sa.String(length=255), nullable=True),
        sa.Column("benchmark", sa.String(length=64), nullable=True),
        sa.Column("db_id", sa.String(length=255), nullable=True),
        sa.Column("provider", sa.String(length=255), nullable=True),
        sa.Column("template", sa.String(length=255), nullable=True),
        sa.Column("query_text", sa.Text(), nullable=True),
        sa.Column("ir_json", sa.JSON(), nullable=True),
        sa.Column("graph_json", sa.JSON(), nullable=True),
        sa.Column("executable_sql", sa.Text(), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_query_plans_user_id", "query_plans", ["user_id"])
    op.create_index("ix_query_plans_conversation_id", "query_plans", ["conversation_id"])
    op.create_index("ix_query_plans_session_id", "query_plans", ["session_id"])

    op.create_table(
        "plan_edits",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("plan_id", sa.String(length=128), nullable=False),
        sa.Column("user_id", sa.String(length=64), sa.ForeignKey("users.id", ondelete="CASCADE")),
        sa.Column("node_id", sa.String(length=128), nullable=False),
        sa.Column("old_data", sa.JSON(), nullable=True),
        sa.Column("new_data", sa.JSON(), nullable=True),
        sa.Column("edit_result", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_plan_edits_plan_id", "plan_edits", ["plan_id"])
    op.create_index("ix_plan_edits_user_id", "plan_edits", ["user_id"])

    op.create_table(
        "execution_runs",
        sa.Column("id", sa.String(length=128), primary_key=True),
        sa.Column("user_id", sa.String(length=64), sa.ForeignKey("users.id", ondelete="CASCADE")),
        sa.Column("plan_id", sa.String(length=128), nullable=True),
        sa.Column("session_id", sa.String(length=255), nullable=True),
        sa.Column("run_type", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=64), nullable=False),
        sa.Column("sql", sa.Text(), nullable=True),
        sa.Column("node_states", sa.JSON(), nullable=True),
        sa.Column("result_preview", sa.JSON(), nullable=True),
        sa.Column("metrics", sa.JSON(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_execution_runs_user_id", "execution_runs", ["user_id"])
    op.create_index("ix_execution_runs_plan_id", "execution_runs", ["plan_id"])
    op.create_index("ix_execution_runs_session_id", "execution_runs", ["session_id"])

    op.create_table(
        "operation_logs",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("user_id", sa.String(length=64), sa.ForeignKey("users.id", ondelete="CASCADE")),
        sa.Column("session_id", sa.String(length=255), nullable=True),
        sa.Column("operation_type", sa.String(length=128), nullable=False),
        sa.Column("target_type", sa.String(length=128), nullable=True),
        sa.Column("target_id", sa.String(length=255), nullable=True),
        sa.Column("payload", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_operation_logs_user_id", "operation_logs", ["user_id"])
    op.create_index("ix_operation_logs_session_id", "operation_logs", ["session_id"])


def downgrade() -> None:
    op.drop_index("ix_operation_logs_session_id", table_name="operation_logs")
    op.drop_index("ix_operation_logs_user_id", table_name="operation_logs")
    op.drop_table("operation_logs")
    op.drop_index("ix_execution_runs_session_id", table_name="execution_runs")
    op.drop_index("ix_execution_runs_plan_id", table_name="execution_runs")
    op.drop_index("ix_execution_runs_user_id", table_name="execution_runs")
    op.drop_table("execution_runs")
    op.drop_index("ix_plan_edits_user_id", table_name="plan_edits")
    op.drop_index("ix_plan_edits_plan_id", table_name="plan_edits")
    op.drop_table("plan_edits")
    op.drop_index("ix_query_plans_session_id", table_name="query_plans")
    op.drop_index("ix_query_plans_conversation_id", table_name="query_plans")
    op.drop_index("ix_query_plans_user_id", table_name="query_plans")
    op.drop_table("query_plans")
    op.drop_index("ix_messages_user_id", table_name="messages")
    op.drop_index("ix_messages_conversation_id", table_name="messages")
    op.drop_table("messages")
    op.drop_index("ix_conversations_session_id", table_name="conversations")
    op.drop_index("ix_conversations_user_id", table_name="conversations")
    op.drop_table("conversations")
    op.drop_index("ix_sessions_user_id", table_name="sessions")
    op.drop_table("sessions")
    op.drop_index("ix_oauth_accounts_user_id", table_name="oauth_accounts")
    op.drop_table("oauth_accounts")
    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")
