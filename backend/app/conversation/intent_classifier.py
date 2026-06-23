from __future__ import annotations

from app.benchmark_registry import SQLITE_ROOTS
from app.config import get_settings
from app.conversation.schemas import ConversationIntent
from app.conversation.tool_assistant import is_schema_question


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


def _llm_configured() -> bool:
    settings = get_settings()
    provider = settings.query_plan_provider.lower()
    if provider == "gemini":
        return bool(settings.gemini_api_key.strip())
    if provider == "openai_compatible":
        return bool(settings.llm_api_key.strip() and settings.llm_api_base_url.strip())
    return False


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
        if is_schema_question(message):
            return ConversationIntent(
                intent_type="benchmark_query",
                confidence=0.85,
                requires_plan=False,
                requires_execution=False,
                reason=f"Message asks for schema overview in {benchmark.upper()}.",
            )

        if _llm_configured():
            return ConversationIntent(
                intent_type="benchmark_query",
                confidence=0.7,
                requires_plan=False,
                requires_execution=True,
                reason="Message will be handled by the configured SQL assistant.",
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

    if _llm_configured():
        return ConversationIntent(
            intent_type="benchmark_query",
            confidence=0.7,
            requires_plan=False,
            requires_execution=True,
            reason="Message will be handled by the configured SQL assistant.",
        )

    return ConversationIntent(
        intent_type="benchmark_query",
        confidence=0.55,
        requires_plan=False,
        requires_execution=True,
        reason="Fallback demo query path.",
    )
