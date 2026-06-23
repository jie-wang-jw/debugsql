from __future__ import annotations

from typing import Any

from app.gemini.schemas import GeminiQueryPlan


def gemini_plan_to_graph(plan: GeminiQueryPlan, query_label: str) -> dict[str, Any]:
    """Map a validated LLM plan to the frontend QueryPlanGraph shape."""
    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []

    x_center = 320
    y_start = 40
    y_step = 130

    nodes.append(
        {
            "id": "intent",
            "type": "intent",
            "position": {"x": x_center, "y": y_start},
            "data": {
                "kind": "intent",
                "intentLabel": plan.goal,
                "targetColumns": [],
            },
        }
    )

    previous_id = "intent"
    for index, step in enumerate(sorted(plan.steps, key=lambda item: item.id)):
        node_id = f"step_{step.id}"
        y = y_start + (index + 1) * y_step
        nodes.append(
            {
                "id": node_id,
                "type": "operation",
                "position": {"x": x_center, "y": y},
                "data": {
                    "kind": "operation",
                    "operationType": "SELECT",
                    "label": step.title,
                    "detail": step.description,
                    "estimatedRows": 0,
                    "cost": round(8.0 + index * 3.5, 1),
                    "executionState": "pending",
                },
            }
        )
        edges.append(_edge(previous_id, node_id, animated=True))
        previous_id = node_id

    sql_node_id = "op_sql"
    sql_y = y_start + (len(plan.steps) + 1) * y_step
    sql_content = plan.sql or ""
    nodes.append(
        {
            "id": sql_node_id,
            "type": "operation",
            "position": {"x": x_center, "y": sql_y},
            "data": {
                "kind": "operation",
                "operationType": "SQL",
                "label": "Generated SQL",
                "detail": sql_content,
                "fragmentSql": sql_content,
                "estimatedRows": 0,
                "cost": round(12.0 + len(plan.steps) * 3.5, 1),
                "executionState": "pending",
            },
        }
    )
    edges.append(_edge(previous_id, sql_node_id, animated=True))

    result_node_id = "data_result"
    result_y = sql_y + y_step
    nodes.append(
        {
            "id": result_node_id,
            "type": "data",
            "position": {"x": x_center, "y": result_y},
            "data": {
                "kind": "data",
                "tableName": "Result",
                "nodeRole": "result",
                "rowCount": 0,
                "estimatedCost": round(18.0 + len(plan.steps) * 4.0, 1),
                "columns": [],
                "executionState": "pending",
            },
        }
    )
    edges.append(_edge(sql_node_id, result_node_id, animated=True))

    return {
        "nodes": nodes,
        "edges": edges,
        "queryLabel": query_label,
        "totalCost": round(18.5 + len(nodes) * 7.3, 1),
    }


def _edge(source: str, target: str, animated: bool = False) -> dict[str, Any]:
    return {
        "id": f"{source}-{target}",
        "source": source,
        "target": target,
        "animated": animated,
    }
