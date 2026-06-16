from __future__ import annotations

import hashlib
import json
import logging
import re
import time
from typing import Any

from app.benchmark_registry import (
    SQLITE_ROOTS,
    execute_benchmark_sql,
    find_benchmark_gold_sql,
    get_schema_context,
)
from app.config import get_settings
from app.gemini import GeminiService, QueryPlanParseError, gemini_plan_to_graph
from app.gemini.schemas import GeminiConfigError
from app.nl2ir.provider import get_nl2ir_provider
from app.nl2ir.schemas import NL2IRRequest, NL2IRResult
from app.planning.provider import get_ir_to_plan_provider
from app.planning.schemas import ExecutablePlan, PlanNode, PlanningRequest, QueryPlan
from app.simple_nl2sql import build_simple_schema_nl2sql


logger = logging.getLogger(__name__)


PLAN_STORE: dict[str, dict[str, Any]] = {}
RUN_STORE: dict[str, dict[str, Any]] = {}
RUN_OWNER_STORE: dict[str, str | None] = {}
PLAN_RUN_STORE: dict[str, dict[str, Any]] = {}


def build_demo_ir(message: str) -> dict[str, Any]:
    """Small deterministic NL-to-IR stub used until a real NL2IR provider is wired in."""
    text = message.lower()

    metric = "sales"
    if "alcohol" in text:
        metric = "alcohol"
    elif "order" in text:
        metric = "order_count"
    elif "customer" in text:
        metric = "customer_id"

    dimension = "region"
    if "quality" in text:
        dimension = "quality"
    elif "store" in text:
        dimension = "store_id"
    elif "state" in text:
        dimension = "state"

    table = "sales"
    if "wine" in text or "alcohol" in text or "quality" in text:
        table = "wine_quality"
    elif "order" in text or "customer" in text:
        table = "orders"

    aggregation = "avg" if "average" in text or "avg" in text else "sum"
    if "count" in text:
        aggregation = "count"

    filters: list[dict[str, Any]] = []
    if "texas" in text or " tx" in f" {text}":
        filters.append({"column": "state", "op": "=", "value": "TX"})
    if "low stock" in text:
        filters.append({"column": "quantity", "op": "<", "value": 10})

    limit = 10 if "top" in text else None

    return {
        "intent_type": "aggregate",
        "table": table,
        "target_columns": [metric],
        "group_by": [dimension],
        "filters": filters,
        "aggregation": aggregation,
        "order_by": {"column": metric, "direction": "DESC"} if "top" in text else None,
        "limit": limit,
        "raw_query": message,
        "needs_clarification": False,
    }


def _should_use_gemini() -> bool:
    settings = get_settings()
    return (
        settings.query_plan_provider.lower() == "gemini"
        and bool(settings.gemini_api_key.strip())
    )


def _should_use_nl2ir_provider() -> bool:
    provider_name = get_settings().nl2ir_provider.strip().lower()
    return provider_name not in {"", "stub", "disabled", "none"}


def generate_gemini_plan_for_message(
    message: str,
    session_id: str | None = None,
    dataset_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    benchmark = (dataset_context or {}).get("benchmark")
    db_id = (dataset_context or {}).get("dbId")
    schema_context = (
        get_schema_context(benchmark, db_id)
        if benchmark in SQLITE_ROOTS and db_id
        else None
    )

    service = GeminiService()
    gemini_plan = service.generate_query_plan(message, schema_context)
    graph = gemini_plan_to_graph(gemini_plan, message)
    plan_id = _stable_id("plan_gemini", {"message": message, "session": session_id})
    sql = gemini_plan.sql or ""

    stored = {
        "message": message,
        "session_id": session_id,
        "dataset_context": dataset_context,
        "ir": {
            "intent_type": "gemini",
            "raw_query": message,
            "goal": gemini_plan.goal,
        },
        "plan": {
            "plan_id": plan_id,
            "plan_type": "linear",
            "data_source_type": "relational",
            "executable": {"type": "sql", "dialect": "sqlite", "content": sql},
            "metadata": {
                "provider": "gemini",
                "template": "gemini",
                "goal": gemini_plan.goal,
            },
        },
        "graph": graph,
        "assistant_content": _gemini_assistant_content(gemini_plan),
        "created_at": time.time(),
    }
    PLAN_STORE[plan_id] = stored
    return stored


def generate_plan_for_message(
    message: str,
    session_id: str | None = None,
    dataset_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    benchmark = (dataset_context or {}).get("benchmark")
    db_id = (dataset_context or {}).get("dbId")

    if not benchmark and _is_sales_store_demo(message):
        stored = _build_sales_store_demo(message, session_id)
        PLAN_STORE[stored["plan"]["plan_id"]] = stored
        return stored

    if _should_use_gemini():
        try:
            return generate_gemini_plan_for_message(message, session_id, dataset_context)
        except (GeminiConfigError, QueryPlanParseError, TimeoutError, RuntimeError) as exc:
            logger.warning("Gemini plan generation failed, falling back to legacy pipeline: %s", exc)

    schema_context = get_schema_context(benchmark, db_id)
    nl2ir_result = (
        get_nl2ir_provider().generate_ir(
            NL2IRRequest(
                message=message,
                schema_context=schema_context,
                dataset_context=dataset_context,
            )
        )
        if benchmark in SQLITE_ROOTS and db_id and _should_use_nl2ir_provider()
        else None
    )

    gold_sql = (
        None
        if nl2ir_result
        else find_benchmark_gold_sql(benchmark, db_id, message)
        if benchmark in SQLITE_ROOTS
        else None
    )
    fallback = (
        build_simple_schema_nl2sql(message, schema_context)
        if benchmark in SQLITE_ROOTS and db_id and not gold_sql and not nl2ir_result
        else None
    )
    if benchmark in SQLITE_ROOTS and db_id and not gold_sql and not fallback and not nl2ir_result:
        raise ValueError("No benchmark gold SQL found for this question.")

    intent_ir = (
        nl2ir_result.intent_ir
        if nl2ir_result
        else fallback.intent_ir
        if fallback
        else build_demo_ir(message)
    )
    if dataset_context:
        intent_ir["dataset_context"] = dataset_context

    schema_context = schema_context or {
        "tables": [
            {
                "name": intent_ir["table"],
                "columns": list(
                    dict.fromkeys(
                        [
                            *intent_ir.get("target_columns", []),
                            *intent_ir.get("group_by", []),
                            "state",
                            "quantity",
                        ]
                    )
                ),
            }
        ]
    }
    request = PlanningRequest(intent_ir=intent_ir, schema_context=schema_context)
    plan = get_ir_to_plan_provider().generate_plan(request)
    if nl2ir_result:
        _apply_nl2ir_result_to_plan(plan, nl2ir_result)
    if gold_sql and plan.executable:
        plan.executable.content = gold_sql
        plan.metadata["template"] = "benchmark_gold_sql"
    if fallback and plan.executable:
        plan.executable.content = fallback.sql
        plan.metadata["template"] = "schema_fallback_sql"
        plan.metadata["fallback_explanation"] = fallback.explanation
    graph = query_plan_to_graph(plan, message)
    assistant_content = (
        _benchmark_query_content(
            plan.executable.content,
            graph,
            (dataset_context or {}).get("benchmark"),
        )
        if gold_sql and plan.executable
        else _kddcup_trace_content(nl2ir_result, plan.executable.content if plan.executable else "", graph)
        if nl2ir_result
        else _schema_fallback_content(fallback, plan.executable.content, graph)
        if fallback and plan.executable
        else _assistant_content((plan.executable.content if plan.executable else ""), graph)
    )

    PLAN_STORE[plan.plan_id] = {
        "message": message,
        "session_id": session_id,
        "dataset_context": dataset_context,
        "ir": intent_ir,
        "plan": _plan_with_dataset_metadata(plan, dataset_context),
        "graph": graph,
        "assistant_content": assistant_content,
        "created_at": time.time(),
    }
    return PLAN_STORE[plan.plan_id]


def get_plan_graph(plan_id: str, user_id: str | None = None) -> dict[str, Any] | None:
    stored = PLAN_STORE.get(plan_id)
    if stored and not _stored_plan_allowed(stored, user_id):
        return None
    if not stored:
        stored = _restore_plan_from_database(plan_id, user_id=user_id)
    if not stored:
        return None
    return stored["graph"]


def get_plan_record(plan_id: str, user_id: str | None = None) -> dict[str, Any] | None:
    stored = PLAN_STORE.get(plan_id)
    if stored and _stored_plan_allowed(stored, user_id):
        return stored
    if stored and user_id:
        return None
    return _restore_plan_from_database(plan_id, user_id=user_id)


def update_plan_node(
    plan_id: str,
    node_id: str,
    data: dict[str, Any],
    user_id: str | None = None,
) -> dict[str, Any] | None:
    graph = get_plan_graph(plan_id, user_id=user_id)
    if not graph:
        return None

    old_data: dict[str, Any] | None = None
    for node in graph["nodes"]:
        if node["id"] == node_id:
            old_data = dict(node.get("data", {}))
            node["data"] = data
            node["data"]["_lastEditedAt"] = int(time.time())
            node["data"]["_editVersion"] = int(node["data"].get("_editVersion") or 0) + 1
            if node["data"].get("kind") == "operation":
                node["data"]["executionState"] = "pending"
            if node["data"].get("kind") == "data":
                node["data"]["executionState"] = "pending"
                node["data"]["materialized"] = False
            break
    else:
        return None

    before_sql = ((get_plan_record(plan_id, user_id=user_id) or {}).get("plan") or {}).get("executable", {}).get("content")
    downstream = _mark_downstream_pending(graph, node_id)
    _clear_plan_run_state(plan_id, graph)
    edit_result = _apply_node_edit_to_executable(plan_id, node_id)
    after_sql = ((get_plan_record(plan_id, user_id=user_id) or {}).get("plan") or {}).get("executable", {}).get("content")
    edit_result["editedNodeId"] = node_id
    edit_result["downstreamNodeIds"] = sorted(downstream)
    edit_result["needsReplan"] = edit_result.get("status") == "needs_replan" or not edit_result.get("executableAvailable", True)
    edit_result["operationType"] = "plan_edit_replan"
    edit_result["executableSqlChanged"] = before_sql != after_sql
    _record_plan_edit(plan_id, node_id, old_data, data, edit_result)
    _persist_latest_plan_edit(plan_id, user_id=user_id)
    graph["editStatus"] = edit_result
    graph["lastEditResult"] = edit_result
    graph["needsReplan"] = bool(edit_result["needsReplan"])
    return graph


def merge_plan_nodes(
    plan_id: str,
    node_ids: list[str],
    user_id: str | None = None,
) -> dict[str, Any] | None:
    graph = get_plan_graph(plan_id, user_id=user_id)
    stored = get_plan_record(plan_id, user_id=user_id)
    if not graph or not stored:
        return None

    selected_ids = [node_id for node_id in node_ids if node_id]
    if len(selected_ids) < 2:
        graph["lastEditResult"] = _merge_result("needs_replan", "Select at least two operation nodes to merge.", selected_ids)
        return graph

    selected_nodes = [_graph_node(graph, node_id) for node_id in selected_ids]
    if any(node is None for node in selected_nodes):
        graph["lastEditResult"] = _merge_result("needs_replan", "One or more selected nodes were not found.", selected_ids)
        return graph
    if any((node or {}).get("data", {}).get("kind") != "operation" for node in selected_nodes):
        graph["lastEditResult"] = _merge_result("needs_replan", "Only operation nodes can be merged in the MVP.", selected_ids)
        return graph

    ordered = [node_id for node_id in _plan_node_order(graph) if node_id in selected_ids]
    if set(ordered) != set(selected_ids) or not _nodes_form_adjacent_path(graph, ordered):
        graph["lastEditResult"] = _merge_result(
            "needs_replan",
            "Only adjacent operation nodes on the same query-plan path can be merged.",
            selected_ids,
        )
        return graph

    operation_types = [
        str((_graph_node(graph, node_id) or {}).get("data", {}).get("operationType") or "").upper()
        for node_id in ordered
    ]
    if not _merge_supported(operation_types):
        graph["lastEditResult"] = _merge_result(
            "needs_replan",
            f"Merge is not supported for operation sequence: {' + '.join(operation_types)}.",
            selected_ids,
        )
        return graph

    target_id = ordered[0]
    target = _graph_node(graph, target_id)
    assert target is not None
    target_data = target.setdefault("data", {})
    old_data = dict(target_data)
    merged_details = [
        str((_graph_node(graph, node_id) or {}).get("data", {}).get("detail") or "")
        for node_id in ordered
    ]
    target_data.update(
        {
            "kind": "operation",
            "operationType": "MERGED",
            "label": " + ".join(operation_types),
            "detail": " | ".join(detail for detail in merged_details if detail),
            "mergedFrom": ordered,
            "executionState": "pending",
            "_lastEditedAt": int(time.time()),
            "_editVersion": int(target_data.get("_editVersion") or 0) + 1,
        }
    )

    removed = set(ordered[1:])
    graph["nodes"] = [node for node in graph.get("nodes", []) if node.get("id") not in removed]
    graph["edges"] = _rewire_merged_edges(graph.get("edges", []), target_id, removed)
    downstream = _mark_downstream_pending(graph, target_id)
    _clear_plan_run_state(plan_id, graph)

    edit_result = _merge_result(
        "graph_updated",
        f"Merged adjacent operation nodes: {' + '.join(operation_types)}.",
        ordered,
        downstream,
    )
    graph["editStatus"] = edit_result
    graph["lastEditResult"] = edit_result
    graph["needsReplan"] = False
    _record_plan_edit(plan_id, target_id, old_data, target_data, edit_result)
    _persist_latest_plan_edit(plan_id, user_id=user_id)
    return graph


def run_demo_execution(
    sql_or_query: str,
    session_id: str | None = None,
    plan_id: str | None = None,
    user_id: str | None = None,
) -> dict[str, Any]:
    run_id = _stable_id("run", {"sql": sql_or_query, "session": session_id, "plan": plan_id, "time": time.time()})
    if _plan_requires_replan(plan_id):
        result = _replan_required_execution_result(plan_id)
        RUN_STORE[run_id] = result
        RUN_OWNER_STORE[run_id] = user_id
        _persist_execution(run_id, plan_id, session_id, "sql", "success", result.get("sql"), result, user_id=user_id)
        return {"runId": run_id, "status": "running"}

    sql = _execution_sql(sql_or_query, plan_id)
    if not sql.strip():
        result = _replan_required_execution_result(plan_id)
        RUN_STORE[run_id] = result
        RUN_OWNER_STORE[run_id] = user_id
        _persist_execution(run_id, plan_id, session_id, "sql", result.get("status", "success"), sql, result, user_id=user_id)
        return {"runId": run_id, "status": "running"}

    dataset_context = _plan_dataset_context(plan_id)
    benchmark = (dataset_context or {}).get("benchmark")
    db_id = (dataset_context or {}).get("dbId")
    if benchmark in SQLITE_ROOTS and db_id:
        result = execute_benchmark_sql(benchmark, db_id, sql)
    else:
        rows, columns = _execution_rows(sql)
        result = {
            "sql": sql,
            "columns": columns,
            "rows": rows,
            "metrics": {
                "planningTimeMs": 42,
                "executionTimeMs": 86,
                "rowCount": len(rows),
                "estimatedRows": 1200,
            },
        }
    _apply_execution_result_to_result_nodes(plan_id, result)
    RUN_STORE[run_id] = result
    RUN_OWNER_STORE[run_id] = user_id
    _persist_execution(run_id, plan_id, session_id, "sql", "success", result.get("sql"), result, user_id=user_id)
    return {"runId": run_id, "status": "running"}


def get_execution_result(run_id: str, user_id: str | None = None) -> dict[str, Any] | None:
    result = RUN_STORE.get(run_id)
    if result:
        owner = RUN_OWNER_STORE.get(run_id)
        if user_id and owner and owner != user_id:
            return None
        return result
    return _restore_execution_result_from_database(run_id, user_id=user_id)


def create_plan_run(plan_id: str, user_id: str | None = None) -> dict[str, Any] | None:
    stored = get_plan_record(plan_id, user_id=user_id)
    if not stored:
        return None

    graph = stored["graph"]
    order = _plan_node_order(graph)
    run_id = _stable_id("plan_run", {"plan": plan_id, "time": time.time()})
    node_states = {node_id: "pending" for node_id in order}
    run = {
        "runId": run_id,
        "planId": plan_id,
        "status": "idle",
        "nodeOrder": order,
        "currentNodeId": None,
        "nextNodeId": order[0] if order else None,
        "nodeStates": node_states,
        "stepsCompleted": 0,
        "totalSteps": len(order),
        "resultRunId": None,
        "result": None,
        "userId": user_id,
        "createdAt": time.time(),
        "updatedAt": time.time(),
    }
    PLAN_RUN_STORE[run_id] = run
    _apply_plan_run_to_graph(plan_id, run)
    _persist_execution(run_id, plan_id, None, "plan_step", "idle", None, None, node_states, user_id=user_id)
    return _public_plan_run(run)


def get_plan_run(run_id: str, user_id: str | None = None) -> dict[str, Any] | None:
    run = PLAN_RUN_STORE.get(run_id)
    if not run:
        run = _restore_plan_run_from_database(run_id, user_id=user_id)
    if run and user_id and run.get("userId") and run.get("userId") != user_id:
        return None
    return _public_plan_run(run) if run else None


def step_plan_run(plan_id: str, run_id: str, user_id: str | None = None) -> dict[str, Any] | None:
    run = PLAN_RUN_STORE.get(run_id)
    if not run:
        run = _restore_plan_run_from_database(run_id, user_id=user_id)
    if not run or run.get("planId") != plan_id:
        return None

    if run["status"] in {"success", "error"}:
        return _public_plan_run(run)

    order: list[str] = run["nodeOrder"]
    index = int(run["stepsCompleted"])
    if index >= len(order):
        run["status"] = "success"
        run["currentNodeId"] = None
        run["nextNodeId"] = None
        run["updatedAt"] = time.time()
        _apply_plan_run_to_graph(plan_id, run)
        return _public_plan_run(run)

    node_id = order[index]
    node_preview = _node_step_preview(plan_id, node_id)
    run["status"] = "running"
    run["currentNodeId"] = node_id
    run["nextNodeId"] = order[index + 1] if index + 1 < len(order) else None
    run["nodeStates"][node_id] = "running"
    run.setdefault("nodePreviews", {})[node_id] = node_preview
    _apply_plan_run_to_graph(plan_id, run)

    try:
        if index == len(order) - 1:
            execution = run_demo_execution("step-plan-run", "dev-session", plan_id, user_id=user_id or run.get("userId"))
            result = get_execution_result(execution["runId"], user_id=user_id or run.get("userId"))
            run["resultRunId"] = execution["runId"]
            run["result"] = result
            run.setdefault("nodePreviews", {})[node_id] = _result_step_preview(result)
        elif node_preview.get("status") == "error":
            raise ValueError(node_preview.get("errorMessage") or node_preview.get("message") or "Node materialization failed.")
        run["nodeStates"][node_id] = "success"
        run["stepsCompleted"] = index + 1
        run["status"] = "success" if run["stepsCompleted"] >= len(order) else "running"
        run["currentNodeId"] = node_id
        run["nextNodeId"] = order[run["stepsCompleted"]] if run["stepsCompleted"] < len(order) else None
    except Exception as exc:  # pragma: no cover - defensive state capture for API callers.
        run["nodeStates"][node_id] = "error"
        run["status"] = "error"
        run["error"] = str(exc)
        run.setdefault("nodePreviews", {})[node_id] = {
            **node_preview,
            "status": "error",
            "message": str(exc),
            "errorMessage": str(exc),
        }

    run["updatedAt"] = time.time()
    _apply_plan_run_to_graph(plan_id, run)
    _persist_execution(
        run_id,
        plan_id,
        None,
        "plan_step",
        run["status"],
        (run.get("result") or {}).get("sql"),
        run.get("result"),
        run.get("nodeStates"),
        run.get("error"),
        node_previews=run.get("nodePreviews"),
        user_id=user_id or run.get("userId"),
    )
    return _public_plan_run(run)


def run_full_plan(plan_id: str, run_id: str, user_id: str | None = None) -> dict[str, Any] | None:
    run = PLAN_RUN_STORE.get(run_id)
    if not run:
        run = _restore_plan_run_from_database(run_id, user_id=user_id)
    if not run or run.get("planId") != plan_id:
        return None

    while run.get("status") not in {"success", "error"}:
        step_plan_run(plan_id, run_id, user_id=user_id)
        run = PLAN_RUN_STORE[run_id]
        if int(run["stepsCompleted"]) >= int(run["totalSteps"]):
            break
    return _public_plan_run(run)


def reset_plan_run(plan_id: str, run_id: str, user_id: str | None = None) -> dict[str, Any] | None:
    run = PLAN_RUN_STORE.get(run_id)
    if not run:
        run = _restore_plan_run_from_database(run_id, user_id=user_id)
    if not run or run.get("planId") != plan_id:
        return None

    order: list[str] = run["nodeOrder"]
    run["status"] = "idle"
    run["currentNodeId"] = None
    run["nextNodeId"] = order[0] if order else None
    run["nodeStates"] = {node_id: "pending" for node_id in order}
    run["nodePreviews"] = {}
    run["stepsCompleted"] = 0
    run["resultRunId"] = None
    run["result"] = None
    run.pop("error", None)
    run["updatedAt"] = time.time()
    _clear_graph_previews(PLAN_STORE.get(plan_id, {}).get("graph") or {}, set(order))
    _apply_plan_run_to_graph(plan_id, run)
    _persist_execution(run_id, plan_id, None, "plan_step", "idle", None, None, run["nodeStates"], user_id=user_id or run.get("userId"))
    return _public_plan_run(run)


def _plan_with_dataset_metadata(plan: QueryPlan, dataset_context: dict[str, Any] | None) -> dict[str, Any]:
    dumped = plan.model_dump()
    if dataset_context:
        dumped.setdefault("metadata", {})["dataset_context"] = dataset_context
        dumped["metadata"]["benchmark"] = dataset_context.get("benchmark")
        dumped["metadata"]["db_id"] = dataset_context.get("dbId")
    return dumped


def _restore_plan_from_database(plan_id: str, user_id: str | None = None) -> dict[str, Any] | None:
    try:
        from app.database import session_scope
        from app.models.history import QueryPlanRecord

        with session_scope() as session:
            record = session.get(QueryPlanRecord, plan_id)
            if not record or not record.graph_json:
                return None
            if user_id and record.user_id != user_id:
                return None
            stored = {
                "message": record.query_text or record.id,
                "session_id": record.session_id,
                "user_id": record.user_id,
                "dataset_context": (
                    {"benchmark": record.benchmark, "dbId": record.db_id}
                    if record.benchmark and record.db_id
                    else None
                ),
                "ir": record.ir_json or {},
                "plan": {
                    "plan_id": record.id,
                    "metadata": record.metadata_json or {},
                    "executable": {
                        "type": "sql",
                        "dialect": "sqlite",
                        "content": record.executable_sql or "",
                    },
                },
                "graph": record.graph_json,
                "assistant_content": "",
                "created_at": time.time(),
            }
            PLAN_STORE[plan_id] = stored
            return stored
    except Exception as exc:  # pragma: no cover - best-effort restore path.
        print(f"[persistence] query plan restore skipped: {exc}")
        return None


def _stored_plan_allowed(stored: dict[str, Any], user_id: str | None) -> bool:
    if not user_id:
        return True
    owner = stored.get("user_id") or stored.get("userId")
    return not owner or owner == user_id


def _restore_execution_result_from_database(run_id: str, user_id: str | None = None) -> dict[str, Any] | None:
    try:
        from app.database import session_scope
        from app.models.history import ExecutionRun

        with session_scope() as session:
            record = session.get(ExecutionRun, run_id)
            if not record:
                return None
            if user_id and record.user_id != user_id:
                return None
            result = _execution_result_from_record(record)
            _apply_execution_result_to_result_nodes(record.plan_id, result, persist=False)
            RUN_STORE[run_id] = result
            RUN_OWNER_STORE[run_id] = record.user_id
            return result
    except Exception as exc:  # pragma: no cover - best-effort restore path.
        print(f"[persistence] execution restore skipped: {exc}")
        return None


def _execution_result_from_record(record: Any) -> dict[str, Any]:
    preview = record.result_preview or {}
    rows = preview.get("rows") or []
    columns = preview.get("columns") or []
    metrics = record.metrics or {}
    if not metrics:
        metrics = {
            "planningTimeMs": 0,
            "executionTimeMs": 0,
            "rowCount": preview.get("rowCount", len(rows)),
            "estimatedRows": preview.get("rowCount", len(rows)),
        }
    if record.error_message and not rows:
        columns = [{"key": "error", "label": "error"}]
        rows = [{"error": record.error_message}]
    return {
        "sql": record.sql or "",
        "columns": columns,
        "rows": rows,
        "metrics": metrics,
    }


def _restore_plan_run_from_database(run_id: str, user_id: str | None = None) -> dict[str, Any] | None:
    try:
        from app.database import session_scope
        from app.models.history import ExecutionRun

        with session_scope() as session:
            record = session.get(ExecutionRun, run_id)
            if not record or record.run_type != "plan_step" or not record.plan_id:
                return None
            if user_id and record.user_id != user_id:
                return None
            stored = get_plan_record(record.plan_id, user_id=record.user_id)
            if not stored:
                return None
            order = _plan_node_order(stored["graph"])
            node_states = record.node_states or {node_id: "pending" for node_id in order}
            steps_completed = sum(1 for node_id in order if node_states.get(node_id) == "success")
            next_node_id = next((node_id for node_id in order if node_states.get(node_id) == "pending"), None)
            current_node_id = next((node_id for node_id in order if node_states.get(node_id) == "running"), None)
            run = {
                "runId": record.id,
                "planId": record.plan_id,
                "status": record.status,
                "nodeOrder": order,
                "currentNodeId": current_node_id,
                "nextNodeId": None if record.status in {"success", "error"} else next_node_id,
                "nodeStates": node_states,
                "nodePreviews": record.node_previews or {},
                "stepsCompleted": steps_completed,
                "totalSteps": len(order),
                "resultRunId": record.id if record.result_preview else None,
                "result": _execution_result_from_record(record) if record.result_preview or record.error_message else None,
                "error": record.error_message,
                "userId": record.user_id,
                "createdAt": record.created_at.timestamp(),
                "updatedAt": record.updated_at.timestamp(),
            }
            PLAN_RUN_STORE[run_id] = run
            _apply_plan_run_to_graph(record.plan_id, run)
            return run
    except Exception as exc:  # pragma: no cover - best-effort restore path.
        print(f"[persistence] plan run restore skipped: {exc}")
        return None


def _plan_dataset_context(plan_id: str | None) -> dict[str, Any] | None:
    if not plan_id:
        return None
    if plan_id not in PLAN_STORE:
        _restore_plan_from_database(plan_id)
    if plan_id not in PLAN_STORE:
        return None
    stored = PLAN_STORE[plan_id]
    context = stored.get("dataset_context")
    if context:
        return context
    metadata = stored.get("plan", {}).get("metadata", {})
    return metadata.get("dataset_context")


def _plan_template(plan_id: str | None) -> str | None:
    if not plan_id:
        return None
    if plan_id not in PLAN_STORE:
        _restore_plan_from_database(plan_id)
    if plan_id not in PLAN_STORE:
        return None
    return PLAN_STORE[plan_id].get("plan", {}).get("metadata", {}).get("template")


def _plan_requires_replan(plan_id: str | None) -> bool:
    if not plan_id:
        return False
    if plan_id not in PLAN_STORE:
        _restore_plan_from_database(plan_id)
    if plan_id not in PLAN_STORE:
        return False
    metadata = PLAN_STORE[plan_id].get("plan", {}).get("metadata", {})
    return bool(metadata.get("requires_replan"))


def query_plan_to_graph(plan: QueryPlan, query_label: str) -> dict[str, Any]:
    levels = _node_levels(plan)
    nodes = []
    for index, node in enumerate(plan.nodes):
        level = levels.get(node.node_id, index)
        nodes.append(
            {
                "id": node.node_id,
                "type": node.node_type,
                "position": {"x": 80 + level * 190, "y": 70 + level * 82},
                "data": _flow_node_data(node),
            }
        )

    edges = [
        {
            "id": f"{edge.source}-{edge.target}",
            "source": edge.source,
            "target": edge.target,
            "animated": edge.edge_type == "data_flow",
        }
        for edge in plan.edges
    ]
    return {
        "nodes": nodes,
        "edges": edges,
        "queryLabel": query_label,
        "totalCost": round(18.5 + len(nodes) * 7.3, 1),
    }


def _is_sales_store_demo(message: str) -> bool:
    text = message.lower()
    return (
        ("store" in text or "stores" in text)
        and ("top" in text or "rank" in text or "sales" in text or "selling" in text)
    )


def _build_sales_store_demo(message: str, session_id: str | None) -> dict[str, Any]:
    has_texas_filter = "texas" in message.lower() or " tx" in f" {message.lower()}"
    plan_id = _stable_id("plan_demo", {"message": message})
    filter_text = "state = 'TX'" if has_texas_filter else "sales_date >= CURRENT_DATE - 30"
    sql = (
        "SELECT\n"
        "  s.store_id,\n"
        "  s.store_name,\n"
        "  SUM(t.amount) AS total_sales\n"
        "FROM sales_transactions t\n"
        "JOIN stores s ON t.store_id = s.store_id\n"
        f"WHERE {filter_text}\n"
        "GROUP BY s.store_id, s.store_name\n"
        "ORDER BY total_sales DESC\n"
        "LIMIT 10;"
    )
    intent_ir = {
        "intent_type": "ranked_aggregation",
        "table": "sales_transactions",
        "target_columns": ["amount", "store_id", "store_name"],
        "group_by": ["store_id", "store_name"],
        "filters": [{"column": "state", "op": "=", "value": "TX"}] if has_texas_filter else [],
        "aggregation": "sum",
        "order_by": {"column": "total_sales", "direction": "DESC"},
        "limit": 10,
        "raw_query": message,
    }
    graph = {
        "queryLabel": message,
        "totalCost": 63.1,
        "nodes": [
            _intent_node(
                "intent",
                80,
                40,
                "Ranked Sales Query",
                "SUM(amount)",
                [filter_text],
                ["store_id"],
                ["amount", "store_id", "store_name"],
            ),
            _data_node(
                "data_sales",
                80,
                270,
                "sales_transactions",
                "source",
                284000,
                18.9,
                ["id", "store_id", "amount", "state", "sale_date"],
            ),
            _op_node("op_filter", 540, 80, "FILTER", "Filter", filter_text, 18400, 12.4),
            _data_node(
                "data_stores",
                820,
                270,
                "stores",
                "source",
                420,
                2.8,
                ["store_id", "store_name", "region", "state"],
            ),
            _op_node(
                "op_join",
                590,
                270,
                "JOIN",
                "Hash Join",
                "sales.store_id = stores.store_id",
                18400,
                45.2,
            ),
            _op_node("op_group_by", 590, 450, "GROUP_BY", "Group By", "store_id, store_name", 28, 52.1),
            _op_node("op_aggregate", 590, 600, "AGGREGATE", "Aggregate", "SUM(amount) AS total_sales", 28, 62.8),
            _op_node("op_sort", 590, 760, "SORT", "Sort", "total_sales DESC", 28, 63.1),
            _op_node("op_limit", 590, 900, "LIMIT", "Limit", "LIMIT 10", 10, 63.1),
            _data_node(
                "data_result",
                590,
                1040,
                "Result",
                "result",
                10,
                63.1,
                ["store_id", "store_name", "total_sales"],
            ),
        ],
        "edges": [
            _edge("intent", "op_filter", animated=True),
            _edge("data_sales", "op_join", animated=True),
            _edge("op_filter", "op_join", animated=True),
            _edge("data_stores", "op_join", animated=True),
            _edge("op_join", "op_group_by"),
            _edge("op_group_by", "op_aggregate"),
            _edge("op_aggregate", "op_sort"),
            _edge("op_sort", "op_limit"),
            _edge("op_limit", "data_result", animated=True),
        ],
    }
    return {
        "message": message,
        "session_id": session_id,
        "ir": intent_ir,
        "plan": {
            "plan_id": plan_id,
            "plan_type": "tree",
            "data_source_type": "relational",
            "executable": {"type": "sql", "dialect": "sqlite", "content": sql},
            "metadata": {"provider": "backend_demo_template", "template": "sales_store_ranking"},
        },
        "graph": graph,
        "assistant_content": _assistant_content(sql, graph),
        "created_at": time.time(),
    }


def _assistant_content(sql: str, graph: dict[str, Any]) -> str:
    return (
        "I've created a backend-generated plan for your ranked/sorted query.\n\n"
        f"```sql\n{sql}\n```\n\n"
        "The plan includes table scan, filter, join, group-by, aggregate, sort, "
        f"and result nodes. Total cost: **{graph['totalCost']:.1f}**."
    )


def _gemini_assistant_content(plan) -> str:
    step_count = len(plan.steps)
    sql_block = f"\n\n```sql\n{plan.sql}\n```" if plan.sql else ""
    return (
        f"I generated a query plan for your question.\n\n"
        f"**Goal:** {plan.goal}\n\n"
        f"The plan has **{step_count}** step(s). "
        "Open the Query Plan panel to inspect each step."
        f"{sql_block}"
    )


def _apply_nl2ir_result_to_plan(plan: QueryPlan, result: NL2IRResult) -> None:
    metadata = plan.metadata
    metadata["provider"] = result.provider_name
    metadata["template"] = "kddcup_trace_sql" if result.selected_sql else "kddcup_trace_no_sql"
    metadata["trace"] = result.trace
    metadata["agent_succeeded"] = result.succeeded
    if result.error_message:
        metadata["agent_error"] = result.error_message

    if not plan.executable:
        plan.executable = ExecutablePlan(type="sql", dialect="sqlite", content="")

    if result.selected_sql:
        plan.executable.content = result.selected_sql
        metadata.pop("requires_replan", None)
        metadata.pop("replan_reason", None)
        return

    plan.executable.content = ""
    metadata["requires_replan"] = True
    metadata["replan_reason"] = (
        result.error_message
        or "The KDDCup agent did not execute SQL for this query, so DebugSQL cannot re-execute it."
    )


def _kddcup_trace_content(result: NL2IRResult, sql: str, graph: dict[str, Any]) -> str:
    step_count = len((result.trace or {}).get("steps") or [])
    if result.selected_sql:
        return (
            "I generated IR from the KDDCup data-agent trace and extracted executable SQL.\n\n"
            f"```sql\n{sql}\n```\n\n"
            f"The trace contains **{step_count}** agent step(s), and the plan can now be inspected, "
            f"edited, and executed. Total cost: **{graph['totalCost']:.1f}**."
        )

    reason = result.error_message or "No executable SQL was found in the agent trace."
    return (
        "I generated an inspectable IR from the KDDCup data-agent trace, but there is no executable SQL yet.\n\n"
        f"Reason: {reason}\n\n"
        "The trace can still be inspected in the Query Plan, but re-execution requires a SQL-producing "
        "agent step."
    )


def _benchmark_query_content(
    sql: str,
    graph: dict[str, Any],
    benchmark: str | None = None,
) -> str:
    label = (benchmark or "benchmark").upper()
    return (
        f"I matched this question to a {label} dev example and generated an executable plan.\n\n"
        f"```sql\n{sql}\n```\n\n"
        f"The plan can be inspected and executed against the selected SQLite database. Total cost: **{graph['totalCost']:.1f}**."
    )


def _schema_fallback_content(
    fallback: Any,
    sql: str,
    graph: dict[str, Any],
) -> str:
    return (
        "I generated a demo schema-aware NL2SQL plan for this question.\n\n"
        f"```sql\n{sql}\n```\n\n"
        f"{fallback.explanation} This fallback is intentionally simple; complex joins, nested SQL, "
        "and domain reasoning still require the real NL2SQL provider. "
        f"Total cost: **{graph['totalCost']:.1f}**."
    )


def _replan_required_execution_result(plan_id: str | None) -> dict[str, Any]:
    stored = PLAN_STORE.get(plan_id or "", {})
    metadata = stored.get("plan", {}).get("metadata", {})
    reason = metadata.get("replan_reason") or "The edited node changes query semantics."
    return {
        "sql": "",
        "columns": [
            {"key": "status", "label": "status"},
            {"key": "message", "label": "message"},
        ],
        "rows": [
            {
                "status": "needs_replan",
                "message": (
                    f"{reason} A real NL2IR/IR2Plan provider is required to regenerate this "
                    "benchmark plan safely."
                ),
            }
        ],
        "metrics": {
            "planningTimeMs": 0,
            "executionTimeMs": 0,
            "rowCount": 1,
            "estimatedRows": 0,
        },
    }


def _intent_node(
    node_id: str,
    x: int,
    y: int,
    label: str,
    aggregation: str,
    filters: list[str],
    group_by: list[str],
    target_columns: list[str],
) -> dict[str, Any]:
    return {
        "id": node_id,
        "type": "intent",
        "position": {"x": x, "y": y},
        "data": {
            "kind": "intent",
            "intentLabel": label,
            "aggregation": aggregation,
            "filters": filters,
            "groupBy": group_by,
            "targetColumns": target_columns,
        },
    }


def _op_node(
    node_id: str,
    x: int,
    y: int,
    operation_type: str,
    label: str,
    detail: str,
    rows: int,
    cost: float,
) -> dict[str, Any]:
    return {
        "id": node_id,
        "type": "operation",
        "position": {"x": x, "y": y},
        "data": {
            "kind": "operation",
            "operationType": operation_type,
            "label": label,
            "detail": detail,
            "estimatedRows": rows,
            "cost": cost,
            "executionState": "pending",
        },
    }


def _data_node(
    node_id: str,
    x: int,
    y: int,
    table_name: str,
    role: str,
    rows: int,
    cost: float,
    columns: list[str],
) -> dict[str, Any]:
    return {
        "id": node_id,
        "type": "data",
        "position": {"x": x, "y": y},
        "data": {
            "kind": "data",
            "tableName": table_name,
            "nodeRole": role,
            "rowCount": rows,
            "estimatedCost": cost,
            "columns": columns,
        },
    }


def _edge(source: str, target: str, animated: bool = False) -> dict[str, Any]:
    return {
        "id": f"{source}-{target}",
        "source": source,
        "target": target,
        "animated": animated,
    }


def _flow_node_data(node: PlanNode) -> dict[str, Any]:
    payload = node.payload
    if node.node_type == "intent":
        return {
            "kind": "intent",
            "intentLabel": payload.get("intent_type", "Query Intent"),
            "aggregation": payload.get("aggregation"),
            "filters": [json.dumps(item) for item in payload.get("filters", [])],
            "groupBy": payload.get("group_by", []),
            "targetColumns": payload.get("target_columns", []),
        }

    if node.node_type == "data":
        return {
            "kind": "data",
            "tableName": node.label,
            "nodeRole": "result" if "result" in node.node_id else "source",
            "rowCount": 0 if "result" in node.node_id else 1200,
            "estimatedCost": 3.2,
            "columns": payload.get("columns", []),
        }

    return {
        "kind": "operation",
        "operationType": _operation_type(node.operation_type),
        "label": node.label,
        "detail": _operation_detail(node),
        "estimatedRows": 1200,
        "cost": 12.5,
        "executionState": "pending",
    }


def _operation_type(operation_type: str | None) -> str:
    mapping = {
        "scan": "SCAN",
        "filter": "FILTER",
        "group_by": "GROUP_BY",
        "join": "JOIN",
        "sort": "SORT",
        "aggregate": "AGGREGATE",
        "limit": "LIMIT",
        "tool": "TOOL",
        "execute_sql": "SQL",
        "answer": "ANSWER",
    }
    return mapping.get(operation_type or "", "SELECT")


def _operation_detail(node: PlanNode) -> str:
    payload = node.payload
    if node.operation_type == "scan":
        return f"table = {payload.get('table')}"
    if node.operation_type == "aggregate":
        return f"{payload.get('function')}({', '.join(payload.get('columns', []))})"
    if node.operation_type == "group_by":
        return ", ".join(payload.get("columns", []))
    if payload.get("op"):
        return str(payload.get("thought") or payload.get("op") or "")
    return json.dumps(payload, default=str)


def _node_levels(plan: QueryPlan) -> dict[str, int]:
    levels = {plan.nodes[0].node_id: 0} if plan.nodes else {}
    changed = True
    while changed:
        changed = False
        for edge in plan.edges:
            if edge.source in levels:
                next_level = levels[edge.source] + 1
                if levels.get(edge.target, -1) < next_level:
                    levels[edge.target] = next_level
                    changed = True
    return levels


def _execution_sql(sql_or_query: str, plan_id: str | None) -> str:
    if not plan_id and PLAN_STORE:
        plan_id = max(PLAN_STORE.items(), key=lambda item: item[1].get("created_at", 0))[0]

    if plan_id and plan_id not in PLAN_STORE:
        _restore_plan_from_database(plan_id)

    if plan_id and plan_id in PLAN_STORE:
        executable = PLAN_STORE[plan_id]["plan"].get("executable") or {}
        if executable.get("content"):
            return executable["content"]
    if sql_or_query.strip().lower().startswith("select"):
        return sql_or_query
    return "SELECT dimension, value FROM debugsql_stub_result ORDER BY value DESC"


def _apply_node_edit_to_executable(plan_id: str, node_id: str) -> dict[str, Any]:
    stored = PLAN_STORE.get(plan_id)
    if not stored:
        return {"status": "missing_plan", "message": "Plan was not found."}

    metadata = stored.get("plan", {}).setdefault("metadata", {})
    metadata.pop("requires_replan", None)
    metadata.pop("replan_reason", None)

    graph = stored.get("graph") or {}
    node = _graph_node(graph, node_id)
    if node and (node.get("data") or {}).get("kind") == "data":
        return {
            "status": "graph_updated",
            "message": "Data-node display metadata was updated without changing SQL.",
            "executableAvailable": bool((stored.get("plan", {}).get("executable") or {}).get("content")),
        }

    template = metadata.get("template")
    if template == "sales_store_ranking":
        _sync_executable_from_graph(plan_id)
        return {
            "status": "regenerated",
            "message": "Sales demo SQL was regenerated from edited plan nodes.",
            "executableAvailable": True,
        }

    if template == "benchmark_gold_sql":
        patch_result = _apply_supported_benchmark_sql_patch(plan_id, node_id)
        if patch_result["status"] in {"regenerated", "graph_updated"}:
            return patch_result

        metadata["requires_replan"] = True
        metadata["replan_reason"] = patch_result["message"]
        executable = stored.get("plan", {}).setdefault("executable", {})
        executable["content"] = ""
        return {
            **patch_result,
            "executableAvailable": False,
            "requiresProvider": True,
        }

    if template == "gemini":
        return _apply_gemini_node_edit(stored, node)

    return {
        "status": "graph_updated",
        "message": "Node payload was saved. This plan type does not require SQL regeneration.",
        "executableAvailable": bool((stored.get("plan", {}).get("executable") or {}).get("content")),
    }


def _apply_gemini_node_edit(stored: dict[str, Any], node: dict[str, Any] | None) -> dict[str, Any]:
    data = (node or {}).get("data") or {}
    operation_type = str(data.get("operationType") or "").upper()
    if operation_type == "SQL":
        sql = str(data.get("fragmentSql") or data.get("detail") or "").strip()
        if sql:
            executable = stored.get("plan", {}).setdefault("executable", {})
            executable["content"] = sql
            data["fragmentSql"] = sql
            data["detail"] = sql
            node["data"] = data
            return {
                "status": "regenerated",
                "message": "Gemini SQL was updated from the edited SQL node.",
                "executableAvailable": True,
            }
        return {
            "status": "needs_replan",
            "message": "The SQL node does not contain executable SQL.",
            "executableAvailable": False,
        }

    return {
        "status": "graph_updated",
        "message": "Plan step metadata was updated.",
        "executableAvailable": bool((stored.get("plan", {}).get("executable") or {}).get("content")),
    }


def _apply_supported_benchmark_sql_patch(plan_id: str, node_id: str) -> dict[str, Any]:
    stored = PLAN_STORE[plan_id]
    graph = stored["graph"]
    node = _graph_node(graph, node_id)
    if not node:
        return {"status": "missing_node", "message": "Edited node was not found."}

    data = node.get("data", {})
    if data.get("kind") == "data":
        return {
            "status": "graph_updated",
            "message": "Data-node display metadata was updated without changing SQL.",
            "executableAvailable": True,
        }

    executable = stored.get("plan", {}).get("executable") or {}
    sql = executable.get("content") or ""
    if not sql:
        return {"status": "needs_replan", "message": "No executable SQL is available to patch."}

    operation_type = str(data.get("operationType") or "").upper()
    if operation_type == "LIMIT":
        limit = _extract_limit(str(data.get("detail") or data.get("label") or ""))
        if limit is None:
            return {"status": "needs_replan", "message": "The edited LIMIT node does not contain a valid integer limit."}
        executable["content"] = _replace_sql_limit(sql, limit)
        return {
            "status": "regenerated",
            "message": f"Benchmark SQL LIMIT was regenerated as LIMIT {limit}.",
            "executableAvailable": True,
        }

    if operation_type == "SORT":
        order_by = str(data.get("detail") or "").strip()
        if not order_by:
            return {"status": "needs_replan", "message": "The edited SORT node does not contain an ORDER BY expression."}
        executable["content"] = _replace_sql_order_by(sql, order_by)
        return {
            "status": "regenerated",
            "message": f"Benchmark SQL ORDER BY was regenerated as {order_by}.",
            "executableAvailable": True,
        }

    return {
        "status": "needs_replan",
        "message": (
            "This benchmark node edit changes semantics that cannot be safely regenerated "
            "without the external NL2IR/IR2Plan provider."
        ),
    }


def _record_plan_edit(
    plan_id: str,
    node_id: str,
    old_data: dict[str, Any] | None,
    new_data: dict[str, Any],
    edit_result: dict[str, Any],
) -> None:
    stored = PLAN_STORE.get(plan_id)
    if not stored:
        return
    stored.setdefault("edit_log", []).append(
        {
            "node_id": node_id,
            "old_data": old_data,
            "new_data": new_data,
            "result": edit_result,
            "created_at": time.time(),
        }
    )


def _persist_latest_plan_edit(plan_id: str, user_id: str | None = None) -> None:
    stored = PLAN_STORE.get(plan_id)
    edits = (stored or {}).get("edit_log") or []
    if not edits:
        return
    try:
        from app.persistence import persist_plan_edit, persist_query_plan

        persist_plan_edit(plan_id, edits[-1], user_id=user_id)
        persist_query_plan(plan_id, (stored or {}).get("session_id"), user_id=user_id)
    except Exception as exc:  # pragma: no cover - defensive audit path.
        print(f"[persistence] plan edit skipped: {exc}")


def _persist_execution(
    run_id: str,
    plan_id: str | None,
    session_id: str | None,
    run_type: str,
    status: str,
    sql: str | None,
    result: dict[str, Any] | None,
    node_states: dict[str, Any] | None = None,
    error_message: str | None = None,
    node_previews: dict[str, Any] | None = None,
    user_id: str | None = None,
) -> None:
    try:
        from app.persistence import persist_execution_run

        persist_execution_run(
            run_id=run_id,
            plan_id=plan_id,
            session_id=session_id,
            run_type=run_type,
            status=status,
            sql=sql,
            result=result,
            node_states=node_states,
            node_previews=node_previews,
            error_message=error_message,
            user_id=user_id,
        )
    except Exception as exc:  # pragma: no cover - defensive audit path.
        print(f"[persistence] execution skipped: {exc}")


def _mark_downstream_pending(graph: dict[str, Any], node_id: str) -> set[str]:
    downstream = _downstream_node_ids(graph, node_id)
    _clear_graph_previews(graph, downstream | {node_id})
    for node in graph.get("nodes", []):
        data = node.get("data", {})
        if node.get("id") in downstream and data.get("kind") == "operation":
            data["executionState"] = "pending"
        if node.get("id") in downstream and data.get("kind") == "data":
            data["materialized"] = False
            data["executionState"] = "pending"
    return downstream


def _clear_graph_previews(graph: dict[str, Any], node_ids: set[str]) -> None:
    preview_keys = {
        "fragmentSql",
        "previewColumns",
        "previewMessage",
        "previewRowCount",
        "previewRows",
        "previewStatus",
    }
    for node in graph.get("nodes", []):
        if node.get("id") not in node_ids:
            continue
        data = node.setdefault("data", {})
        for key in preview_keys:
            if (
                key == "fragmentSql"
                and data.get("kind") == "operation"
                and str(data.get("operationType") or "").upper() == "SQL"
            ):
                continue
            data.pop(key, None)


def _clear_plan_run_state(plan_id: str, graph: dict[str, Any]) -> None:
    graph.pop("runStatus", None)
    for run_id, run in list(PLAN_RUN_STORE.items()):
        if run.get("planId") == plan_id:
            PLAN_RUN_STORE.pop(run_id, None)
    for node in graph.get("nodes", []):
        data = node.setdefault("data", {})
        data.pop("_runId", None)


def _downstream_node_ids(graph: dict[str, Any], node_id: str) -> set[str]:
    adjacency: dict[str, list[str]] = {}
    for edge in graph.get("edges", []):
        adjacency.setdefault(edge.get("source"), []).append(edge.get("target"))

    seen: set[str] = set()
    stack = list(adjacency.get(node_id, []))
    while stack:
        current = stack.pop()
        if current in seen:
            continue
        seen.add(current)
        stack.extend(adjacency.get(current, []))
    return seen


def _plan_node_order(graph: dict[str, Any]) -> list[str]:
    nodes = [node.get("id") for node in graph.get("nodes", []) if node.get("id")]
    if not nodes:
        return []

    adjacency: dict[str, list[str]] = {node_id: [] for node_id in nodes}
    indegree: dict[str, int] = {node_id: 0 for node_id in nodes}
    for edge in graph.get("edges", []):
        source = edge.get("source")
        target = edge.get("target")
        if source in adjacency and target in indegree:
            adjacency[source].append(target)
            indegree[target] += 1

    queue = [node_id for node_id in nodes if indegree[node_id] == 0]
    ordered: list[str] = []
    while queue:
        current = queue.pop(0)
        ordered.append(current)
        for target in adjacency.get(current, []):
            indegree[target] -= 1
            if indegree[target] == 0:
                queue.append(target)

    return ordered if len(ordered) == len(nodes) else nodes


def _apply_plan_run_to_graph(plan_id: str, run: dict[str, Any]) -> None:
    stored = PLAN_STORE.get(plan_id)
    if not stored:
        return
    graph = stored["graph"]
    graph["runStatus"] = {
        "runId": run["runId"],
        "status": run["status"],
        "currentNodeId": run.get("currentNodeId"),
        "nextNodeId": run.get("nextNodeId"),
        "stepsCompleted": run["stepsCompleted"],
        "totalSteps": run["totalSteps"],
    }
    for node in graph.get("nodes", []):
        node_id = node.get("id")
        data = node.setdefault("data", {})
        if node_id in run.get("nodeStates", {}):
            data["executionState"] = run["nodeStates"][node_id]
            data["_runId"] = run["runId"]
            preview = (run.get("nodePreviews") or {}).get(node_id)
            if preview:
                data["previewStatus"] = preview.get("status")
                data["previewMessage"] = preview.get("message")
                data["fragmentSql"] = preview.get("fragmentSql")
                data["previewRows"] = preview.get("rows", [])
                data["previewColumns"] = preview.get("columns", [])
                data["previewRowCount"] = preview.get("rowCount", len(preview.get("rows", [])))
            if data.get("kind") == "data":
                data["materialized"] = run["nodeStates"][node_id] == "success"


def _public_plan_run(run: dict[str, Any]) -> dict[str, Any]:
    return {
        "runId": run["runId"],
        "planId": run["planId"],
        "status": run["status"],
        "currentNodeId": run.get("currentNodeId"),
        "nextNodeId": run.get("nextNodeId"),
        "nodeStates": run.get("nodeStates", {}),
        "stepsCompleted": run["stepsCompleted"],
        "totalSteps": run["totalSteps"],
        "resultRunId": run.get("resultRunId"),
        "result": run.get("result"),
        "nodePreviews": run.get("nodePreviews", {}),
        "error": run.get("error"),
    }


def _node_step_preview(plan_id: str, node_id: str) -> dict[str, Any]:
    stored = get_plan_record(plan_id)
    graph = (stored or {}).get("graph") or {}
    node = _graph_node(graph, node_id)
    data = (node or {}).get("data") or {}
    kind = data.get("kind")

    if kind == "data":
        columns = [{"key": column, "label": column} for column in data.get("columns", [])]
        role = data.get("nodeRole")
        if role == "source":
            return _execute_node_fragment(stored, _scan_fragment(str(data.get("tableName") or "")), metadata_columns=columns)
        return {
            "status": "not_materializable",
            "message": "Result rows will be materialized when the final SQL step completes.",
            "columns": columns,
            "rows": [],
            "rowCount": 0,
        }

    if kind == "operation":
        return _execute_node_fragment(stored, _operation_fragment(stored, data))

    return {
        "status": "metadata_only",
        "message": "Intent node inspected; no data is materialized at this step.",
        "columns": [],
        "rows": [],
        "rowCount": 0,
    }


def _result_step_preview(result: dict[str, Any] | None) -> dict[str, Any]:
    if not result:
        return {
            "status": "not_materializable",
            "message": "No execution result is available for this data node.",
            "columns": [],
            "rows": [],
            "rowCount": 0,
        }
    rows = result.get("rows") or []
    if _result_has_error(result):
        message = str((rows[0] if rows else {}).get("message") or (rows[0] if rows else {}).get("error") or "Execution failed.")
        return {
            "status": "error",
            "message": message,
            "errorMessage": message,
            "fragmentSql": result.get("sql") or "",
            "columns": result.get("columns") or [],
            "rows": rows[:20],
            "rowCount": len(rows),
        }
    return {
        "status": "materialized",
        "message": "Final SQL result materialized for this data node.",
        "fragmentSql": result.get("sql") or "",
        "columns": result.get("columns") or [],
        "rows": rows[:20],
        "rowCount": len(rows),
    }


def _operation_fragment(stored: dict[str, Any] | None, data: dict[str, Any]) -> str | None:
    if not stored:
        return None
    sql = str((((stored.get("plan") or {}).get("executable") or {}).get("content") or "")).strip()
    operation_type = str(data.get("operationType") or "").upper()
    table = _fragment_table(stored, sql, data)

    if operation_type in {"SCAN", "SELECT"}:
        return _scan_fragment(table)
    if operation_type == "FILTER":
        where_clause = _extract_sql_section(sql, "where", ("group by", "order by", "limit"))
        scan = _scan_fragment(table, include_limit=False)
        return f"{scan}\nWHERE {where_clause}\nLIMIT 20" if scan and where_clause else None
    if operation_type in {"GROUP_BY", "AGGREGATE"}:
        return _preview_limit(_strip_sql_suffix(sql, ("order by", "limit"))) if "group by" in sql.lower() else None
    if operation_type == "SORT":
        return _preview_limit(_strip_sql_suffix(sql, ("limit",))) if re.search(r"\border\s+by\b", sql, re.IGNORECASE) else None
    if operation_type == "LIMIT":
        limit = _extract_limit(str(data.get("detail") or "")) or _extract_limit(sql)
        return _replace_sql_limit(sql, limit).rstrip(";") if limit is not None and sql else None
    if operation_type == "SQL":
        return sql or None
    return None


def _execute_node_fragment(
    stored: dict[str, Any] | None,
    fragment_sql: str | None,
    *,
    metadata_columns: list[dict[str, str]] | None = None,
) -> dict[str, Any]:
    if not fragment_sql:
        return {
            "status": "not_materializable",
            "message": "This node cannot be safely represented as an executable SQL preview.",
            "fragmentSql": None,
            "columns": metadata_columns or [],
            "rows": [],
            "rowCount": 0,
        }
    context = (stored or {}).get("dataset_context") or ((stored or {}).get("plan") or {}).get("metadata", {}).get("dataset_context")
    benchmark = (context or {}).get("benchmark")
    db_id = (context or {}).get("dbId")
    if benchmark not in SQLITE_ROOTS or not db_id:
        return {
            "status": "not_materializable",
            "message": "No resolvable read-only SQLite database is attached to this node.",
            "fragmentSql": fragment_sql,
            "columns": metadata_columns or [],
            "rows": [],
            "rowCount": 0,
        }
    preview = _result_step_preview(execute_benchmark_sql(benchmark, db_id, fragment_sql))
    if preview["status"] == "materialized":
        preview["message"] = f"Materialized preview from {len(preview.get('rows') or [])} row(s)."
    return preview


def _fragment_table(stored: dict[str, Any], sql: str, data: dict[str, Any]) -> str | None:
    detail_match = re.search(r"\btable\s*=\s*(.+)$", str(data.get("detail") or ""), flags=re.IGNORECASE)
    candidate = detail_match.group(1).strip() if detail_match else None
    candidate = candidate or str((stored.get("ir") or {}).get("table") or "").strip()
    if not candidate:
        from_match = re.search(r"\bfrom\s+((?:\"[^\"]+\"|`[^`]+`|\[[^\]]+\]|[\w.]+))", sql, flags=re.IGNORECASE)
        candidate = from_match.group(1) if from_match else ""
    return candidate if _safe_table_reference(candidate) else None


def _safe_table_reference(table: str | None) -> bool:
    if not table:
        return False
    identifier = r'(?:[\w]+|"[^"]+"|`[^`]+`|\[[^\]]+\])'
    return bool(re.fullmatch(rf"{identifier}(?:\.{identifier})?", table))


def _scan_fragment(table: str | None, *, include_limit: bool = True) -> str | None:
    if not _safe_table_reference(table):
        return None
    return f"SELECT * FROM {table}" + ("\nLIMIT 20" if include_limit else "")


def _extract_sql_section(sql: str, start: str, endings: tuple[str, ...]) -> str | None:
    ending_pattern = "|".join(rf"\b{re.escape(item)}\b" for item in endings)
    match = re.search(rf"\b{re.escape(start)}\b\s+(.+?)(?={ending_pattern}|$)", sql.rstrip(";"), flags=re.IGNORECASE | re.DOTALL)
    return match.group(1).strip() if match else None


def _strip_sql_suffix(sql: str, clauses: tuple[str, ...]) -> str:
    stripped = sql.strip().rstrip(";")
    starts = [
        match.start()
        for clause in clauses
        if (match := re.search(rf"\b{re.escape(clause)}\b", stripped, flags=re.IGNORECASE))
    ]
    return stripped[: min(starts)].rstrip() if starts else stripped


def _preview_limit(sql: str) -> str:
    return f"{sql.rstrip(';')}\nLIMIT 20"


def _result_has_error(result: dict[str, Any] | None) -> bool:
    return any(isinstance(row, dict) and row.get("error") for row in ((result or {}).get("rows") or []))


def _apply_execution_result_to_result_nodes(
    plan_id: str | None,
    result: dict[str, Any] | None,
    *,
    persist: bool = True,
) -> None:
    if not plan_id or not result:
        return
    stored = get_plan_record(plan_id)
    if not stored:
        return
    graph = stored.get("graph") or {}
    preview = _result_step_preview(result)
    for node in graph.get("nodes", []):
        data = node.setdefault("data", {})
        if data.get("kind") != "data" or data.get("nodeRole") != "result":
            continue
        data["materialized"] = preview["status"] == "materialized"
        data["executionState"] = "error" if preview["status"] == "error" else "success"
        data["previewStatus"] = preview["status"]
        data["previewMessage"] = preview["message"]
        data["fragmentSql"] = preview.get("fragmentSql")
        data["previewRows"] = preview["rows"]
        data["previewColumns"] = preview["columns"]
        data["previewRowCount"] = preview["rowCount"]
        data["rowCount"] = preview["rowCount"]
        labels = [
            str(column.get("label") or column.get("key"))
            for column in preview["columns"]
            if isinstance(column, dict) and (column.get("label") or column.get("key"))
        ]
        if labels:
            data["columns"] = labels
    if not persist:
        return
    try:
        from app.persistence import persist_query_plan

        persist_query_plan(plan_id, stored.get("session_id"), user_id=stored.get("user_id"))
    except Exception as exc:  # pragma: no cover - defensive preview persistence.
        print(f"[persistence] result-node preview skipped: {exc}")


def _graph_node(graph: dict[str, Any], node_id: str) -> dict[str, Any] | None:
    for node in graph.get("nodes", []):
        if node.get("id") == node_id:
            return node
    return None


def _nodes_form_adjacent_path(graph: dict[str, Any], ordered_node_ids: list[str]) -> bool:
    edges = {(edge.get("source"), edge.get("target")) for edge in graph.get("edges", [])}
    return all((source, target) in edges for source, target in zip(ordered_node_ids, ordered_node_ids[1:]))


def _merge_supported(operation_types: list[str]) -> bool:
    compact = [item for item in operation_types if item]
    supported_pairs = {
        ("SELECT", "FILTER"),
        ("FILTER", "JOIN"),
        ("JOIN", "GROUP_BY"),
        ("GROUP_BY", "AGGREGATE"),
        ("SORT", "LIMIT"),
        ("AGGREGATE", "SORT"),
    }
    return all((source, target) in supported_pairs for source, target in zip(compact, compact[1:]))


def _rewire_merged_edges(
    edges: list[dict[str, Any]],
    target_id: str,
    removed: set[str],
) -> list[dict[str, Any]]:
    rewired: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for edge in edges:
        source = target_id if edge.get("source") in removed else edge.get("source")
        target = target_id if edge.get("target") in removed else edge.get("target")
        if not source or not target or source == target:
            continue
        key = (source, target)
        if key in seen:
            continue
        seen.add(key)
        rewired.append({**edge, "id": f"{source}-{target}", "source": source, "target": target})
    return rewired


def _merge_result(
    status: str,
    message: str,
    node_ids: list[str],
    downstream: set[str] | None = None,
) -> dict[str, Any]:
    needs_replan = status == "needs_replan"
    return {
        "status": status,
        "message": message,
        "needsReplan": needs_replan,
        "executableAvailable": not needs_replan,
        "editedNodeId": node_ids[0] if node_ids else None,
        "downstreamNodeIds": sorted(downstream or set()),
        "mergedNodeIds": node_ids,
        "operationType": "plan_node_merge",
    }


def _replace_sql_limit(sql: str, limit: int) -> str:
    stripped = sql.strip().rstrip(";")
    if re.search(r"\bLIMIT\s+\d+\b", stripped, flags=re.IGNORECASE):
        patched = re.sub(r"\bLIMIT\s+\d+\b", f"LIMIT {limit}", stripped, flags=re.IGNORECASE)
    else:
        patched = f"{stripped}\nLIMIT {limit}"
    return f"{patched};"


def _replace_sql_order_by(sql: str, order_by: str) -> str:
    stripped = sql.strip().rstrip(";")
    limit_match = re.search(r"\bLIMIT\s+\d+\b", stripped, flags=re.IGNORECASE)
    limit_clause = ""
    body = stripped
    if limit_match:
        limit_clause = limit_match.group(0)
        body = stripped[: limit_match.start()].rstrip()

    if re.search(r"\bORDER\s+BY\b", body, flags=re.IGNORECASE):
        body = re.sub(r"\bORDER\s+BY\b.+$", f"ORDER BY {order_by}", body, flags=re.IGNORECASE | re.DOTALL)
    else:
        body = f"{body}\nORDER BY {order_by}"

    if limit_clause:
        body = f"{body}\n{limit_clause}"
    return f"{body};"


def _sync_executable_from_graph(plan_id: str) -> None:
    stored = PLAN_STORE.get(plan_id)
    if not stored:
        return

    metadata = stored.get("plan", {}).get("metadata", {})
    if metadata.get("template") != "sales_store_ranking":
        return

    graph = stored["graph"]
    filter_detail = (
        _node_detail(graph, "op_filter")
        or _node_detail(graph, "intent")
        or "sales_date >= CURRENT_DATE - 30"
    )
    group_by = _node_detail(graph, "op_group_by") or "store_id, store_name"
    aggregate = _node_detail(graph, "op_aggregate") or "SUM(amount) AS total_sales"
    sort = _node_detail(graph, "op_sort") or "total_sales DESC"
    limit = _node_detail(graph, "op_limit") or "LIMIT 10"

    stored["plan"]["executable"]["content"] = _sales_store_sql(
        filter_detail=filter_detail,
        group_by=group_by,
        aggregate=aggregate,
        sort=sort,
        limit=limit,
    )


def _node_detail(graph: dict[str, Any], node_id: str) -> str | None:
    for node in graph.get("nodes", []):
        if node.get("id") == node_id:
            data = node.get("data", {})
            if data.get("detail"):
                return str(data["detail"])
            if node_id == "intent" and data.get("filters"):
                return str(data["filters"][0])
    return None


def _sales_store_sql(
    filter_detail: str,
    group_by: str,
    aggregate: str,
    sort: str,
    limit: str,
) -> str:
    limit_clause = limit if limit.strip().upper().startswith("LIMIT") else f"LIMIT {limit}"
    aggregate_expr = aggregate if " AS " in aggregate.upper() else f"{aggregate} AS total_sales"
    return (
        "SELECT\n"
        "  s.store_id,\n"
        "  s.store_name,\n"
        f"  {aggregate_expr}\n"
        "FROM sales_transactions t\n"
        "JOIN stores s ON t.store_id = s.store_id\n"
        f"WHERE {filter_detail}\n"
        f"GROUP BY {group_by}\n"
        f"ORDER BY {sort}\n"
        f"{limit_clause};"
    )


def _execution_rows(sql: str) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    limit = _extract_limit(sql)
    if "total_sales" in sql or "sales_transactions" in sql:
        columns = [
            {"key": "store_id", "label": "store_id"},
            {"key": "store_name", "label": "store_name"},
            {"key": "total_sales", "label": "total_sales"},
        ]
        rows = [
            {"store_id": "S-104", "store_name": "North Market", "total_sales": 12840},
            {"store_id": "S-087", "store_name": "South Plaza", "total_sales": 11720},
            {"store_id": "S-022", "store_name": "West End", "total_sales": 10895},
            {"store_id": "S-145", "store_name": "East Point", "total_sales": 9850},
        ]
        return _apply_limit(rows, limit), columns

    columns = [
        {"key": "dimension", "label": "dimension"},
        {"key": "value", "label": "value"},
    ]
    rows = [
        {"dimension": "North", "value": 12840},
        {"dimension": "South", "value": 11720},
        {"dimension": "West", "value": 10895},
        {"dimension": "East", "value": 9850},
    ]
    return _apply_limit(rows, limit), columns


def _extract_limit(sql: str) -> int | None:
    plain = sql.strip()
    if plain.isdigit():
        return int(plain)
    match = re.search(r"\bLIMIT\s+(\d+)\b", sql, flags=re.IGNORECASE)
    if not match:
        return None
    limit = int(match.group(1))
    return limit if limit >= 0 else None


def _apply_limit(rows: list[dict[str, Any]], limit: int | None) -> list[dict[str, Any]]:
    if limit is None:
        return rows
    return rows[:limit]


def _stable_id(prefix: str, payload: dict[str, Any]) -> str:
    digest = hashlib.sha1(json.dumps(payload, sort_keys=True, default=str).encode("utf-8")).hexdigest()[:10]
    return f"{prefix}_{digest}"
