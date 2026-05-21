from __future__ import annotations

import hashlib
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


def _result_preview(result: dict[str, Any] | None) -> dict[str, Any] | None:
    if not result:
        return None
    rows = result.get("rows") or []
    return {
        "columns": result.get("columns") or [],
        "rows": rows[:20],
        "rowCount": len(rows),
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
        return {
            "id": conversation.id,
            "sessionId": conversation.session_id,
            "title": conversation.title,
            "datasetContext": conversation.dataset_context,
            "activePlanId": conversation.active_plan_id,
            "updatedAt": conversation.updated_at.isoformat(),
            "messages": [
                {
                    "id": item.id,
                    "role": item.role,
                    "content": item.content,
                    "timestamp": item.created_at.isoformat(),
                    "planId": item.plan_id,
                    "sql": item.sql,
                    "datasetContext": item.dataset_context,
                }
                for item in messages
            ],
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
