from __future__ import annotations

import hashlib
import json
import re
import time
from typing import Any

from app.benchmark_registry import (
    SQLITE_ROOTS,
    execute_benchmark_sql,
    find_benchmark_gold_sql,
    get_schema_context,
)
from app.planning.provider import get_ir_to_plan_provider
from app.planning.schemas import PlanNode, PlanningRequest, QueryPlan


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

    gold_sql = find_benchmark_gold_sql(benchmark, db_id, message) if benchmark in SQLITE_ROOTS else None
    if benchmark in SQLITE_ROOTS and db_id and not gold_sql:
        raise ValueError("No benchmark gold SQL found for this question.")

    intent_ir = build_demo_ir(message)
    if dataset_context:
        intent_ir["dataset_context"] = dataset_context

    schema_context = get_schema_context(benchmark, db_id) or {
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
    if gold_sql and plan.executable:
        plan.executable.content = gold_sql
        plan.metadata["template"] = "benchmark_gold_sql"
    graph = query_plan_to_graph(plan, message)
    assistant_content = (
        _benchmark_query_content(
            plan.executable.content,
            graph,
            (dataset_context or {}).get("benchmark"),
        )
        if gold_sql and plan.executable
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
            break
    else:
        return None

    downstream = _mark_downstream_pending(graph, node_id)
    edit_result = _apply_node_edit_to_executable(plan_id, node_id)
    edit_result["downstreamNodeIds"] = sorted(downstream)
    edit_result["needsReplan"] = edit_result.get("status") == "needs_replan" or not edit_result.get("executableAvailable", True)
    edit_result["operationType"] = "plan_edit_replan"
    _record_plan_edit(plan_id, node_id, old_data, data, edit_result)
    _persist_latest_plan_edit(plan_id, user_id=user_id)
    graph["editStatus"] = edit_result
    graph["lastEditResult"] = edit_result
    graph["needsReplan"] = bool(edit_result["needsReplan"])
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
    run["status"] = "running"
    run["currentNodeId"] = node_id
    run["nextNodeId"] = order[index + 1] if index + 1 < len(order) else None
    run["nodeStates"][node_id] = "running"
    _apply_plan_run_to_graph(plan_id, run)

    try:
        if index == len(order) - 1:
            execution = run_demo_execution("step-plan-run", "dev-session", plan_id, user_id=user_id or run.get("userId"))
            result = get_execution_result(execution["runId"], user_id=user_id or run.get("userId"))
            run["resultRunId"] = execution["runId"]
            run["result"] = result
        run["nodeStates"][node_id] = "success"
        run["stepsCompleted"] = index + 1
        run["status"] = "success" if run["stepsCompleted"] >= len(order) else "running"
        run["currentNodeId"] = node_id
        run["nextNodeId"] = order[run["stepsCompleted"]] if run["stepsCompleted"] < len(order) else None
    except Exception as exc:  # pragma: no cover - defensive state capture for API callers.
        run["nodeStates"][node_id] = "error"
        run["status"] = "error"
        run["error"] = str(exc)

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
    run["stepsCompleted"] = 0
    run["resultRunId"] = None
    run["result"] = None
    run.pop("error", None)
    run["updatedAt"] = time.time()
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
        "scan": "SELECT",
        "filter": "FILTER",
        "group_by": "GROUP_BY",
        "join": "JOIN",
        "sort": "SORT",
        "aggregate": "AGGREGATE",
        "limit": "LIMIT",
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

    return {
        "status": "graph_updated",
        "message": "Node payload was saved. This plan type does not require SQL regeneration.",
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
            error_message=error_message,
            user_id=user_id,
        )
    except Exception as exc:  # pragma: no cover - defensive audit path.
        print(f"[persistence] execution skipped: {exc}")


def _mark_downstream_pending(graph: dict[str, Any], node_id: str) -> set[str]:
    downstream = _downstream_node_ids(graph, node_id)
    for node in graph.get("nodes", []):
        data = node.get("data", {})
        if node.get("id") in downstream and data.get("kind") == "operation":
            data["executionState"] = "pending"
        if node.get("id") in downstream and data.get("kind") == "data":
            data["materialized"] = False
    return downstream


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
        "error": run.get("error"),
    }


def _graph_node(graph: dict[str, Any], node_id: str) -> dict[str, Any] | None:
    for node in graph.get("nodes", []):
        if node.get("id") == node_id:
            return node
    return None


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
        _node_detail(graph, "intent")
        or _node_detail(graph, "op_filter")
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
