from __future__ import annotations

import uuid
from typing import Any

from app.benchmark_registry import get_schema_context
from app.conversation.sql_resolver import resolve_sql_for_message
from app.tools.registry import normalize_context
from app.tools.schemas import DatasetContext, ProposedToolAction

_SCHEMA_QUESTION_TERMS = (
    "schema",
    "tables and columns",
    "table and column",
    "what tables",
    "which tables",
    "list tables",
    "show tables",
    "available tables",
    "columns are available",
    "column names",
    "describe the database",
    "database structure",
    "what can i see",
    "what can i query",
)


def build_proposed_actions(
    message: str,
    dataset_context: dict | DatasetContext | None,
) -> tuple[str, list[ProposedToolAction], str | None, dict[str, object]]:
    """Build assistant content and proposed tool actions for a benchmark query."""
    context = normalize_context(dataset_context)
    schema = None
    if context.dbType == "sqlite_benchmark" and context.benchmark and context.dbId:
        schema = get_schema_context(context.benchmark, context.dbId)

    resolved = resolve_sql_for_message(message, context, schema)
    sql = resolved.sql
    explanation = resolved.explanation

    actions: list[ProposedToolAction] = []

    if context.dbType == "sqlite_benchmark" and context.benchmark and context.dbId:
        actions.append(
            ProposedToolAction(
                id=_action_id("introspect"),
                tool="introspect_schema",
                label="Inspect schema",
                description=f"Load tables and relationships for {context.benchmark}/{context.dbId}.",
                arguments={},
                requiresApproval=False,
            )
        )

    if sql:
        actions.append(
            ProposedToolAction(
                id=_action_id("preview"),
                tool="run_sql_preview",
                label="Validate SQL",
                description="Check that the proposed query is read-only and safe to run.",
                arguments={"sql": sql},
                requiresApproval=False,
            )
        )
        actions.append(
            ProposedToolAction(
                id=_action_id("run"),
                tool="run_sql",
                label="Run SQL",
                description="Execute the proposed read-only query after approval.",
                arguments={"sql": sql},
                requiresApproval=True,
            )
        )
        content = _sql_proposal_content(context, sql, explanation, resolved)
    elif schema and _is_schema_question(message):
        content = _schema_overview_content(context, schema)
    else:
        content = _no_sql_content(context, message, resolved)

    metadata: dict[str, object] = {
        "provider": resolved.provider,
        "confidence": resolved.confidence,
        "assumptions": list(resolved.assumptions),
        "tablesUsed": list(resolved.tables_used),
        "clarifyingQuestion": resolved.clarifying_question,
    }
    return content, actions, sql, metadata


def _sql_proposal_content(context: DatasetContext, sql: str, explanation: str, resolved) -> str:
    scope = _scope_label(context)
    parts = [
        resolved.answer or f"I prepared a read-only SQL query for **{scope}**.",
        "",
        "Review the proposed actions below. Validation can run immediately; execution requires your approval.",
    ]
    if explanation:
        parts.extend(["", explanation])
    if resolved.assumptions:
        parts.extend(["", "Assumptions:", *[f"- {item}" for item in resolved.assumptions]])
    if resolved.tables_used:
        parts.extend(["", f"Tables used: {', '.join(resolved.tables_used)}"])
    if resolved.confidence is not None:
        parts.extend(["", f"Confidence: {resolved.confidence:.2f}"])
    parts.extend(["", "```sql", sql.strip().rstrip(";") + ";", "```"])
    return "\n".join(parts)


def _is_schema_question(message: str) -> bool:
    text = message.lower().strip()
    return any(term in text for term in _SCHEMA_QUESTION_TERMS)


def is_schema_question(message: str) -> bool:
    return _is_schema_question(message)


def _schema_overview_content(context: DatasetContext, schema: dict[str, Any]) -> str:
    scope = _scope_label(context)
    tables = schema.get("tables", [])
    lines = [
        f"Here are the tables and columns available in **{scope}**:",
        "",
    ]
    for table in tables:
        name = str(table.get("name", ""))
        columns = [
            str(column.get("name", column)) if isinstance(column, dict) else str(column)
            for column in table.get("columns", [])
            if column and column != "*"
        ]
        preview = ", ".join(columns[:10])
        if len(columns) > 10:
            preview = f"{preview}, … +{len(columns) - 10} more"
        lines.append(f"- **{name}** ({len(columns)} columns): {preview or '—'}")
    lines.extend(
        [
            "",
            "See the Capabilities Explorer on the right for relationships and examples, "
            "or ask a data question such as `how many rows in author?`.",
        ]
    )
    return "\n".join(lines)


def _no_sql_content(context: DatasetContext, message: str, resolved) -> str:
    scope = _scope_label(context)
    if resolved.answer or resolved.clarifying_question:
        lines = [
            resolved.answer or f"I could not confidently map your question to SQL for **{scope}**.",
            "",
        ]
        if resolved.clarifying_question:
            lines.extend(["Clarifying question:", resolved.clarifying_question, ""])
        if resolved.explanation:
            lines.extend([resolved.explanation, ""])
        lines.extend(
            [
                "You can still:",
                "- Inspect the available schema with the proposed action below.",
                "- Click an example from the Capabilities Explorer.",
                "- Rephrase with a table name or a simpler question.",
            ]
        )
        return "\n".join(lines)
    return (
        f"I could not confidently map your question to SQL for **{scope}**.\n\n"
        "You can still:\n"
        "- Inspect the available schema with the proposed action below.\n"
        "- Click an example from the Capabilities Explorer.\n"
        "- Rephrase with a table name or a simpler question such as `how many rows?` or `show top 10`.\n\n"
        f"Your message: \"{message.strip()}\""
    )


def _scope_label(context: DatasetContext) -> str:
    if context.dbType == "postgres":
        return "PostgreSQL"
    if context.benchmark and context.dbId:
        return f"{context.benchmark} / {context.dbId}"
    return "the selected database"


def _action_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}"
