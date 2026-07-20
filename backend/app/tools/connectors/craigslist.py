from __future__ import annotations

import sqlite3
import time
from typing import Any

from app.craigslist.registry import (
    dataset_ready,
    images_by_aid,
    image_to_aid,
    load_furniture,
    load_images,
    media_preview,
)
from app.craigslist.resolver import CraigslistSemanticResolver
from app.semantic_sql import SemanticSQLError, contains_semantic_operators, rewrite_semantic_sql
from app.tools.connector_base import DatabaseConnector
from app.tools.policy import is_safe_read_query
from app.tools.schemas import ConnectorCapabilities, DatasetContext


_TABLE_COLUMNS = {
    "furniture": ["aid", "time", "neighborhood", "title", "title_u", "url", "price"],
    "images": ["img", "aid"],
}
_SEMANTIC_TABLES = {"furniture": "aid", "images": "img"}

NL_FILTER_EXAMPLE_SQL = (
    "SELECT f.aid, f.title, f.price, i.img AS asset_id\n"
    "FROM furniture f\n"
    "JOIN images i ON i.aid = f.aid\n"
    "WHERE f.price < 200 AND NL_FILTER(i.img, 'blue chair')\n"
    "ORDER BY nlf_0_score DESC\n"
    "LIMIT 20;"
)


class CraigslistConnector(DatabaseConnector):
    def capabilities(self) -> ConnectorCapabilities:
        return ConnectorCapabilities(
            dbType="craigslist",
            label="Craigslist furniture benchmark (read-only)",
            supportsExplain=False,
            supportsSampleRows=True,
            supportsRelationships=True,
            readOnly=True,
            maxRows=100,
            maxSampleRows=10,
        )

    def list_tables(self, context: DatasetContext) -> list[dict[str, Any]]:
        return [
            {"name": name, "columnCount": len(columns)}
            for name, columns in _TABLE_COLUMNS.items()
        ]

    def describe_table(self, context: DatasetContext, table: str) -> dict[str, Any]:
        return {
            "table": table,
            "columns": [{"name": column} for column in _TABLE_COLUMNS.get(table, [])],
            "found": table in _TABLE_COLUMNS,
        }

    def get_relationships(self, context: DatasetContext) -> list[dict[str, Any]]:
        return [{"fromTable": "images", "fromColumn": "aid", "toTable": "furniture", "toColumn": "aid"}]

    def sample_rows(self, context: DatasetContext, table: str, limit: int = 5) -> dict[str, Any]:
        if table not in _TABLE_COLUMNS:
            return _error_result("", f"Unknown Craigslist table '{table}'.")
        safe_limit = max(1, min(limit, self.capabilities().maxSampleRows))
        return self.execute_readonly(context, f'SELECT * FROM "{table}" LIMIT {safe_limit}', safe_limit)

    def introspect_schema(self, context: DatasetContext) -> dict[str, Any]:
        return {
            "dataset": "craigslist",
            "tables": [
                {"name": name, "columns": [{"name": column} for column in columns]}
                for name, columns in _TABLE_COLUMNS.items()
            ],
            "relationships": self.get_relationships(context),
            "mediaTypes": [{"type": "image", "count": len(load_images())}],
            "exampleQuestions": [
                {"question": "Show blue chair images under 200 dollars"},
                {"question": "Find wooden tables with matching photos"},
                {"question": "Show red furniture images sorted by price"},
            ],
            "semanticSql": {
                "operators": ["NL_FILTER(column, 'natural language condition')"],
                "semanticColumns": ["images.img", "furniture.title_u"],
                "instructions": (
                    "For visual meaning, join furniture to images on aid and use NL_FILTER(images.img, '...'). "
                    "For fuzzy title meaning, use NL_FILTER(furniture.title_u, '...'). Always select "
                    "images.img AS asset_id when the user asks to see images."
                ),
                "exampleSql": NL_FILTER_EXAMPLE_SQL,
            },
        }

    def execute_readonly(self, context: DatasetContext, sql: str, max_rows: int = 100) -> dict[str, Any]:
        if not dataset_ready():
            return _error_result(
                sql,
                "Craigslist dataset is not ready. Expected furnitures.csv, imgs.csv, and "
                "furniture_imgs/ under data/benchmarks/Craigslist/.",
            )
        if not is_safe_read_query(sql):
            return _error_result(sql, "Only read-only SELECT/WITH SQL can be executed.")

        started = time.perf_counter()
        executable_sql = sql
        semantic: dict[str, Any] | None = None
        if contains_semantic_operators(sql):
            try:
                rewrite = rewrite_semantic_sql(
                    sql,
                    resolver=CraigslistSemanticResolver(),
                    table_columns=_TABLE_COLUMNS,
                    semantic_tables=_SEMANTIC_TABLES,
                )
            except SemanticSQLError as exc:
                return _error_result(sql, exc.message)
            executable_sql = rewrite.sql
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
            with sqlite3.connect(":memory:") as connection:
                connection.row_factory = sqlite3.Row
                _load_tables(connection)
                cursor = connection.execute(executable_sql)
                fetched = cursor.fetchmany(max_rows)
                columns = [{"key": desc[0], "label": desc[0]} for desc in (cursor.description or [])]
                rows = [dict(row) for row in fetched]
        except sqlite3.Error as exc:
            return _error_result(executable_sql, f"SQLite execution error: {exc}")

        elapsed_ms = max(1, int((time.perf_counter() - started) * 1000))
        payload: dict[str, Any] = {
            "sql": executable_sql,
            "columns": columns,
            "rows": rows,
            "mediaPreviews": _media_previews(rows),
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


def _load_tables(connection: sqlite3.Connection) -> None:
    connection.execute(
        "CREATE TABLE furniture (aid TEXT PRIMARY KEY, time TEXT, neighborhood TEXT, "
        "title TEXT, title_u TEXT, url TEXT, price REAL)"
    )
    connection.execute("CREATE TABLE images (img TEXT PRIMARY KEY, aid TEXT)")
    connection.executemany(
        "INSERT INTO furniture VALUES (?, ?, ?, ?, ?, ?, ?)",
        [
            (
                row["aid"], row.get("time"), row.get("neighborhood"), row.get("title"),
                row.get("title_u"), row.get("url"), row.get("price"),
            )
            for row in load_furniture()
        ],
    )
    connection.executemany(
        "INSERT INTO images VALUES (?, ?)",
        [(row["img"], row["aid"]) for row in load_images()],
    )


def _media_previews(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    previews: list[dict[str, Any]] = []
    seen: set[str] = set()
    by_aid = images_by_aid()
    known_images = image_to_aid()
    for row in rows:
        value = row.get("img") or row.get("asset_id")
        img = str(value) if value is not None else ""
        if img not in known_images:
            aid = str(row.get("aid") or row.get("entity_id") or value or "")
            img = (by_aid.get(aid) or [""])[0]
        if not img or img in seen:
            continue
        preview = media_preview(img, float(row.get("score") or row.get("nlf_0_score") or 0))
        if preview is not None:
            seen.add(img)
            previews.append(preview)
    return previews


def _error_result(sql: str, message: str) -> dict[str, Any]:
    return {
        "sql": sql,
        "columns": [{"key": "error", "label": "error"}, {"key": "message", "label": "message"}],
        "rows": [{"error": "execution_error", "message": message}],
        "mediaPreviews": [],
        "metrics": {"planningTimeMs": 0, "executionTimeMs": 0, "rowCount": 1, "estimatedRows": 0},
    }
