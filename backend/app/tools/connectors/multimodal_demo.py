from __future__ import annotations

import sqlite3
import time
from typing import Any

from app.multimodal.registry import build_media_match, load_assets, load_entities
from app.semantic_sql import (
    KeywordMediaResolver,
    SemanticSQLError,
    contains_semantic_operators,
    rewrite_semantic_sql,
)
from app.tools.connector_base import DatabaseConnector
from app.tools.policy import is_safe_read_query
from app.tools.schemas import ConnectorCapabilities, DatasetContext


_TABLE_COLUMNS: dict[str, list[str]] = {
    "entities": ["id", "name", "category", "price", "description"],
    "media_assets": ["id", "entity_id", "media_type", "caption", "transcript", "tags", "file_path"],
}

# media_assets is the only table with a semantic resolver in this slice;
# its primary key is what NL_FILTER match CTEs join against.
_SEMANTIC_TABLES: dict[str, str] = {"media_assets": "id"}

NL_FILTER_EXAMPLE_SQL = (
    "SELECT e.name, e.price, a.id AS asset_id, a.file_path\n"
    "FROM entities e\n"
    "JOIN media_assets a ON a.entity_id = e.id\n"
    "WHERE NL_FILTER(a.caption, 'red car')\n"
    "ORDER BY nlf_0_score DESC;"
)


class MultimodalDemoConnector(DatabaseConnector):
    def capabilities(self) -> ConnectorCapabilities:
        return ConnectorCapabilities(
            dbType="multimodal_demo",
            label="Multimodal Demo (read-only)",
            supportsExplain=False,
            supportsSampleRows=True,
            supportsRelationships=True,
            readOnly=True,
            maxRows=100,
            maxSampleRows=10,
        )

    def list_tables(self, context: DatasetContext) -> list[dict[str, Any]]:
        return [
            {"name": "entities", "columnCount": 5},
            {"name": "media_assets", "columnCount": 7},
        ]

    def describe_table(self, context: DatasetContext, table: str) -> dict[str, Any]:
        return {
            "table": table,
            "columns": [{"name": column} for column in _TABLE_COLUMNS.get(table, [])],
            "found": table in _TABLE_COLUMNS,
        }

    def get_relationships(self, context: DatasetContext) -> list[dict[str, Any]]:
        return [
            {
                "fromTable": "media_assets",
                "fromColumn": "entity_id",
                "toTable": "entities",
                "toColumn": "id",
            }
        ]

    def sample_rows(self, context: DatasetContext, table: str, limit: int = 5) -> dict[str, Any]:
        safe_limit = max(1, min(limit, self.capabilities().maxSampleRows))
        escaped = table.replace('"', '""')
        return self.execute_readonly(context, f'SELECT * FROM "{escaped}" LIMIT {safe_limit}', max_rows=safe_limit)

    def introspect_schema(self, context: DatasetContext) -> dict[str, Any]:
        assets = load_assets()
        media_counts = {
            "image": sum(1 for asset in assets if asset.media_type == "image"),
            "audio": sum(1 for asset in assets if asset.media_type == "audio"),
            "video": sum(1 for asset in assets if asset.media_type == "video"),
        }
        return {
            "dataset": "multimodal_demo",
            "tables": [
                {"name": "entities", "columns": [{"name": name} for name in ["id", "name", "category", "price", "description"]]},
                {"name": "media_assets", "columns": [{"name": name} for name in ["id", "entity_id", "media_type", "caption", "transcript", "tags", "file_path"]]},
            ],
            "relationships": self.get_relationships(context),
            "mediaTypes": [
                {"type": key, "count": value}
                for key, value in media_counts.items()
            ],
            "exampleQuestions": [
                {"question": "Find red car images from the ThalamusDB sample"},
                {"question": "Show white cars under 20000"},
                {"question": "Find images that look like a red backpack"},
                {"question": "Show audio clips that sound like applause"},
                {"question": "Find videos related to classroom teaching"},
            ],
            "semanticSql": {
                "operators": ["NL_FILTER(column, 'natural language condition')"],
                "exampleSql": NL_FILTER_EXAMPLE_SQL,
            },
        }

    def execute_readonly(self, context: DatasetContext, sql: str, max_rows: int = 100) -> dict[str, Any]:
        if not is_safe_read_query(sql):
            return _error_result(sql, "Only read-only SELECT/WITH SQL can be executed.")

        start = time.perf_counter()
        exec_sql = sql
        semantic: dict[str, Any] | None = None
        if contains_semantic_operators(sql):
            try:
                rewrite = rewrite_semantic_sql(
                    sql,
                    resolver=KeywordMediaResolver(),
                    table_columns=_TABLE_COLUMNS,
                    semantic_tables=_SEMANTIC_TABLES,
                )
            except SemanticSQLError as exc:
                return _error_result(sql, exc.message)
            exec_sql = rewrite.sql
            semantic = {
                "originalSql": rewrite.original_sql,
                "explanation": rewrite.explanation,
                "assumptions": rewrite.assumptions,
                "operators": [
                    {
                        "opId": op.op_id,
                        "table": op.table,
                        "column": op.column,
                        "predicate": op.predicate,
                        "strategy": op.strategy,
                        "matchCount": len(op.matches),
                    }
                    for op in rewrite.operators
                ],
            }

        try:
            with sqlite3.connect(":memory:") as conn:
                conn.row_factory = sqlite3.Row
                _load_demo_tables(conn)
                cursor = conn.execute(exec_sql)
                fetched = cursor.fetchmany(max_rows)
                columns = [{"key": desc[0], "label": desc[0]} for desc in (cursor.description or [])]
                rows = [dict(row) for row in fetched]
        except sqlite3.Error as exc:
            return _error_result(exec_sql, f"SQLite execution error: {exc}")
        elapsed_ms = max(1, int((time.perf_counter() - start) * 1000))
        previews = _media_previews(rows)
        payload: dict[str, Any] = {
            "sql": exec_sql,
            "columns": columns,
            "rows": rows,
            "mediaPreviews": previews,
            "metrics": {
                "planningTimeMs": 0,
                "executionTimeMs": elapsed_ms,
                "rowCount": len(rows),
                "estimatedRows": len(rows),
            },
        }
        if semantic is not None:
            payload["semantic"] = semantic
        return payload


def _load_demo_tables(conn: sqlite3.Connection) -> None:
    conn.execute("CREATE TABLE entities (id TEXT PRIMARY KEY, name TEXT, category TEXT, price REAL, description TEXT)")
    conn.execute(
        "CREATE TABLE media_assets ("
        "id TEXT PRIMARY KEY, entity_id TEXT, media_type TEXT, caption TEXT, "
        "transcript TEXT, tags TEXT, file_path TEXT)"
    )
    for entity in load_entities():
        conn.execute(
            "INSERT INTO entities VALUES (?, ?, ?, ?, ?)",
            (entity.id, entity.name, entity.category, entity.price, entity.description),
        )
    for asset in load_assets():
        conn.execute(
            "INSERT INTO media_assets VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                asset.id,
                asset.entity_id,
                asset.media_type,
                asset.caption,
                asset.transcript,
                ", ".join(asset.tags),
                asset.file_path,
            ),
        )


def _media_previews(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    assets_by_id = {asset.id: asset for asset in load_assets()}
    previews = []
    seen = set()
    for row in rows:
        asset_id = row.get("asset_id")
        if not isinstance(asset_id, str) or asset_id in seen:
            continue
        asset = assets_by_id.get(asset_id)
        if asset is None:
            continue
        seen.add(asset_id)
        previews.append(build_media_match(asset, float(row.get("score") or 0)).model_dump())
    return previews


def _error_result(sql: str, message: str) -> dict[str, Any]:
    return {
        "sql": sql,
        "columns": [{"key": "error", "label": "error"}, {"key": "message", "label": "message"}],
        "rows": [{"error": "execution_error", "message": message}],
        "mediaPreviews": [],
        "metrics": {"planningTimeMs": 0, "executionTimeMs": 0, "rowCount": 1, "estimatedRows": 0},
    }
