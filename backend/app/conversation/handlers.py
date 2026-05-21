from __future__ import annotations

from app.conversation.intent_classifier import classify_message
from app.conversation.schemas import ConversationResponse
from app.demo_pipeline import generate_plan_for_message


def handle_chat_message(
    message: str,
    session_id: str,
    dataset_context: dict | None = None,
) -> ConversationResponse:
    intent = classify_message(message, dataset_context)

    if intent.intent_type == "help":
        return ConversationResponse(
            content=_help_content(dataset_context),
            intentType=intent.intent_type,
            requiresPlan=False,
            requiresExecution=False,
            explanation=intent.reason,
        )

    if intent.intent_type == "edit_plan":
        return ConversationResponse(
            content=(
                "Plan-edit messages are not routed through chat yet. For now, select a node in the "
                "Query Plan and edit it in the Inspector, then click Apply Changes."
            ),
            intentType=intent.intent_type,
            requiresPlan=False,
            requiresExecution=False,
            explanation=intent.reason,
        )

    if intent.intent_type == "unsupported":
        return ConversationResponse(
            content=_unsupported_content(dataset_context),
            intentType=intent.intent_type,
            requiresPlan=False,
            requiresExecution=False,
            explanation=intent.reason,
        )

    stored = generate_plan_for_message(message, session_id, dataset_context)
    plan = stored["plan"]
    sql = (plan.get("executable") or {}).get("content", "")
    return ConversationResponse(
        content=stored.get("assistant_content") or "I generated a query plan for this request.",
        intentType=intent.intent_type,
        requiresPlan=True,
        requiresExecution=bool(sql),
        planId=plan["plan_id"],
        sql=sql,
        explanation=intent.reason,
    )


def _help_content(dataset_context: dict | None) -> str:
    benchmark = (dataset_context or {}).get("benchmark", "selected benchmark")
    db_id = (dataset_context or {}).get("dbId", "selected database")
    return (
        "DebugSQL currently supports three MVP workflows:\n\n"
        f"1. Select a benchmark/database, currently **{benchmark} / {db_id}**.\n"
        "2. Click a Spider or BIRD example question to test real SQLite execution.\n"
        "3. Ask schema questions such as `what tables are inside this database?`.\n\n"
        "For arbitrary natural-language benchmark questions, the next step is connecting the "
        "real NL2SQL provider. Until then, unsupported questions return guidance instead of fake SQL."
    )


def _unsupported_content(dataset_context: dict | None) -> str:
    db_id = (dataset_context or {}).get("dbId", "the selected database")
    return (
        f"I cannot generate reliable SQL for **{db_id}** from this question yet.\n\n"
        "Please try one of these:\n"
        "- Click a Spider or BIRD example question shown in the chat panel.\n"
        "- Ask what tables or columns are inside the selected database.\n"
        "- Wait until the real NL2SQL provider is connected for arbitrary questions.\n\n"
        "I did not create a query plan because doing so would risk showing incorrect SQL."
    )
