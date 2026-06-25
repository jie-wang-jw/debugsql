from __future__ import annotations

from app.conversation.intent_classifier import classify_message
from app.conversation.schemas import ConversationResponse
from app.conversation.tool_assistant import build_proposed_actions
from app.tools.registry import normalize_context


def handle_chat_message(
    message: str,
    session_id: str,
    dataset_context: dict | None = None,
    working_state: dict | None = None,
) -> ConversationResponse:
    intent = classify_message(message, dataset_context)
    context = normalize_context(dataset_context)

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
                "Plan editing has been replaced by tool-assisted actions. Ask a question in natural "
                "language, review the proposed SQL, and approve execution from the chat."
            ),
            intentType=intent.intent_type,
            requiresPlan=False,
            requiresExecution=False,
            explanation=intent.reason,
        )

    if intent.intent_type == "unsupported":
        if working_state:
            # Short follow-ups such as "top 5" or "only black border" may not look like
            # standalone SQL questions. Let the LLM resolver try them against the saved
            # working query before falling back to an unsupported response.
            pass
        else:
            return ConversationResponse(
                content=_unsupported_content(dataset_context),
                intentType=intent.intent_type,
                requiresPlan=False,
                requiresExecution=False,
                explanation=intent.reason,
            )

    content, proposed_actions, sql, metadata = build_proposed_actions(
        message,
        context,
        working_state=working_state,
    )
    requires_approval = any(action.requiresApproval for action in proposed_actions)
    return ConversationResponse(
        content=content,
        intentType=intent.intent_type,
        requiresPlan=False,
        requiresExecution=bool(sql),
        sql=sql,
        explanation=str(metadata.get("llmExplanation") or intent.reason),
        proposedActions=proposed_actions,
        requiresApproval=requires_approval,
        confidence=metadata.get("confidence") if isinstance(metadata.get("confidence"), float) else None,
        assumptions=list(metadata.get("assumptions") or []),
        tablesUsed=list(metadata.get("tablesUsed") or []),
        usedContext=bool(metadata.get("usedContext")),
        conversationMode=metadata.get("conversationMode") if isinstance(metadata.get("conversationMode"), str) else None,
    )


def _help_content(dataset_context: dict | None) -> str:
    context = normalize_context(dataset_context)
    if context.dbType == "postgres":
        scope = "PostgreSQL"
    else:
        benchmark = context.benchmark or "selected benchmark"
        db_id = context.dbId or "selected database"
        scope = f"{benchmark} / {db_id}"
    return (
        "DebugSQL is now a tool-assisted database chat.\n\n"
        f"Current context: **{scope}**.\n\n"
        "Workflow:\n"
        "1. Select a benchmark/database or switch to PostgreSQL in the Capabilities Explorer.\n"
        "2. Ask a question in natural language.\n"
        "3. Review proposed actions (schema inspection, SQL validation, execution).\n"
        "4. Approve execution when you are ready to run read-only SQL."
    )


def _unsupported_content(dataset_context: dict | None) -> str:
    context = normalize_context(dataset_context)
    if context.dbType == "postgres":
        scope = "PostgreSQL"
    else:
        benchmark = context.benchmark or "selected benchmark"
        db_id = context.dbId or "the selected database"
        scope = f"{benchmark} / {db_id}"
    return (
        f"I could not safely generate SQL for **{scope}** from this wording.\n\n"
        "What works today:\n"
        "- Use the Capabilities Explorer to see available tables and example prompts.\n"
        "- Click an example question for the selected benchmark database.\n"
        "- Try simpler schema questions such as `how many rows?`, `show cards`, or `top 10`.\n\n"
        "I did not propose execution because guessed SQL would be misleading."
    )
