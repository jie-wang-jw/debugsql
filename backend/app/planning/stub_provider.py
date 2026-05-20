from __future__ import annotations

import hashlib
import json
from typing import Any

from app.planning.schemas import ExecutablePlan, PlanEdge, PlanNode, PlanningRequest, QueryPlan


class StubIRToPlanProvider:
    """Deterministic relational IR-to-plan baseline for UI and integration development."""

    provider_name = "stub"
    version = "0.1.0"

    def generate_plan(self, request: PlanningRequest) -> QueryPlan:
        intent_ir = request.intent_ir
        options = request.options

        nodes: list[PlanNode] = [
            PlanNode(
                node_id="intent",
                node_type="intent",
                label="Intent IR",
                status="ready",
                editable=True,
                payload=intent_ir,
            )
        ]
        edges: list[PlanEdge] = []

        operation_nodes = self._build_operation_nodes(intent_ir, request.schema_context)
        nodes.extend(operation_nodes)
        nodes.append(
            PlanNode(
                node_id="data_result",
                node_type="data",
                label="Result Data",
                status="pending",
                editable=False,
                payload={"materialized": False, "preview": []},
            )
        )

        ordered_node_ids = [node.node_id for node in nodes]
        for source, target in zip(ordered_node_ids, ordered_node_ids[1:]):
            edge_type = "data_flow" if target == "data_result" else "control_flow"
            edges.append(PlanEdge(source=source, target=target, edge_type=edge_type))

        sql, warnings = self._build_sql(intent_ir, request.schema_context, options.dialect)

        return QueryPlan(
            plan_id=self._plan_id(intent_ir),
            plan_type=options.plan_type,
            data_source_type=options.data_source_type,
            nodes=nodes,
            edges=edges,
            executable=ExecutablePlan(type="sql", dialect=options.dialect, content=sql),
            warnings=warnings,
            metadata={"provider": self.provider_name, "version": self.version},
        )

    def _build_operation_nodes(
        self, intent_ir: dict[str, Any], schema_context: dict[str, Any]
    ) -> list[PlanNode]:
        table = self._infer_table(intent_ir, schema_context)
        nodes = [
            PlanNode(
                node_id="op_scan",
                node_type="operation",
                operation_type="scan",
                label=f"SCAN {table or 'table'}",
                payload={"table": table},
            )
        ]

        filters = intent_ir.get("filters") or intent_ir.get("filter_hints") or []
        if filters:
            nodes.append(
                PlanNode(
                    node_id="op_filter",
                    node_type="operation",
                    operation_type="filter",
                    label="FILTER rows",
                    payload={"filters": filters},
                )
            )

        joins = intent_ir.get("joins") or intent_ir.get("join_hints") or []
        if joins:
            nodes.append(
                PlanNode(
                    node_id="op_join",
                    node_type="operation",
                    operation_type="join",
                    label="JOIN tables",
                    payload={"joins": joins},
                )
            )

        group_by = intent_ir.get("group_by") or intent_ir.get("dimension_hints") or []
        if group_by:
            nodes.append(
                PlanNode(
                    node_id="op_group_by",
                    node_type="operation",
                    operation_type="group_by",
                    label="GROUP BY",
                    payload={"columns": group_by},
                )
            )

        aggregation = intent_ir.get("aggregation") or intent_ir.get("agg_func_hint")
        target_columns = intent_ir.get("target_columns") or intent_ir.get("metric_hints") or []
        if aggregation or target_columns:
            nodes.append(
                PlanNode(
                    node_id="op_aggregate",
                    node_type="operation",
                    operation_type="aggregate",
                    label="AGGREGATE",
                    payload={"function": aggregation or "avg", "columns": target_columns},
                )
            )

        order_by = intent_ir.get("order_by") or intent_ir.get("sort_hint")
        if order_by:
            nodes.append(
                PlanNode(
                    node_id="op_sort",
                    node_type="operation",
                    operation_type="sort",
                    label="SORT",
                    payload={"order_by": order_by},
                )
            )

        limit = intent_ir.get("limit") or intent_ir.get("limit_hint")
        if limit:
            nodes.append(
                PlanNode(
                    node_id="op_limit",
                    node_type="operation",
                    operation_type="limit",
                    label="LIMIT",
                    payload={"limit": limit},
                )
            )

        return nodes

    def _build_sql(
        self, intent_ir: dict[str, Any], schema_context: dict[str, Any], dialect: str
    ) -> tuple[str, list[str]]:
        warnings: list[str] = []
        table = self._infer_table(intent_ir, schema_context)
        if not table:
            table = "<table>"
            warnings.append("No table was found in the Intent IR or schema context.")

        group_by = self._as_list(intent_ir.get("group_by") or intent_ir.get("dimension_hints"))
        metrics = self._as_list(intent_ir.get("target_columns") or intent_ir.get("metric_hints"))
        aggregation = intent_ir.get("aggregation") or intent_ir.get("agg_func_hint")

        select_parts: list[str] = []
        select_parts.extend(group_by)
        if aggregation and metrics:
            func = str(aggregation).upper()
            select_parts.extend(f"{func}({column}) AS {func.lower()}_{column}" for column in metrics)
        elif metrics:
            select_parts.extend(metrics)

        if not select_parts:
            select_parts = ["*"]

        sql_parts = [f"SELECT {', '.join(select_parts)}", f"FROM {table}"]

        where_clause = self._filters_to_sql(intent_ir.get("filters") or intent_ir.get("filter_hints"))
        if where_clause:
            sql_parts.append(f"WHERE {where_clause}")

        if group_by:
            sql_parts.append(f"GROUP BY {', '.join(group_by)}")

        order_by = intent_ir.get("order_by") or intent_ir.get("sort_hint")
        order_clause = self._order_to_sql(order_by)
        if order_clause:
            sql_parts.append(f"ORDER BY {order_clause}")

        limit = intent_ir.get("limit") or intent_ir.get("limit_hint")
        if limit:
            sql_parts.append(f"LIMIT {int(limit)}")

        return "\n".join(sql_parts), warnings

    def _infer_table(self, intent_ir: dict[str, Any], schema_context: dict[str, Any]) -> str | None:
        table = intent_ir.get("table") or intent_ir.get("table_name")
        if table:
            return str(table)

        tables = schema_context.get("tables") or []
        if tables:
            first = tables[0]
            if isinstance(first, dict):
                return first.get("name") or first.get("table_name")
            return str(first)

        return None

    def _filters_to_sql(self, filters: Any) -> str:
        if not filters:
            return ""
        clauses = []
        for item in self._as_list(filters):
            if isinstance(item, dict):
                column = item.get("column")
                op = item.get("op") or item.get("operator") or "="
                value = item.get("value")
                clauses.append(f"{column} {op} {self._sql_literal(value)}")
            else:
                clauses.append(str(item))
        return " AND ".join(clauses)

    def _order_to_sql(self, order_by: Any) -> str:
        if not order_by:
            return ""
        if isinstance(order_by, dict):
            column = order_by.get("column")
            direction = order_by.get("direction", "ASC")
            return f"{column} {str(direction).upper()}"
        if isinstance(order_by, list):
            return ", ".join(str(item) for item in order_by)
        return str(order_by)

    def _sql_literal(self, value: Any) -> str:
        if value is None:
            return "NULL"
        if isinstance(value, bool):
            return "TRUE" if value else "FALSE"
        if isinstance(value, int | float):
            return str(value)
        escaped = str(value).replace("'", "''")
        return f"'{escaped}'"

    def _as_list(self, value: Any) -> list[Any]:
        if value is None:
            return []
        if isinstance(value, list):
            return value
        return [value]

    def _plan_id(self, intent_ir: dict[str, Any]) -> str:
        payload = json.dumps(intent_ir, sort_keys=True, default=str)
        digest = hashlib.sha1(payload.encode("utf-8")).hexdigest()[:10]
        return f"plan_stub_{digest}"
