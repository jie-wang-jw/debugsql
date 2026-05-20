from __future__ import annotations

import json
import sqlite3
import time
from functools import lru_cache
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
BENCHMARK_ROOT = PROJECT_ROOT / "data" / "benchmarks"
SPIDER_ROOT = BENCHMARK_ROOT / "spider"


def list_benchmarks() -> list[dict[str, Any]]:
    spider_dbs = list_spider_databases()
    return [
        {
            "id": "spider",
            "label": "Spider",
            "status": "ready" if spider_dbs else "missing",
            "databaseCount": len(spider_dbs),
        },
        {
            "id": "bird",
            "label": "BIRD",
            "status": "placeholder",
            "databaseCount": 0,
        },
    ]


def list_databases(benchmark: str) -> list[dict[str, Any]]:
    if benchmark != "spider":
        return []
    return list_spider_databases()


@lru_cache(maxsize=1)
def list_spider_databases() -> list[dict[str, Any]]:
    schemas = _load_spider_schema()
    questions_by_db = _load_spider_questions_by_db()
    database_root = SPIDER_ROOT / "sqlite" / "database"
    databases: list[dict[str, Any]] = []

    for db_id in sorted(schemas):
        sqlite_path = database_root / db_id / f"{db_id}.sqlite"
        databases.append(
            {
                "benchmark": "spider",
                "dbId": db_id,
                "label": db_id,
                "hasSQLite": sqlite_path.exists(),
                "tableCount": len(schemas[db_id].get("table_names_clean", [])),
                "sampleQuestions": questions_by_db.get(db_id, [])[:5],
            }
        )
    return databases


def get_schema_context(benchmark: str | None, db_id: str | None) -> dict[str, Any] | None:
    if benchmark != "spider" or not db_id:
        return None
    schema = _load_spider_schema().get(db_id)
    if not schema:
        return None

    table_names = schema.get("table_names_clean") or schema.get("table_names_original") or []
    column_pairs = schema.get("column_names_clean") or schema.get("column_names_original") or []
    tables = [{"name": name, "columns": []} for name in table_names]

    for table_index, column_name in column_pairs:
        if table_index >= 0 and table_index < len(tables):
            tables[table_index]["columns"].append(column_name)

    return {
        "benchmark": benchmark,
        "db_id": db_id,
        "tables": tables,
        "foreign_keys": schema.get("foreign_keys", []),
        "primary_keys": schema.get("primary_keys", []),
    }


def find_spider_gold_sql(db_id: str | None, question: str) -> str | None:
    if not db_id:
        return None
    normalized = _normalize_question(question)
    for item in _load_spider_questions_by_db(full=True).get(db_id, []):
        if _normalize_question(item.get("question", "")) == normalized:
            return item.get("query")
    return None


def execute_spider_sql(db_id: str, sql: str) -> dict[str, Any]:
    if not _is_safe_read_query(sql):
        return _error_result(sql, "Only read-only SELECT/WITH SQL can be executed against benchmark databases.")

    sqlite_path = SPIDER_ROOT / "sqlite" / "database" / db_id / f"{db_id}.sqlite"
    if not sqlite_path.exists():
        return _error_result(sql, f"SQLite database was not found for Spider db_id '{db_id}'.")

    start = time.perf_counter()
    try:
        with sqlite3.connect(sqlite_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(sql)
            fetched = cursor.fetchmany(100)
            columns = [{"key": desc[0], "label": desc[0]} for desc in (cursor.description or [])]
            rows = [dict(row) for row in fetched]
    except sqlite3.Error as exc:
        return _error_result(sql, f"SQLite execution error: {exc}")

    elapsed_ms = max(1, int((time.perf_counter() - start) * 1000))
    return {
        "sql": sql,
        "columns": columns,
        "rows": rows,
        "metrics": {
            "planningTimeMs": 0,
            "executionTimeMs": elapsed_ms,
            "rowCount": len(rows),
            "estimatedRows": len(rows),
        },
    }


@lru_cache(maxsize=1)
def _load_spider_schema() -> dict[str, Any]:
    path = SPIDER_ROOT / "processed" / "clean_schema.json"
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


@lru_cache(maxsize=2)
def _load_spider_questions_by_db(full: bool = False) -> dict[str, list[dict[str, Any]]]:
    path = SPIDER_ROOT / "processed" / "clean_dev.json"
    if not path.exists():
        return {}

    rows = json.loads(path.read_text(encoding="utf-8"))
    grouped: dict[str, list[dict[str, Any]]] = {}
    for item in rows:
        db_id = item.get("db_id")
        if not db_id:
            continue
        payload = item if full else {"question": item.get("question"), "query": item.get("query")}
        grouped.setdefault(db_id, []).append(payload)
    return grouped


def _normalize_question(question: str) -> str:
    return " ".join(question.lower().strip().split())


def _is_safe_read_query(sql: str) -> bool:
    stripped = sql.strip().rstrip(";").strip()
    if not stripped:
        return False
    lowered = stripped.lower()
    if not (lowered.startswith("select") or lowered.startswith("with")):
        return False
    blocked = (" insert ", " update ", " delete ", " drop ", " alter ", " create ", " attach ", " pragma ")
    return not any(token in f" {lowered} " for token in blocked)


def _error_result(sql: str, message: str) -> dict[str, Any]:
    return {
        "sql": sql,
        "columns": [
            {"key": "error", "label": "error"},
            {"key": "message", "label": "message"},
        ],
        "rows": [{"error": "execution_error", "message": message}],
        "metrics": {
            "planningTimeMs": 0,
            "executionTimeMs": 0,
            "rowCount": 1,
            "estimatedRows": 0,
        },
    }
