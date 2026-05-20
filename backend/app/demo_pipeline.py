from __future__ import annotations

import hashlib
import json
import time
from typing import Any

from app.planning.provider import get_ir_to_plan_provider
from app.planning.schemas import PlanNode, PlanningRequest, QueryPlan


PLAN_STORE: dict[str, dict[str, Any]] = {}
RUN_STORE: dict[str, dict[str, Any]] = {}


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


def generate_plan_for_message(message: str, session_id: str | None = None) -> dict[str, Any]:
    intent_ir = build_demo_ir(message)
    schema_context = {
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
    graph = query_plan_to_graph(plan, message)

    PLAN_STORE[plan.plan_id] = {
        "message": message,
        "session_id": session_id,
        "ir": intent_ir,
        "plan": plan.model_dump(),
        "graph": graph,
        "created_at": time.time(),
    }
    return PLAN_STORE[plan.plan_id]


def get_plan_graph(plan_id: str) -> dict[str, Any] | None:
    stored = PLAN_STORE.get(plan_id)
    if not stored:
        return None
    return stored["graph"]


def update_plan_node(plan_id: str, node_id: str, data: dict[str, Any]) -> dict[str, Any] | None:
    graph = get_plan_graph(plan_id)
    if not graph:
        return None

    for node in graph["nodes"]:
        if node["id"] == node_id:
            node["data"] = data
            node["data"]["_lastEditedAt"] = int(time.time())
            break
    return graph


def run_demo_execution(sql_or_query: str, session_id: str | None = None, plan_id: str | None = None) -> dict[str, Any]:
    run_id = _stable_id("run", {"sql": sql_or_query, "session": session_id, "plan": plan_id, "time": time.time()})
    sql = _execution_sql(sql_or_query, plan_id)
    result = {
        "sql": sql,
        "columns": [
            {"key": "dimension", "label": "dimension"},
            {"key": "value", "label": "value"},
        ],
        "rows": [
            {"dimension": "North", "value": 12840},
            {"dimension": "South", "value": 11720},
            {"dimension": "West", "value": 10895},
            {"dimension": "East", "value": 9850},
        ],
        "metrics": {
            "planningTimeMs": 42,
            "executionTimeMs": 86,
            "rowCount": 4,
            "estimatedRows": 1200,
        },
    }
    RUN_STORE[run_id] = result
    return {"runId": run_id, "status": "running"}


def get_execution_result(run_id: str) -> dict[str, Any] | None:
    return RUN_STORE.get(run_id)


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
    if plan_id and plan_id in PLAN_STORE:
        executable = PLAN_STORE[plan_id]["plan"].get("executable") or {}
        if executable.get("content"):
            return executable["content"]
    if sql_or_query.strip().lower().startswith("select"):
        return sql_or_query
    return "SELECT dimension, value FROM debugsql_stub_result ORDER BY value DESC"


def _stable_id(prefix: str, payload: dict[str, Any]) -> str:
    digest = hashlib.sha1(json.dumps(payload, sort_keys=True, default=str).encode("utf-8")).hexdigest()[:10]
    return f"{prefix}_{digest}"
