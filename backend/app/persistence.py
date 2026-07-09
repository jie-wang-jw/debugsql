from __future__ import annotations

import hashlib
import csv
import io
import json
import time
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import desc, func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.auth import ensure_dev_user
from app.database import session_scope
from app.models.history import (
    Conversation,
    ExecutionRun,
    Message,
    OperationLog,
    PlanEdit,
    QueryPlanRecord,
)
from app.models.auth import User


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _stable_id(prefix: str, payload: Any) -> str:
    raw = json.dumps(payload, sort_keys=True, default=str)
    digest = hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]
    return f"{prefix}_{digest}"


def _safe_json(value: Any) -> Any:
    return json.loads(json.dumps(value, default=str))


def _dataset_key(value: dict[str, Any] | None) -> tuple[str | None, str | None, str | None]:
    payload = value or {}
    return (
        payload.get("dbType") or payload.get("db_type") or ("sqlite_benchmark" if payload.get("benchmark") else None),
        payload.get("benchmark"),
        payload.get("dbId") or payload.get("db_id"),
    )


def _same_dataset(left: dict[str, Any] | None, right: dict[str, Any] | None) -> bool:
    return _dataset_key(left) == _dataset_key(right)


def _result_preview(result: dict[str, Any] | None) -> dict[str, Any] | None:
    if not result:
        return None
    rows = result.get("rows") or []
    preview = {
        "columns": result.get("columns") or [],
        "rows": rows[:20],
        "rowCount": (result.get("metrics") or {}).get("rowCount", len(rows)),
    }
    if "mediaPreviews" in result:
        preview["mediaPreviews"] = (result.get("mediaPreviews") or [])[:20]
    return preview


def _execution_restore_preview(run: ExecutionRun | None) -> dict[str, Any] | None:
    if not run or not run.result_preview:
        return None
    preview = dict(run.result_preview)
    preview["sql"] = run.sql or ""
    preview["metrics"] = run.metrics or {
        "planningTimeMs": 0,
        "executionTimeMs": 0,
        "rowCount": preview.get("rowCount", len(preview.get("rows") or [])),
        "estimatedRows": preview.get("rowCount", len(preview.get("rows") or [])),
    }
    return preview


def _message_history_payload(item: Message) -> dict[str, Any]:
    extra = item.extra or {}
    return {
        "id": item.id,
        "role": item.role,
        "content": item.content,
        "timestamp": item.created_at.isoformat(),
        "planId": item.plan_id,
        "sql": item.sql,
        "datasetContext": item.dataset_context,
        "proposedActions": extra.get("proposedActions") or [],
        "requiresApproval": extra.get("requiresApproval"),
        "confidence": extra.get("confidence"),
        "assumptions": extra.get("assumptions") or [],
        "tablesUsed": extra.get("tablesUsed") or [],
        "explanation": extra.get("explanation"),
        "usedContext": extra.get("usedContext"),
        "conversationMode": extra.get("conversationMode"),
        "workingStateRevision": extra.get("workingStateRevision"),
        "mediaMatches": extra.get("mediaMatches") or [],
        "mediaPredicate": extra.get("mediaPredicate"),
        "mediaType": extra.get("mediaType"),
        "mediaLimit": extra.get("mediaLimit"),
    }


def best_effort(operation: str, fn, user_id: str | None = None) -> None:
    try:
        with session_scope() as session:
            effective_user_id = user_id or ensure_dev_user(session).id
            fn(session, effective_user_id)
    except SQLAlchemyError as exc:
        print(f"[persistence] {operation} skipped: {exc}")
    except Exception as exc:  # pragma: no cover - defensive audit path.
        print(f"[persistence] {operation} skipped: {exc}")


def get_or_create_conversation(
    session: Session,
    user_id: str,
    session_id: str,
    dataset_context: dict[str, Any] | None,
    title: str | None = None,
) -> Conversation:
    conversation_id = _stable_id("conv", {"user": user_id, "session": session_id})
    conversation = session.get(Conversation, conversation_id)
    now = _utc_now()
    if conversation:
        if dataset_context and not _same_dataset(conversation.dataset_context, dataset_context):
            conversation.working_state = None
        if dataset_context:
            conversation.dataset_context = _safe_json(dataset_context)
        if title and not conversation.title:
            conversation.title = title[:500]
        conversation.updated_at = now
        return conversation

    conversation = Conversation(
        id=conversation_id,
        user_id=user_id,
        session_id=session_id,
        title=(title or "DebugSQL conversation")[:500],
        dataset_context=_safe_json(dataset_context) if dataset_context else None,
    )
    session.add(conversation)
    session.flush()
    return conversation


def get_conversation_working_state(
    *,
    session_id: str,
    dataset_context: dict[str, Any] | None,
    user_id: str | None = None,
) -> dict[str, Any] | None:
    with session_scope() as session:
        user = session.get(User, user_id) if user_id else ensure_dev_user(session)
        if not user:
            return None
        conversation_id = _stable_id("conv", {"user": user.id, "session": session_id})
        conversation = session.get(Conversation, conversation_id)
        if not conversation or conversation.user_id != user.id or not conversation.working_state:
            return None
        state = dict(conversation.working_state)
        state_context = state.get("dataset_context") or conversation.dataset_context
        if dataset_context and not _same_dataset(state_context, dataset_context):
            return None
        return _safe_json(state)


def get_conversation_message_history(
    *,
    session_id: str,
    dataset_context: dict[str, Any] | None,
    user_id: str | None = None,
) -> list[dict[str, Any]]:
    with session_scope() as session:
        user = session.get(User, user_id) if user_id else ensure_dev_user(session)
        if not user:
            return []
        conversation_id = _stable_id("conv", {"user": user.id, "session": session_id})
        conversation = session.get(Conversation, conversation_id)
        if not conversation or conversation.user_id != user.id:
            return []
        if dataset_context and not _same_dataset(conversation.dataset_context, dataset_context):
            return []
        messages = session.execute(
            select(Message)
            .where(Message.conversation_id == conversation.id, Message.user_id == user.id)
            .order_by(Message.created_at, Message.id)
        ).scalars().all()
        return [_message_history_payload(item) for item in messages]


def _build_working_state(
    *,
    previous: dict[str, Any] | None,
    user_message: str,
    assistant_content: str,
    dataset_context: dict[str, Any] | None,
    response: dict[str, Any],
) -> dict[str, Any] | None:
    sql = response.get("sql")
    if not sql:
        return None

    previous = previous if previous and _same_dataset(previous.get("dataset_context"), dataset_context) else None
    mode = response.get("conversationMode") or "new_query"
    revision = int((previous or {}).get("revision") or 0) + 1
    original_question = (
        (previous or {}).get("original_question")
        if mode == "refine_query" and previous
        else user_message
    )
    return _safe_json(
        {
            "original_question": original_question,
            "latest_user_request": user_message,
            "current_sql": sql,
            "answer": assistant_content,
            "explanation": response.get("llmExplanation") or response.get("explanation"),
            "assumptions": response.get("assumptions") or [],
            "tables_used": response.get("tablesUsed") or [],
            "mediaPredicate": response.get("mediaPredicate"),
            "mediaType": response.get("mediaType"),
            "mediaMatches": response.get("mediaMatches") or [],
            "limit": response.get("mediaLimit"),
            "dataset_context": dataset_context,
            "latest_result_summary": (previous or {}).get("latest_result_summary"),
            "latest_execution_run_id": (previous or {}).get("latest_execution_run_id"),
            "revision": revision,
            "conversation_mode": mode,
            "updated_at": _utc_now().isoformat(),
        }
    )


def _summarize_execution_result(result: dict[str, Any] | None) -> str:
    if not result:
        return "Executed SQL successfully."
    rows = result.get("rows") or []
    metrics = result.get("metrics") or {}
    row_count = metrics.get("rowCount", len(rows))
    if not rows:
        return f"Executed SQL successfully. The query returned {row_count} rows."
    first = rows[0] if isinstance(rows[0], dict) else {}
    preview = ", ".join(f"{key}: {first.get(key)}" for key in list(first)[:4])
    if preview:
        return f"Executed SQL successfully. The query returned {row_count} rows. First row: {preview}."
    return f"Executed SQL successfully. The query returned {row_count} rows."


def update_working_state_execution_summary(
    *,
    session_id: str | None,
    result: dict[str, Any] | None,
    run_id: str | None,
    user_id: str | None = None,
) -> str | None:
    if not session_id:
        return None

    summary = _summarize_execution_result(result)

    def write(session: Session, user_id: str) -> None:
        conversation_id = _stable_id("conv", {"user": user_id, "session": session_id})
        conversation = session.get(Conversation, conversation_id)
        if not conversation or not conversation.working_state:
            return
        state = dict(conversation.working_state)
        state["latest_result_summary"] = summary
        state["latest_execution_run_id"] = run_id
        state["updated_at"] = _utc_now().isoformat()
        conversation.working_state = _safe_json(state)
        conversation.updated_at = _utc_now()

    best_effort("update_working_state_execution_summary", write, user_id=user_id)
    return summary


def persist_chat_interaction(
    *,
    session_id: str,
    user_message: str,
    assistant_content: str,
    dataset_context: dict[str, Any] | None,
    response: dict[str, Any],
    user_id: str | None = None,
) -> None:
    def write(session: Session, user_id: str) -> None:
        conversation = get_or_create_conversation(
            session,
            user_id,
            session_id,
            dataset_context,
            title=user_message,
        )
        plan_id = response.get("planId")
        if plan_id:
            conversation.active_plan_id = plan_id
        new_working_state = _build_working_state(
            previous=conversation.working_state,
            user_message=user_message,
            assistant_content=assistant_content,
            dataset_context=dataset_context,
            response=response,
        )
        if new_working_state:
            conversation.working_state = new_working_state
        conversation.updated_at = _utc_now()

        base = {"conversation": conversation.id, "time": time.time()}
        session.add(
            Message(
                id=_stable_id("msg", {**base, "role": "user", "content": user_message}),
                conversation_id=conversation.id,
                user_id=user_id,
                role="user",
                content=user_message,
                dataset_context=_safe_json(dataset_context) if dataset_context else None,
            )
        )
        session.add(
            Message(
                id=_stable_id("msg", {**base, "role": "assistant", "content": assistant_content}),
                conversation_id=conversation.id,
                user_id=user_id,
                role="assistant",
                content=assistant_content,
                intent_type=response.get("intentType"),
                plan_id=plan_id,
                sql=response.get("sql"),
                dataset_context=_safe_json(dataset_context) if dataset_context else None,
                extra=_safe_json(
                    {
                        "requiresPlan": response.get("requiresPlan"),
                        "requiresExecution": response.get("requiresExecution"),
                        "explanation": response.get("explanation"),
                        "proposedActions": response.get("proposedActions"),
                        "requiresApproval": response.get("requiresApproval"),
                        "confidence": response.get("confidence"),
                        "assumptions": response.get("assumptions"),
                        "tablesUsed": response.get("tablesUsed"),
                        "mediaMatches": response.get("mediaMatches"),
                        "mediaPredicate": response.get("mediaPredicate"),
                        "mediaType": response.get("mediaType"),
                        "mediaLimit": response.get("mediaLimit"),
                        "usedContext": response.get("usedContext"),
                        "conversationMode": response.get("conversationMode"),
                        "workingStateRevision": response.get("workingStateRevision"),
                    }
                ),
            )
        )
        session.add(
            OperationLog(
                id=_stable_id("op", {**base, "type": "chat_query", "message": user_message}),
                user_id=user_id,
                session_id=session_id,
                operation_type="chat_query",
                target_type="conversation",
                target_id=conversation.id,
                payload=_safe_json({"datasetContext": dataset_context, "planId": plan_id}),
            )
        )

    best_effort("persist_chat_interaction", write, user_id=user_id)


def persist_chat_failure(
    *,
    session_id: str,
    user_message: str,
    assistant_content: str,
    dataset_context: dict[str, Any] | None,
    error_type: str,
    error_message: str,
    user_id: str | None = None,
) -> None:
    response = {
        "intentType": "error",
        "requiresPlan": False,
        "requiresExecution": False,
        "explanation": error_message,
        "errorType": error_type,
    }

    def write(session: Session, user_id: str) -> None:
        conversation = get_or_create_conversation(
            session,
            user_id,
            session_id,
            dataset_context,
            title=user_message,
        )
        conversation.updated_at = _utc_now()
        base = {"conversation": conversation.id, "time": time.time()}
        session.add(
            Message(
                id=_stable_id("msg", {**base, "role": "user", "content": user_message}),
                conversation_id=conversation.id,
                user_id=user_id,
                role="user",
                content=user_message,
                dataset_context=_safe_json(dataset_context) if dataset_context else None,
            )
        )
        session.add(
            Message(
                id=_stable_id("msg", {**base, "role": "assistant", "content": assistant_content}),
                conversation_id=conversation.id,
                user_id=user_id,
                role="assistant",
                content=assistant_content,
                intent_type="error",
                dataset_context=_safe_json(dataset_context) if dataset_context else None,
                extra=_safe_json(response),
            )
        )
        session.add(
            OperationLog(
                id=_stable_id("op", {**base, "type": "chat_error", "message": user_message}),
                user_id=user_id,
                session_id=session_id,
                operation_type="chat_error",
                target_type="conversation",
                target_id=conversation.id,
                payload=_safe_json(
                    {
                        "datasetContext": dataset_context,
                        "errorType": error_type,
                        "errorMessage": error_message,
                    }
                ),
            )
        )

    best_effort("persist_chat_failure", write, user_id=user_id)


def persist_query_plan(
    plan_id: str,
    conversation_session_id: str | None = None,
    user_id: str | None = None,
) -> None:
    from app.demo_pipeline import get_plan_record

    record = get_plan_record(plan_id)
    if not record:
        return
    if user_id:
        record["user_id"] = user_id

    def write(session: Session, user_id: str) -> None:
        dataset_context = record.get("dataset_context") or {}
        conversation = None
        session_id = conversation_session_id or record.get("session_id")
        if session_id:
            conversation = get_or_create_conversation(
                session,
                user_id,
                session_id,
                dataset_context,
                title=record.get("message"),
            )
            conversation.active_plan_id = plan_id

        plan = record.get("plan") or {}
        metadata = plan.get("metadata") or {}
        executable = plan.get("executable") or {}
        existing = session.get(QueryPlanRecord, plan_id)
        payload = {
            "user_id": user_id,
            "conversation_id": conversation.id if conversation else None,
            "session_id": session_id,
            "benchmark": dataset_context.get("benchmark") or metadata.get("benchmark"),
            "db_id": dataset_context.get("dbId") or metadata.get("db_id"),
            "provider": metadata.get("provider"),
            "template": metadata.get("template"),
            "query_text": record.get("message"),
            "ir_json": _safe_json(record.get("ir")),
            "graph_json": _safe_json(record.get("graph")),
            "executable_sql": executable.get("content"),
            "metadata_json": _safe_json(metadata),
            "updated_at": _utc_now(),
        }
        if existing:
            for key, value in payload.items():
                setattr(existing, key, value)
        else:
            session.add(QueryPlanRecord(id=plan_id, **payload))

        session.add(
            OperationLog(
                id=_stable_id("op", {"type": "query_plan_saved", "plan": plan_id, "time": time.time()}),
                user_id=user_id,
                session_id=session_id,
                operation_type="query_plan_saved",
                target_type="query_plan",
                target_id=plan_id,
                payload=_safe_json({"template": metadata.get("template"), "datasetContext": dataset_context}),
            )
        )

    best_effort("persist_query_plan", write, user_id=user_id)


def persist_plan_edit(plan_id: str, edit: dict[str, Any], user_id: str | None = None) -> None:
    def write(session: Session, user_id: str) -> None:
        session.add(
            PlanEdit(
                id=_stable_id("edit", {"plan": plan_id, "node": edit.get("node_id"), "time": time.time()}),
                plan_id=plan_id,
                user_id=user_id,
                node_id=edit.get("node_id") or "",
                old_data=_safe_json(edit.get("old_data")),
                new_data=_safe_json(edit.get("new_data")),
                edit_result=_safe_json(edit.get("result")),
            )
        )
        session.add(
            OperationLog(
                id=_stable_id("op", {"type": "plan_edit", "plan": plan_id, "time": time.time()}),
                user_id=user_id,
                session_id=None,
                operation_type=edit.get("operation_type") or edit.get("operationType") or "plan_edit",
                target_type="query_plan",
                target_id=plan_id,
                payload=_safe_json(edit),
            )
        )
        existing = session.get(QueryPlanRecord, plan_id)
        if existing:
            from app.demo_pipeline import get_plan_record

            record = get_plan_record(plan_id) or {}
            existing.graph_json = _safe_json(record.get("graph"))
            existing.executable_sql = ((record.get("plan") or {}).get("executable") or {}).get("content")
            existing.metadata_json = _safe_json((record.get("plan") or {}).get("metadata"))
            existing.updated_at = _utc_now()

    best_effort("persist_plan_edit", write, user_id=user_id)


def persist_execution_run(
    *,
    run_id: str,
    plan_id: str | None,
    session_id: str | None,
    run_type: str,
    status: str,
    sql: str | None,
    result: dict[str, Any] | None = None,
    node_states: dict[str, Any] | None = None,
    node_previews: dict[str, Any] | None = None,
    error_message: str | None = None,
    user_id: str | None = None,
) -> None:
    def write(session: Session, user_id: str) -> None:
        existing = session.get(ExecutionRun, run_id)
        payload = {
            "user_id": user_id,
            "plan_id": plan_id,
            "session_id": session_id,
            "run_type": run_type,
            "status": status,
            "sql": sql,
            "node_states": _safe_json(node_states) if node_states else None,
            "node_previews": _safe_json(node_previews) if node_previews else None,
            "result_preview": _safe_json(_result_preview(result)),
            "metrics": _safe_json(result.get("metrics")) if result else None,
            "error_message": error_message,
            "updated_at": _utc_now(),
        }
        if existing:
            for key, value in payload.items():
                setattr(existing, key, value)
        else:
            session.add(ExecutionRun(id=run_id, **payload))

        session.add(
            OperationLog(
                id=_stable_id("op", {"type": "execution_run", "run": run_id, "time": time.time()}),
                user_id=user_id,
                session_id=session_id,
                operation_type="execution_run",
                target_type="execution_run",
                target_id=run_id,
                payload=_safe_json({"planId": plan_id, "runType": run_type, "status": status}),
            )
        )

    best_effort("persist_execution_run", write, user_id=user_id)


def persist_operation_log(
    *,
    operation_type: str,
    payload: dict[str, Any],
    target_type: str | None = None,
    target_id: str | None = None,
    session_id: str | None = None,
    user_id: str | None = None,
) -> None:
    def write(session: Session, user_id: str) -> None:
        session.add(
            OperationLog(
                id=_stable_id(
                    "op",
                    {
                        "type": operation_type,
                        "target": target_id,
                        "time": time.time(),
                    },
                ),
                user_id=user_id,
                session_id=session_id,
                operation_type=operation_type,
                target_type=target_type,
                target_id=target_id,
                payload=_safe_json(payload),
            )
        )

    best_effort("persist_operation_log", write, user_id=user_id)


def history_summary(limit: int = 20, offset: int = 0, user_id: str | None = None) -> dict[str, Any]:
    with session_scope() as session:
        user = session.get(User, user_id) if user_id else ensure_dev_user(session)
        if not user:
            raise ValueError("User not found")
        total_conversations = session.scalar(
            select(func.count())
            .select_from(Conversation)
            .where(Conversation.user_id == user.id)
        ) or 0
        conversations = session.execute(
            select(Conversation)
            .where(Conversation.user_id == user.id)
            .order_by(desc(Conversation.updated_at))
            .offset(offset)
            .limit(limit)
        ).scalars().all()
        plans = session.execute(
            select(QueryPlanRecord)
            .where(QueryPlanRecord.user_id == user.id)
            .order_by(desc(QueryPlanRecord.updated_at))
            .limit(limit)
        ).scalars().all()
        executions = session.execute(
            select(ExecutionRun)
            .where(ExecutionRun.user_id == user.id)
            .order_by(desc(ExecutionRun.updated_at))
            .limit(limit)
        ).scalars().all()
        return {
            "user": {"id": user.id, "email": user.email, "displayName": user.display_name},
            "pagination": {
                "limit": limit,
                "offset": offset,
                "totalConversations": total_conversations,
                "hasMoreConversations": offset + len(conversations) < total_conversations,
            },
            "conversations": [
                {
                    "id": item.id,
                    "sessionId": item.session_id,
                    "title": item.title,
                    "activePlanId": item.active_plan_id,
                    "updatedAt": item.updated_at.isoformat(),
                }
                for item in conversations
            ],
            "queryPlans": [
                {
                    "id": item.id,
                    "benchmark": item.benchmark,
                    "dbId": item.db_id,
                    "template": item.template,
                    "updatedAt": item.updated_at.isoformat(),
                }
                for item in plans
            ],
            "executionRuns": [
                {
                    "id": item.id,
                    "planId": item.plan_id,
                    "runType": item.run_type,
                    "status": item.status,
                    "updatedAt": item.updated_at.isoformat(),
                }
                for item in executions
            ],
        }


def conversation_detail(conversation_id: str, user_id: str | None = None) -> dict[str, Any] | None:
    with session_scope() as session:
        user = session.get(User, user_id) if user_id else ensure_dev_user(session)
        if not user:
            return None
        conversation = session.get(Conversation, conversation_id)
        if not conversation or conversation.user_id != user.id:
            return None
        messages = session.execute(
            select(Message)
            .where(Message.conversation_id == conversation.id)
            .order_by(Message.created_at)
        ).scalars().all()
        executions = session.execute(
            select(ExecutionRun)
            .where(ExecutionRun.user_id == user.id, ExecutionRun.session_id == conversation.session_id)
            .order_by(desc(ExecutionRun.updated_at))
            .limit(5)
        ).scalars().all()
        latest_execution = executions[0] if executions else None
        return {
            "id": conversation.id,
            "sessionId": conversation.session_id,
            "title": conversation.title,
            "datasetContext": conversation.dataset_context,
            "activePlanId": conversation.active_plan_id,
            "latestExecutionRunId": latest_execution.id if latest_execution else None,
            "latestExecutionStatus": latest_execution.status if latest_execution else None,
            "latestExecutionResultPreview": _execution_restore_preview(latest_execution),
            "updatedAt": conversation.updated_at.isoformat(),
            "messages": [_message_history_payload(item) for item in messages],
            "executionRuns": [
                {
                    "id": item.id,
                    "planId": item.plan_id,
                    "runType": item.run_type,
                    "status": item.status,
                    "resultPreview": item.result_preview,
                    "updatedAt": item.updated_at.isoformat(),
                }
                for item in executions
            ],
        }


def admin_history_summary(limit: int = 20, offset: int = 0) -> dict[str, Any]:
    limit = max(1, min(limit, 100))
    offset = max(0, offset)
    with session_scope() as session:
        total_conversations = session.scalar(select(func.count()).select_from(Conversation)) or 0
        rows = session.execute(
            select(Conversation, User)
            .join(User, Conversation.user_id == User.id)
            .order_by(desc(Conversation.updated_at))
            .offset(offset)
            .limit(limit)
        ).all()
        return {
            "pagination": {
                "limit": limit,
                "offset": offset,
                "totalConversations": total_conversations,
                "hasMoreConversations": offset + len(rows) < total_conversations,
            },
            "conversations": [
                {
                    "id": conversation.id,
                    "sessionId": conversation.session_id,
                    "title": conversation.title,
                    "activePlanId": conversation.active_plan_id,
                    "datasetContext": conversation.dataset_context,
                    "updatedAt": conversation.updated_at.isoformat(),
                    "user": {
                        "id": user.id,
                        "email": user.email,
                        "displayName": user.display_name,
                    },
                }
                for conversation, user in rows
            ],
        }


def admin_conversation_detail(conversation_id: str) -> dict[str, Any] | None:
    with session_scope() as session:
        conversation = session.get(Conversation, conversation_id)
        if not conversation:
            return None
        user = session.get(User, conversation.user_id)
        if not user:
            return None
        messages = session.execute(
            select(Message)
            .where(Message.conversation_id == conversation.id)
            .order_by(Message.created_at)
        ).scalars().all()
        executions = session.execute(
            select(ExecutionRun)
            .where(ExecutionRun.user_id == user.id, ExecutionRun.session_id == conversation.session_id)
            .order_by(desc(ExecutionRun.updated_at))
            .limit(5)
        ).scalars().all()
        latest_execution = executions[0] if executions else None
        return {
            "id": conversation.id,
            "sessionId": conversation.session_id,
            "title": conversation.title,
            "datasetContext": conversation.dataset_context,
            "activePlanId": conversation.active_plan_id,
            "latestExecutionRunId": latest_execution.id if latest_execution else None,
            "latestExecutionStatus": latest_execution.status if latest_execution else None,
            "latestExecutionResultPreview": _execution_restore_preview(latest_execution),
            "updatedAt": conversation.updated_at.isoformat(),
            "user": {
                "id": user.id,
                "email": user.email,
                "displayName": user.display_name,
            },
            "messages": [_message_history_payload(item) for item in messages],
            "executionRuns": [
                {
                    "id": item.id,
                    "planId": item.plan_id,
                    "runType": item.run_type,
                    "status": item.status,
                    "resultPreview": item.result_preview,
                    "updatedAt": item.updated_at.isoformat(),
                }
                for item in executions
            ],
        }


def operation_logs_export(
    *,
    user_id: str | None = None,
    limit: int = 200,
    output_format: str = "json",
) -> str | list[dict[str, Any]]:
    limit = max(1, min(limit, 1000))
    with session_scope() as session:
        user = session.get(User, user_id) if user_id else ensure_dev_user(session)
        if not user:
            raise ValueError("User not found")
        rows = session.execute(
            select(OperationLog)
            .where(OperationLog.user_id == user.id)
            .order_by(desc(OperationLog.created_at))
            .limit(limit)
        ).scalars().all()
        items = [
            {
                "id": item.id,
                "sessionId": item.session_id,
                "operationType": item.operation_type,
                "targetType": item.target_type,
                "targetId": item.target_id,
                "payload": item.payload or {},
                "createdAt": item.created_at.isoformat(),
            }
            for item in rows
        ]

    if output_format == "csv":
        buffer = io.StringIO()
        writer = csv.DictWriter(
            buffer,
            fieldnames=["id", "sessionId", "operationType", "targetType", "targetId", "payload", "createdAt"],
        )
        writer.writeheader()
        for item in items:
            writer.writerow({**item, "payload": json.dumps(item["payload"], sort_keys=True, default=str)})
        return buffer.getvalue()

    return items
