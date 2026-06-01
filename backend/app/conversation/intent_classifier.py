from __future__ import annotations

from app.benchmark_registry import SQLITE_ROOTS, find_benchmark_gold_sql, get_schema_context
from app.config import get_settings
from app.conversation.schemas import ConversationIntent
from app.simple_nl2sql import can_generate_simple_schema_nl2sql


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

    if benchmark in SQLITE_ROOTS and db_id:
        if get_settings().nl2ir_provider.lower() == "kddcup":
            return ConversationIntent(
                intent_type="benchmark_query",
                confidence=0.8,
                requires_plan=True,
                requires_execution=True,
                reason=(
                    f"Message will be handled by the KDDCup trace-based NL2IR provider for "
                    f"{benchmark.upper()}."
                ),
            )

        gold_sql = find_benchmark_gold_sql(benchmark, db_id, message)
        if gold_sql:
            return ConversationIntent(
                intent_type="benchmark_query",
                confidence=0.95,
                requires_plan=True,
                requires_execution=True,
                reason=f"Message matches a {benchmark.upper()} sample question.",
            )

        if can_generate_simple_schema_nl2sql(message, get_schema_context(benchmark, db_id)):
            return ConversationIntent(
                intent_type="benchmark_query",
                confidence=0.62,
                requires_plan=True,
                requires_execution=True,
                reason=(
                    f"Message was handled by the simple schema-aware {benchmark.upper()} demo fallback."
                ),
            )

        return ConversationIntent(
            intent_type="unsupported",
            confidence=0.75,
            requires_plan=False,
            requires_execution=False,
            reason=(
                f"{benchmark.upper()} question does not match a sample and no NL2SQL provider is connected."
            ),
        )

    return ConversationIntent(
        intent_type="benchmark_query",
        confidence=0.55,
        requires_plan=True,
        requires_execution=True,
        reason="Fallback demo query path.",
    )
