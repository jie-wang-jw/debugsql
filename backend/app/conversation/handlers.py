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
        "DebugSQL currently supports two MVP workflows:\n\n"
        f"1. Select a benchmark/database, currently **{benchmark} / {db_id}**.\n"
        "2. Click a Spider or BIRD example question to test real SQLite execution.\n"
        "For arbitrary natural-language benchmark questions, the next step is connecting the "
        "real NL2SQL provider. Until then, unsupported questions do not create query plans."
    )


def _unsupported_content(dataset_context: dict | None) -> str:
    benchmark = (dataset_context or {}).get("benchmark", "selected benchmark")
    db_id = (dataset_context or {}).get("dbId", "the selected database")
    return (
        f"I could not safely generate SQL for **{benchmark} / {db_id}** from this wording.\n\n"
        "What works in the current MVP:\n"
        "- Click one of the example questions shown for the selected database.\n"
        "- Try simple schema questions such as `how many rows?`, `show cards`, "
        "`list names`, or `top 10 cards`.\n\n"
        "What is not connected yet:\n"
        "- Arbitrary NL2SQL with complex joins, nested SQL, or domain reasoning.\n\n"
        "I did not create a query plan because showing guessed SQL would be misleading."
    )
