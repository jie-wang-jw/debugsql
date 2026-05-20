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
    if _is_sales_store_demo(message):
        stored = _build_sales_store_demo(message, session_id)
        PLAN_STORE[stored["plan"]["plan_id"]] = stored
        return stored

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
        "assistant_content": _assistant_content((plan.executable.content if plan.executable else ""), graph),
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
    _sync_executable_from_graph(plan_id)
    return graph


def run_demo_execution(sql_or_query: str, session_id: str | None = None, plan_id: str | None = None) -> dict[str, Any]:
    run_id = _stable_id("run", {"sql": sql_or_query, "session": session_id, "plan": plan_id, "time": time.time()})
    sql = _execution_sql(sql_or_query, plan_id)
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

    if plan_id and plan_id in PLAN_STORE:
        executable = PLAN_STORE[plan_id]["plan"].get("executable") or {}
        if executable.get("content"):
            return executable["content"]
    if sql_or_query.strip().lower().startswith("select"):
        return sql_or_query
    return "SELECT dimension, value FROM debugsql_stub_result ORDER BY value DESC"


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
        return rows, columns

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
    return rows, columns


def _stable_id(prefix: str, payload: dict[str, Any]) -> str:
    digest = hashlib.sha1(json.dumps(payload, sort_keys=True, default=str).encode("utf-8")).hexdigest()[:10]
    return f"{prefix}_{digest}"
