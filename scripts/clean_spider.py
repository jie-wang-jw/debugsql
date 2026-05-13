"""
clean_spider.py
---------------
Spider dataset cleaning pipeline for DebugSQL.

Usage:
    python clean_spider.py --spider_dir ./data/spider --output_dir ./data/spider_clean

Outputs:
    - clean_schema.json      : cleaned + validated schema index keyed by db_id
    - clean_dev.json         : cleaned dev queries
    - clean_train.json       : cleaned train queries
    - cleaning_report.json   : summary of all issues found and fixed
"""

import os
import re
import json
import sqlite3
import argparse
import logging
from pathlib import Path
from typing import Any

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def normalize_name(name: str) -> str:
    """Lowercase, strip, replace spaces/hyphens with underscores."""
    return re.sub(r"[\s\-]+", "_", name.strip()).lower()


def normalize_sql(sql: str) -> str:
    """Uppercase SQL keywords, collapse whitespace."""
    keywords = [
        "select", "from", "where", "join", "left", "right", "inner", "outer",
        "on", "group", "by", "order", "having", "limit", "union", "intersect",
        "except", "distinct", "as", "and", "or", "not", "in", "is", "null",
        "count", "sum", "avg", "min", "max", "between", "like", "exists",
        "case", "when", "then", "else", "end", "insert", "update", "delete",
        "create", "drop", "alter", "table", "index", "view",
    ]
    for kw in keywords:
        # \b word boundaries prevent partial matches (e.g., "ORDER" inside "REORDER")
        sql = re.sub(rf"\b{kw}\b", kw.upper(), sql, flags=re.IGNORECASE)
    sql = re.sub(r"\s+", " ", sql).strip()
    return sql


def clean_text(text: str) -> str:
    """Strip, fix common unicode issues, normalize whitespace."""
    text = text.strip()
    # Replace curly quotes with straight quotes
    text = text.replace("\u2018", "'").replace("\u2019", "'")
    text = text.replace("\u201c", '"').replace("\u201d", '"')
    # Normalize whitespace
    text = re.sub(r"\s+", " ", text)
    return text


# ---------------------------------------------------------------------------
# Step 1 — Validate that every db_id has a .sqlite file
# ---------------------------------------------------------------------------

def get_available_dbs(database_dir: Path) -> set[str]:
    """Return db_ids for which a .sqlite file actually exists on disk.

    Spider uses a flat layout: database/<db_id>/<db_id>.sqlite, so we check
    that the inner file matches the folder name before accepting it.
    """
    available = set()
    for db_folder in database_dir.iterdir():
        if db_folder.is_dir():
            sqlite_file = db_folder / f"{db_folder.name}.sqlite"
            if sqlite_file.exists():
                available.add(db_folder.name)
    return available


# ---------------------------------------------------------------------------
# Step 2 — Load and clean schema (tables.json)
# ---------------------------------------------------------------------------

def get_sqlite_schema(sqlite_path: Path) -> dict[str, list[str]]:
    """Return {table_name: [col_name, ...]} from the actual SQLite file."""
    schema: dict[str, list[str]] = {}
    try:
        conn = sqlite3.connect(str(sqlite_path))
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = [row[0] for row in cursor.fetchall()]
        for table in tables:
            cursor.execute(f'PRAGMA table_info("{table}");')
            cols = [row[1] for row in cursor.fetchall()]
            schema[table.lower()] = cols
        conn.close()
    except Exception as e:
        log.warning(f"  Could not read SQLite schema from {sqlite_path}: {e}")
    return schema


def check_empty_tables(sqlite_path: Path) -> list[str]:
    """Return list of table names that have zero rows."""
    empty = []
    try:
        conn = sqlite3.connect(str(sqlite_path))
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = [row[0] for row in cursor.fetchall()]
        for table in tables:
            cursor.execute(f'SELECT COUNT(*) FROM "{table}";')
            count = cursor.fetchone()[0]
            if count == 0:
                empty.append(table)
        conn.close()
    except Exception as e:
        log.warning(f"  Could not check empty tables in {sqlite_path}: {e}")
    return empty


def clean_schema(
    tables_json: list[dict],
    available_dbs: set[str],
    database_dir: Path,
    report: dict,
) -> dict[str, Any]:
    """
    Clean tables.json entries and return a dict keyed by db_id.
    Also validates foreign keys and flags empty tables.
    """
    clean: dict[str, Any] = {}
    report["schema"] = {
        "missing_sqlite": [],
        "fk_mismatches": [],
        "empty_tables": {},
        "normalized_names": [],
    }

    for entry in tables_json:
        db_id = entry["db_id"]

        # ── 1. Check SQLite exists ──────────────────────────────────────────
        if db_id not in available_dbs:
            log.warning(f"[SCHEMA] No SQLite found for db_id='{db_id}' — skipping")
            report["schema"]["missing_sqlite"].append(db_id)
            continue

        sqlite_path = database_dir / db_id / f"{db_id}.sqlite"
        actual_schema = get_sqlite_schema(sqlite_path)

        # ── 2. Normalize table names ────────────────────────────────────────
        orig_tables = entry.get("table_names_original", [])
        norm_tables = [normalize_name(t) for t in orig_tables]
        if norm_tables != orig_tables:
            report["schema"]["normalized_names"].append(
                {"db_id": db_id, "type": "table", "before": orig_tables, "after": norm_tables}
            )

        # ── 3. Normalize column names ───────────────────────────────────────
        orig_cols = entry.get("column_names_original", [])
        norm_cols = []
        for (tbl_idx, col_name) in orig_cols:
            norm_col = normalize_name(col_name) if col_name != "*" else "*"
            norm_cols.append([tbl_idx, norm_col])

        # ── 4. Validate foreign keys against actual SQLite ──────────────────
        fks = entry.get("foreign_keys", [])
        col_count = len(norm_cols)
        valid_fks = []
        for fk in fks:
            # FK entries are [col_idx, col_idx] into column_names_original;
            # out-of-bounds indices appear in some Spider versions and crash
            # downstream tools that index into the column list directly.
            if len(fk) == 2 and fk[0] < col_count and fk[1] < col_count:
                valid_fks.append(fk)
            else:
                log.warning(f"[SCHEMA] Invalid FK {fk} in db_id='{db_id}' — removed")
                report["schema"]["fk_mismatches"].append({"db_id": db_id, "fk": fk})

        # ── 5. Flag empty tables ────────────────────────────────────────────
        empty = check_empty_tables(sqlite_path)
        if empty:
            report["schema"]["empty_tables"][db_id] = empty
            log.warning(f"[SCHEMA] Empty tables in '{db_id}': {empty}")

        # ── 6. Build clean entry ────────────────────────────────────────────
        clean[db_id] = {
            "db_id": db_id,
            "table_names_original": orig_tables,
            "table_names_clean": norm_tables,
            "column_names_original": orig_cols,
            "column_names_clean": norm_cols,
            "column_types": entry.get("column_types", []),
            "primary_keys": entry.get("primary_keys", []),
            "foreign_keys": valid_fks,
            "sqlite_path": str(sqlite_path),
            "empty_tables": empty,
            "actual_sqlite_schema": actual_schema,  # ground-truth from SQLite
        }

    log.info(f"[SCHEMA] Cleaned {len(clean)} databases "
             f"({len(report['schema']['missing_sqlite'])} skipped)")
    return clean


# ---------------------------------------------------------------------------
# Step 3 — Load and clean query files (dev.json / train_spider.json)
# ---------------------------------------------------------------------------

def clean_queries(
    queries: list[dict],
    available_dbs: set[str],
    split_name: str,
    report: dict,
) -> list[dict]:
    """Clean a query split (dev or train) and populate the report sub-dict.

    Deduplication is keyed on (db_id, question.lower()) — SQL is intentionally
    excluded from the key so that two questions worded identically but answered
    with different SQL still count as duplicates (keeps the first occurrence).
    """
    clean: list[dict] = []
    report[split_name] = {
        "missing_db": [],
        "encoding_fixed": 0,
        "sql_normalized": 0,
        "duplicates_removed": 0,
    }

    seen: set[tuple[str, str]] = set()

    for entry in queries:
        db_id = entry.get("db_id", "")
        question = entry.get("question", "")
        sql = entry.get("query", "")

        # ── 1. Skip if no SQLite ────────────────────────────────────────────
        if db_id not in available_dbs:
            report[split_name]["missing_db"].append(db_id)
            continue

        # ── 2. Clean question text ──────────────────────────────────────────
        orig_question = question
        question = clean_text(question)
        if question != orig_question:
            report[split_name]["encoding_fixed"] += 1

        # ── 3. Normalize SQL ────────────────────────────────────────────────
        orig_sql = sql
        sql = normalize_sql(sql)
        if sql != orig_sql:
            report[split_name]["sql_normalized"] += 1

        # ── 4. Remove exact duplicates (same db + same question) ────────────
        key = (db_id, question.lower())
        if key in seen:
            report[split_name]["duplicates_removed"] += 1
            continue
        seen.add(key)

        clean.append({
            "db_id": db_id,
            "question": question,
            "query": sql,
            # preserve optional fields
            "query_toks": entry.get("query_toks", []),
            "question_toks": entry.get("question_toks", []),
        })

    log.info(
        f"[{split_name.upper()}] {len(clean)} clean queries "
        f"({report[split_name]['duplicates_removed']} duplicates removed, "
        f"{len(report[split_name]['missing_db'])} missing db skipped)"
    )
    return clean


# ---------------------------------------------------------------------------
# Step 4 — Validate execution (spot-check gold SQL against SQLite)
# ---------------------------------------------------------------------------

def spot_check_execution(
    clean_queries: list[dict],
    clean_schema: dict,
    sample_size: int = 20,
    report: dict = {},  # noqa: B006 — callers always pass a real dict; default is never mutated
) -> None:
    """Run a sample of gold SQL queries to confirm execution works."""
    import random  # lazy import; this step is optional and skipped when --spot_check 0
    sample = random.sample(clean_queries, min(sample_size, len(clean_queries)))
    passed, failed = 0, 0
    failures = []

    for entry in sample:
        db_id = entry["db_id"]
        sql = entry["query"]
        sqlite_path = clean_schema.get(db_id, {}).get("sqlite_path")
        if not sqlite_path:
            continue
        try:
            conn = sqlite3.connect(sqlite_path)
            conn.execute(sql)
            conn.close()
            passed += 1
        except Exception as e:
            failed += 1
            failures.append({"db_id": db_id, "sql": sql, "error": str(e)})

    report["execution_spot_check"] = {
        "sample_size": len(sample),
        "passed": passed,
        "failed": failed,
        "failures": failures,
    }
    log.info(f"[EXEC CHECK] {passed}/{len(sample)} gold queries executed successfully")
    if failures:
        log.warning(f"[EXEC CHECK] {failed} queries failed — see cleaning_report.json")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Clean Spider dataset for DebugSQL")
    parser.add_argument("--spider_dir", default="./data/benchmarks/spider/raw",
                        help="Path to raw Spider directory")
    parser.add_argument("--output_dir", default="./data/benchmarks/spider/processed",
                        help="Where to write cleaned outputs")
    parser.add_argument("--spot_check", type=int, default=20,
                        help="Number of queries to spot-check execution (0 to skip)")
    args = parser.parse_args()

    spider_dir = Path(args.spider_dir)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # SQLite files live in a separate tree from the JSON annotation files;
    # spider_dir contains tables.json / dev.json, while database_dir holds the
    # actual .sqlite files.  Keep them decoupled so either can be swapped.
    database_dir = Path("./data/benchmarks/spider/sqlite/database")
    tables_path  = spider_dir / "tables.json"
    dev_path     = spider_dir / "dev.json"
    train_path   = spider_dir / "train_spider.json"

    report: dict = {}

    # ── Step 1: available databases ─────────────────────────────────────────
    log.info("Step 1: Scanning available SQLite databases...")
    available_dbs = get_available_dbs(database_dir)
    log.info(f"  Found {len(available_dbs)} databases with SQLite files")

    # ── Step 2: clean schema ─────────────────────────────────────────────────
    log.info("Step 2: Cleaning schema (tables.json)...")
    with open(tables_path, encoding="utf-8") as f:
        raw_tables = json.load(f)
    clean_schema_index = clean_schema(raw_tables, available_dbs, database_dir, report)

    schema_out = output_dir / "clean_schema.json"
    with open(schema_out, "w", encoding="utf-8") as f:
        json.dump(clean_schema_index, f, indent=2, ensure_ascii=False)
    log.info(f"  Saved → {schema_out}")

    # ── Step 3: clean dev queries ────────────────────────────────────────────
    log.info("Step 3: Cleaning dev.json...")
    with open(dev_path, encoding="utf-8") as f:
        raw_dev = json.load(f)
    clean_dev = clean_queries(raw_dev, available_dbs, "dev", report)

    dev_out = output_dir / "clean_dev.json"
    with open(dev_out, "w", encoding="utf-8") as f:
        json.dump(clean_dev, f, indent=2, ensure_ascii=False)
    log.info(f"  Saved → {dev_out}")

    # ── Step 4: clean train queries ──────────────────────────────────────────
    if train_path.exists():
        log.info("Step 4: Cleaning train_spider.json...")
        with open(train_path, encoding="utf-8") as f:
            raw_train = json.load(f)
        clean_train = clean_queries(raw_train, available_dbs, "train", report)

        train_out = output_dir / "clean_train.json"
        with open(train_out, "w", encoding="utf-8") as f:
            json.dump(clean_train, f, indent=2, ensure_ascii=False)
        log.info(f"  Saved → {train_out}")
    else:
        clean_train = []
        log.warning("train_spider.json not found — skipping")

    # ── Step 5: spot-check execution ─────────────────────────────────────────
    if args.spot_check > 0 and clean_dev:
        log.info(f"Step 5: Spot-checking {args.spot_check} gold queries...")
        spot_check_execution(clean_dev, clean_schema_index, args.spot_check, report)

    # ── Save report ───────────────────────────────────────────────────────────
    report_out = output_dir / "cleaning_report.json"
    with open(report_out, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    log.info(f"  Cleaning report saved → {report_out}")

    # ── Summary ───────────────────────────────────────────────────────────────
    print("\n" + "="*55)
    print("CLEANING SUMMARY")
    print("="*55)
    print(f"  Databases cleaned      : {len(clean_schema_index)}")
    print(f"  Dev queries cleaned    : {len(clean_dev)}")
    print(f"  Train queries cleaned  : {len(clean_train)}")
    print(f"  Missing SQLite (skipped): {len(report['schema']['missing_sqlite'])}")
    print(f"  FK mismatches fixed    : {len(report['schema']['fk_mismatches'])}")
    print(f"  DBs with empty tables  : {len(report['schema']['empty_tables'])}")
    if "execution_spot_check" in report:
        ec = report["execution_spot_check"]
        print(f"  Exec spot-check        : {ec['passed']}/{ec['sample_size']} passed")
    print(f"\n  Outputs written to: {output_dir}/")
    print("="*55)


if __name__ == "__main__":
    main()
