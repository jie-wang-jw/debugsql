from __future__ import annotations

import time
from typing import Any

from sqlalchemy import inspect, text
from sqlalchemy.exc import SQLAlchemyError

from app.database import get_engine
from app.tools.connector_base import DatabaseConnector
from app.tools.policy import is_safe_read_query
from app.tools.schemas import ConnectorCapabilities, DatasetContext


class PostgresConnector(DatabaseConnector):
    def capabilities(self) -> ConnectorCapabilities:
        return ConnectorCapabilities(
            dbType="postgres",
            label="PostgreSQL (read-only)",
            supportsExplain=True,
            supportsSampleRows=True,
            supportsRelationships=True,
            readOnly=True,
            maxRows=100,
            maxSampleRows=10,
        )

    def list_tables(self, context: DatasetContext) -> list[dict[str, Any]]:
        inspector = inspect(get_engine())
        return [
            {"name": name, "schema": "public", "columnCount": len(inspector.get_columns(name))}
            for name in inspector.get_table_names()
        ]

    def describe_table(self, context: DatasetContext, table: str) -> dict[str, Any]:
        inspector = inspect(get_engine())
        if table not in inspector.get_table_names():
            return {"table": table, "columns": [], "found": False}
        columns = [
            {"name": column["name"], "type": str(column.get("type", ""))}
            for column in inspector.get_columns(table)
        ]
        return {"table": table, "columns": columns, "found": True}

    def get_relationships(self, context: DatasetContext) -> list[dict[str, Any]]:
        inspector = inspect(get_engine())
        relationships: list[dict[str, Any]] = []
        for table in inspector.get_table_names():
            for fk in inspector.get_foreign_keys(table):
                constrained = fk.get("constrained_columns") or []
                referred_table = fk.get("referred_table")
                referred_columns = fk.get("referred_columns") or []
                if constrained and referred_table and referred_columns:
                    relationships.append(
                        {
                            "fromTable": table,
                            "fromColumn": constrained[0],
                            "toTable": referred_table,
                            "toColumn": referred_columns[0],
                        }
                    )
        return relationships

    def sample_rows(self, context: DatasetContext, table: str, limit: int = 5) -> dict[str, Any]:
        safe_limit = max(1, min(limit, self.capabilities().maxSampleRows))
        quoted = table.replace('"', '""')
        sql = f'SELECT * FROM "{quoted}" LIMIT {safe_limit}'
        return self.execute_readonly(context, sql, max_rows=safe_limit)

    def introspect_schema(self, context: DatasetContext) -> dict[str, Any]:
        tables = self.list_tables(context)
        detailed = []
        for table in tables:
            described = self.describe_table(context, table["name"])
            detailed.append({"name": table["name"], "columns": described.get("columns", [])})
        return {
            "dbType": "postgres",
            "tables": detailed,
            "relationships": self.get_relationships(context),
        }

    def explain_sql(self, context: DatasetContext, sql: str) -> dict[str, Any]:
        if not is_safe_read_query(sql):
            return {"supported": True, "plan": None, "message": "Only read-only queries can be explained."}
        try:
            with get_engine().connect() as connection:
                result = connection.execute(text(f"EXPLAIN {sql.rstrip(';')}"))
                plan_lines = [row[0] for row in result.fetchall()]
            return {"supported": True, "plan": plan_lines, "message": "EXPLAIN completed."}
        except SQLAlchemyError as exc:
            return {"supported": True, "plan": None, "message": f"EXPLAIN failed: {exc}"}

    def execute_readonly(self, context: DatasetContext, sql: str, max_rows: int = 100) -> dict[str, Any]:
        if not is_safe_read_query(sql):
            return _error_result(sql, "Only read-only SELECT/WITH SQL can be executed.")
        safe_limit = max(1, min(max_rows, self.capabilities().maxRows))
        limited_sql = _apply_limit(sql, safe_limit)
        start = time.perf_counter()
        try:
            with get_engine().connect() as connection:
                result = connection.execute(text(limited_sql))
                rows = [dict(row._mapping) for row in result.fetchmany(safe_limit)]
                columns = [{"key": key, "label": key} for key in (rows[0].keys() if rows else [])]
        except SQLAlchemyError as exc:
            return _error_result(sql, f"PostgreSQL execution error: {exc}")
        elapsed_ms = max(1, int((time.perf_counter() - start) * 1000))
        return {
            "sql": limited_sql,
            "columns": columns,
            "rows": rows,
            "metrics": {
                "planningTimeMs": 0,
                "executionTimeMs": elapsed_ms,
                "rowCount": len(rows),
                "estimatedRows": len(rows),
            },
        }


def _apply_limit(sql: str, limit: int) -> str:
    stripped = sql.strip().rstrip(";")
    if " limit " in stripped.lower():
        return stripped
    return f"{stripped} LIMIT {limit}"


def _error_result(sql: str, message: str) -> dict[str, Any]:
    return {
        "sql": sql,
        "columns": [{"key": "error", "label": "error"}, {"key": "message", "label": "message"}],
        "rows": [{"error": "execution_error", "message": message}],
        "metrics": {"planningTimeMs": 0, "executionTimeMs": 0, "rowCount": 1, "estimatedRows": 0},
    }
