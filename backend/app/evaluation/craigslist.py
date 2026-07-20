from __future__ import annotations

import hashlib
import json
import math
import re
import sqlite3
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from app.config import get_settings
from app.craigslist.registry import craigslist_root
from app.craigslist.resolver import CraigslistSemanticResolver
from app.semantic_index.store import craigslist_index_dir, load_manifest
from app.semantic_sql import rewrite_semantic_sql
from app.semantic_sql.resolver import SemanticResolver
from app.semantic_sql.schemas import NLFilterOp, ResolvedMatch
from app.tools.connectors.craigslist import _SEMANTIC_TABLES, _TABLE_COLUMNS, _load_tables


_REPO_ROOT = Path(__file__).resolve().parents[3]


def evaluation_root() -> Path:
    root = Path(get_settings().craigslist_evaluation_dir)
    return root if root.is_absolute() else _REPO_ROOT / root


def load_annotations(name: str) -> list[dict]:
    """Evaluation-only annotation loader. Runtime modules must not import this."""
    if name not in {"images", "titles"}:
        raise ValueError("annotation name must be images or titles")
    filename = (
        "craigslist_imgs_label.json" if name == "images"
        else "craigslist_furnitures_title_label.json"
    )
    payload = json.loads((evaluation_root() / filename).read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError(f"Invalid Craigslist {name} annotations")
    return payload


def split_for_id(asset_id: str) -> str:
    bucket = int(hashlib.sha256(asset_id.encode()).hexdigest()[:8], 16) % 100
    return "calibration" if bucket < 20 else "test"


def retrieval_metrics(
    ranked_ids: list[str], relevant_ids: set[str], *, k: int = 10
) -> dict[str, float]:
    top = ranked_ids[:k]
    hits = [1 if item in relevant_ids else 0 for item in top]
    retrieved = set(ranked_ids)
    true_positive = len(retrieved & relevant_ids)
    precision = true_positive / len(retrieved) if retrieved else 0.0
    recall = true_positive / len(relevant_ids) if relevant_ids else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    recall_at_k = sum(hits) / len(relevant_ids) if relevant_ids else 0.0
    dcg = sum(hit / math.log2(index + 2) for index, hit in enumerate(hits))
    ideal = sum(1 / math.log2(index + 2) for index in range(min(k, len(relevant_ids))))
    return {
        "precision": precision,
        "recall": recall,
        "f1": f1,
        f"recallAt{k}": recall_at_k,
        f"ndcgAt{k}": dcg / ideal if ideal else 0.0,
    }


def relative_aggregate_error(actual: float, expected: float) -> float:
    if expected == 0:
        return 0.0 if actual == 0 else float("inf")
    return abs(actual - expected) / abs(expected)


def ensure_test_only(ids: Iterable[str]) -> None:
    invalid = [asset_id for asset_id in ids if split_for_id(asset_id) != "test"]
    if invalid:
        raise ValueError("Evaluation results contain calibration IDs")


@dataclass
class EvaluationQuery:
    query_id: str
    sql: str


class CachedResolver:
    def __init__(self, delegate: SemanticResolver) -> None:
        self.delegate = delegate
        self.cache: dict[tuple[str, str, str], list[ResolvedMatch]] = {}

    def resolve_filter(self, op: NLFilterOp) -> list[ResolvedMatch]:
        key = (op.table, op.column, _normalize(op.predicate))
        if key not in self.cache:
            self.cache[key] = self.delegate.resolve_filter(op)
        return self.cache[key]


class AnnotationResolver:
    """Hidden-label resolver used only to calculate expected test results."""

    def __init__(self) -> None:
        self.images = load_annotations("images")
        self.titles = load_annotations("titles")

    def resolve_filter(self, op: NLFilterOp) -> list[ResolvedMatch]:
        rows = self.images if op.table == "images" else self.titles
        id_field = "img" if op.table == "images" else "aid"
        matches = [
            str(row[id_field])
            for row in rows
            if id_field in row
            and split_for_id(str(row[id_field])) == "test"
            and _annotation_matches(row, op.predicate)
        ]
        return [ResolvedMatch(key=item_id, score=1.0) for item_id in matches]


def load_benchmark_queries() -> list[EvaluationQuery]:
    text = (craigslist_root() / "queries.sql").read_text(encoding="utf-8")
    return [
        EvaluationQuery(query_id=f"Q{match.group(1)}", sql=match.group(2).strip())
        for match in re.finditer(r"--\s*Q(\d+)\s*(.*?;)", text, flags=re.DOTALL | re.IGNORECASE)
    ]


def run_benchmark(mode: str, output_path: Path | None = None) -> dict:
    if mode not in {"clip-only", "clip+vlm"}:
        raise ValueError("mode must be clip-only or clip+vlm")
    settings = get_settings()
    actual = CraigslistSemanticResolver(use_vision=mode == "clip+vlm")
    predicted = CachedResolver(actual)
    expected = CachedResolver(AnnotationResolver())
    started = time.perf_counter()
    query_results = []

    for query in load_benchmark_queries():
        predicted_rewrite = rewrite_semantic_sql(
            query.sql,
            resolver=predicted,
            table_columns=_TABLE_COLUMNS,
            semantic_tables=_SEMANTIC_TABLES,
        )
        expected_rewrite = rewrite_semantic_sql(
            query.sql,
            resolver=expected,
            table_columns=_TABLE_COLUMNS,
            semantic_tables=_SEMANTIC_TABLES,
        )
        actual_rows = _execute(predicted_rewrite.sql)
        expected_rows = _execute(expected_rewrite.sql)
        query_results.append({
            "queryId": query.query_id,
            "semanticSql": query.sql,
            "generatedSql": predicted_rewrite.sql,
            **_compare_results(query.sql, actual_rows, expected_rows),
        })

    operator_results = []
    for (table, column, predicate), matches in predicted.cache.items():
        expected_matches = expected.cache.get((table, column, predicate), [])
        ranked = [match.key for match in matches if split_for_id(match.key) == "test"]
        relevant = {match.key for match in expected_matches}
        operator_results.append({
            "table": table,
            "column": column,
            "predicate": predicate,
            "retrievedCount": len(ranked),
            "relevantCount": len(relevant),
            **retrieval_metrics(ranked, relevant, k=10),
        })

    aggregate_errors = [
        result["relativeAggregateError"]
        for result in query_results
        if result["kind"] == "aggregate" and math.isfinite(result["relativeAggregateError"])
    ]
    image_reranker = actual.image.reranker
    manifest_path = craigslist_index_dir() / "manifest.json"
    report = {
        "benchmark": "craigslist",
        "mode": mode,
        "createdAt": datetime.now(timezone.utc).isoformat(),
        "configuration": {
            "imageModel": f"{settings.clip_model}/{settings.clip_pretrained}",
            "textModel": settings.text_embedding_model,
            "visionProvider": settings.vision_provider if mode == "clip+vlm" else None,
            "visionModel": settings.vision_model if mode == "clip+vlm" else None,
            "candidateCount": settings.clip_candidate_count,
            "rerankCount": settings.vision_rerank_count if mode == "clip+vlm" else 0,
            "scoreCutoff": settings.semantic_sql_score_cutoff,
            "split": "sha256(asset_id) % 100; calibration < 20, test >= 20",
        },
        "indexManifest": load_manifest(),
        "indexManifestSha256": _file_sha256(manifest_path),
        "queryCount": len(query_results),
        "selectionExecutionAccuracy": _mean([
            float(result["resultCorrect"])
            for result in query_results if result["kind"] == "selection"
        ]),
        "meanRelativeAggregateError": _mean(aggregate_errors),
        "latencyMs": round((time.perf_counter() - started) * 1000, 2),
        "visionRequestCount": image_reranker.request_count,
        "visionScoredImageCount": image_reranker.scored_image_count,
        "estimatedProviderCostUsd": None,
        "operatorMetrics": operator_results,
        "queryResults": query_results,
    }
    if output_path is not None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


def _execute(sql: str) -> list[dict]:
    with sqlite3.connect(":memory:") as connection:
        connection.row_factory = sqlite3.Row
        _load_tables(connection)
        return [dict(row) for row in connection.execute(sql).fetchall()]


def _compare_results(original_sql: str, actual: list[dict], expected: list[dict]) -> dict:
    from sqlglot import exp, parse_one

    tree = parse_one(original_sql, read="sqlite")
    aggregate = any(expression.find(exp.AggFunc) for expression in tree.expressions)
    if aggregate:
        actual_value = _first_value(actual)
        expected_value = _first_value(expected)
        error = relative_aggregate_error(float(actual_value or 0), float(expected_value or 0))
        return {
            "kind": "aggregate",
            "actual": actual_value,
            "expected": expected_value,
            "relativeAggregateError": error,
            "resultCorrect": error == 0,
        }
    actual_set = {_row_key(row) for row in actual}
    expected_set = {_row_key(row) for row in expected}
    return {
        "kind": "selection",
        "actualRowCount": len(actual_set),
        "expectedRowCount": len(expected_set),
        "resultCorrect": actual_set == expected_set,
    }


def _annotation_matches(row: dict, predicate: str) -> bool:
    searchable = " ".join(_flatten(row)).lower()
    terms = [term for term in re.findall(r"[a-z0-9]+", predicate.lower()) if len(term) > 1]
    return bool(terms) and all(term in searchable for term in terms)


def _flatten(value) -> list[str]:
    if isinstance(value, dict):
        return [item for child in value.values() for item in _flatten(child)]
    if isinstance(value, list):
        return [item for child in value for item in _flatten(child)]
    return [str(value)]


def _normalize(value: str) -> str:
    return " ".join(value.lower().split())


def _row_key(row: dict) -> str:
    ignored = {"score", "asset_id"} | {key for key in row if key.startswith("nlf_")}
    payload = {key: value for key, value in row.items() if key not in ignored}
    return json.dumps(payload, sort_keys=True, default=str)


def _first_value(rows: list[dict]):
    return next(iter(rows[0].values()), None) if rows else None


def _file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else ""


def _mean(values: list[float]) -> float | None:
    return sum(values) / len(values) if values else None
