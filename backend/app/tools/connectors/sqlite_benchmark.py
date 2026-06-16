from __future__ import annotations

import time
from typing import Any

from app.benchmark_registry import (
    benchmark_questions,
    execute_benchmark_sql,
    get_schema_context,
)
from app.tools.connector_base import DatabaseConnector
from app.tools.policy import is_safe_read_query
from app.tools.schemas import ConnectorCapabilities, DatasetContext


class BenchmarkSQLiteConnector(DatabaseConnector):
    def capabilities(self) -> ConnectorCapabilities:
        return ConnectorCapabilities(
            dbType="sqlite_benchmark",
            label="Benchmark SQLite (read-only)",
            supportsExplain=False,
            supportsSampleRows=True,
            supportsRelationships=True,
            readOnly=True,
            maxRows=100,
            maxSampleRows=10,
        )

    def _schema(self, context: DatasetContext) -> dict[str, Any] | None:
        if not context.benchmark or not context.dbId:
            return None
        return get_schema_context(context.benchmark, context.dbId)

    def list_tables(self, context: DatasetContext) -> list[dict[str, Any]]:
        schema = self._schema(context)
        if not schema:
            return []
        return [
            {
                "name": table["name"],
                "columnCount": len(table.get("columns", [])),
            }
            for table in schema.get("tables", [])
        ]

    def describe_table(self, context: DatasetContext, table: str) -> dict[str, Any]:
        schema = self._schema(context)
        if not schema:
            return {"table": table, "columns": [], "found": False}
        for item in schema.get("tables", []):
            if item.get("name") == table:
                return {
                    "table": table,
                    "columns": [{"name": column} for column in item.get("columns", [])],
                    "found": True,
                }
        return {"table": table, "columns": [], "found": False}

    def get_relationships(self, context: DatasetContext) -> list[dict[str, Any]]:
        schema = self._schema(context)
        if not schema:
            return []
        tables = schema.get("tables", [])
        table_names = [table["name"] for table in tables]
        relationships: list[dict[str, Any]] = []
        for fk in schema.get("foreign_keys", []):
            if len(fk) >= 4:
                from_table = table_names[fk[0]] if fk[0] < len(table_names) else str(fk[0])
                from_column = tables[fk[0]]["columns"][fk[1]] if fk[0] < len(tables) else str(fk[1])
                to_table = table_names[fk[2]] if fk[2] < len(table_names) else str(fk[2])
                to_column = tables[fk[2]]["columns"][fk[3]] if fk[2] < len(tables) else str(fk[3])
                relationships.append(
                    {
                        "fromTable": from_table,
                        "fromColumn": from_column,
                        "toTable": to_table,
                        "toColumn": to_column,
                    }
                )
        return relationships

    def sample_rows(self, context: DatasetContext, table: str, limit: int = 5) -> dict[str, Any]:
        safe_limit = max(1, min(limit, self.capabilities().maxSampleRows))
        sql = f'SELECT * FROM "{table.replace(chr(34), chr(34) * 2)}" LIMIT {safe_limit}'
        return self.execute_readonly(context, sql, max_rows=safe_limit)

    def introspect_schema(self, context: DatasetContext) -> dict[str, Any]:
        schema = self._schema(context)
        if not schema:
            return {"tables": [], "relationships": [], "benchmark": context.benchmark, "dbId": context.dbId}
        return {
            "benchmark": context.benchmark,
            "dbId": context.dbId,
            "tables": [_normalize_table(table) for table in schema.get("tables", [])],
            "relationships": self.get_relationships(context),
            "primaryKeys": schema.get("primary_keys", []),
            "exampleQuestions": benchmark_questions(context.benchmark or "", context.dbId, limit=5),
        }

    def execute_readonly(self, context: DatasetContext, sql: str, max_rows: int = 100) -> dict[str, Any]:
        if not context.benchmark or not context.dbId:
            return _error_result(sql, "Benchmark and database must be selected.")
        if not is_safe_read_query(sql):
            return _error_result(sql, "Only read-only SELECT/WITH SQL can be executed.")
        return execute_benchmark_sql(context.benchmark, context.dbId, sql)


def _normalize_table(table: dict[str, Any]) -> dict[str, Any]:
    return {
        "name": table.get("name", ""),
        "columns": [
            column if isinstance(column, dict) else {"name": str(column)}
            for column in table.get("columns", [])
            if column and column != "*"
        ],
    }


def _error_result(sql: str, message: str) -> dict[str, Any]:
    return {
        "sql": sql,
        "columns": [{"key": "error", "label": "error"}, {"key": "message", "label": "message"}],
        "rows": [{"error": "execution_error", "message": message}],
        "metrics": {"planningTimeMs": 0, "executionTimeMs": 0, "rowCount": 1, "estimatedRows": 0},
    }
