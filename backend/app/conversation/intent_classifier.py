from __future__ import annotations

from app.benchmark_registry import find_spider_gold_sql
from app.conversation.schemas import ConversationIntent


HELP_TERMS = (
    "how to run",
    "how do i run",
    "how to use",
    "what can this system do",
    "help",
    "benchmark",
    "evaluation",
    "evaluate",
)

SCHEMA_TERMS = (
    "inside",
    "schema",
    "tables",
    "columns",
    "what is in",
    "what's in",
)

EDIT_TERMS = (
    "change limit",
    "set limit",
    "remove filter",
    "add filter",
    "sort by",
    "change",
)


def classify_message(message: str, dataset_context: dict | None = None) -> ConversationIntent:
    text = message.lower().strip()
    benchmark = (dataset_context or {}).get("benchmark")
    db_id = (dataset_context or {}).get("dbId")

    if any(term in text for term in EDIT_TERMS):
        return ConversationIntent(
            intent_type="edit_plan",
            confidence=0.65,
            requires_plan=False,
            requires_execution=False,
            reason="Message appears to modify an existing plan.",
        )

    if any(term in text for term in HELP_TERMS):
        return ConversationIntent(
            intent_type="help",
            confidence=0.8,
            requires_plan=False,
            requires_execution=False,
            reason="Message is asking about system or benchmark usage.",
        )

    if benchmark == "spider" and db_id and any(term in text for term in SCHEMA_TERMS):
        return ConversationIntent(
            intent_type="schema_overview",
            confidence=0.85,
            requires_plan=True,
            requires_execution=True,
            reason="Message asks about database structure.",
        )

    if benchmark == "spider" and db_id:
        gold_sql = find_spider_gold_sql(db_id, message)
        if gold_sql:
            return ConversationIntent(
                intent_type="benchmark_query",
                confidence=0.95,
                requires_plan=True,
                requires_execution=True,
                reason="Message matches a Spider sample question.",
            )

        return ConversationIntent(
            intent_type="unsupported",
            confidence=0.75,
            requires_plan=False,
            requires_execution=False,
            reason="Spider question does not match a sample and no NL2SQL provider is connected.",
        )

    return ConversationIntent(
        intent_type="benchmark_query",
        confidence=0.55,
        requires_plan=True,
        requires_execution=True,
        reason="Fallback demo query path.",
    )
