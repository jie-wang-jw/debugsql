from __future__ import annotations

import hashlib
import csv
import io
import json
import time
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request, Response
from pydantic import BaseModel

from app.benchmark_registry import benchmark_questions, execute_benchmark_sql
from app.demo_pipeline import generate_plan_for_message
from app.persistence import persist_operation_log
from app.request_auth import request_user_id


router = APIRouter(prefix="/evaluation", tags=["evaluation"])

EVALUATION_RUNS: dict[str, dict[str, Any]] = {}


class EvaluationRunRequest(BaseModel):
    benchmark: str
    dbId: str | None = None
    limit: int = 20


@router.post("/run")
def run_evaluation(payload: EvaluationRunRequest, request: Request) -> dict:
    user_id = request_user_id(request)
    limit = max(1, min(int(payload.limit), 100))
    examples = benchmark_questions(payload.benchmark, payload.dbId, limit)
    run_id = _stable_id(
        "eval",
        {
            "benchmark": payload.benchmark,
            "dbId": payload.dbId,
            "limit": limit,
            "time": time.time(),
        },
    )
    cases = [_evaluate_case(item, run_id) for item in examples]
    summary = _summarize_cases(cases)
    result = {
        "runId": run_id,
        "benchmark": payload.benchmark,
        "dbId": payload.dbId,
        "limit": limit,
        "summary": summary,
        "cases": cases,
        "createdAt": time.time(),
    }
    EVALUATION_RUNS[run_id] = result
    persist_operation_log(
        operation_type="evaluation_run",
        target_type="evaluation",
        target_id=run_id,
        payload={
            "benchmark": payload.benchmark,
            "dbId": payload.dbId,
            "limit": limit,
            "summary": summary,
        },
        user_id=user_id,
    )
    return {"success": True, "data": result}


@router.get("/runs/{run_id}")
def get_evaluation_run(run_id: str) -> dict:
    result = EVALUATION_RUNS.get(run_id)
    if not result:
        return {"success": False, "data": None, "error": f"Evaluation run {run_id} was not found in memory."}
    return {"success": True, "data": result}


@router.get("/runs/{run_id}/export")
def export_evaluation_run(
    run_id: str,
    format: str = Query(default="json", pattern="^(json|csv)$"),
):
    result = EVALUATION_RUNS.get(run_id)
    if not result:
        raise HTTPException(status_code=404, detail=f"Evaluation run {run_id} was not found in memory.")
    if format == "csv":
        return Response(
            content=_evaluation_cases_csv(result.get("cases") or []),
            media_type="text/csv",
            headers={"Content-Disposition": f'attachment; filename="{run_id}-cases.csv"'},
        )
    return {"success": True, "data": result}


def _evaluate_case(item: dict[str, Any], run_id: str) -> dict[str, Any]:
    benchmark = item["benchmark"]
    db_id = item["db_id"]
    question = item["question"]
    gold_sql = item.get("query") or ""
    started = time.perf_counter()
    case_id = _stable_id("eval_case", {"run": run_id, "benchmark": benchmark, "db": db_id, "q": question})
    try:
        stored = generate_plan_for_message(
            question,
            f"{run_id}-{case_id}",
            {"benchmark": benchmark, "dbId": db_id},
        )
        generated_sql = ((stored.get("plan") or {}).get("executable") or {}).get("content") or ""
        generated_result = execute_benchmark_sql(benchmark, db_id, generated_sql) if generated_sql else None
        gold_result = execute_benchmark_sql(benchmark, db_id, gold_sql) if gold_sql else None
        execution_correct = bool(
            generated_result
            and gold_result
            and not _has_execution_error(generated_result)
            and not _has_execution_error(gold_result)
            and _normalized_rows(generated_result.get("rows")) == _normalized_rows(gold_result.get("rows"))
        )
        error_type = None if execution_correct else _classify_failure(stored, generated_result)
        return {
            "caseId": case_id,
            "benchmark": benchmark,
            "dbId": db_id,
            "question": question,
            "planId": (stored.get("plan") or {}).get("plan_id"),
            "generatedSql": generated_sql,
            "goldSql": gold_sql,
            "firstPassExecutionAccuracy": execution_correct,
            "debugRecoveryRate": None,
            "intentRepairRate": None,
            "editInterventions": None,
            "timeToCorrectMs": int((time.perf_counter() - started) * 1000),
            "errorType": error_type,
        }
    except Exception as exc:  # noqa: BLE001 - evaluation must continue across bad cases.
        return {
            "caseId": case_id,
            "benchmark": benchmark,
            "dbId": db_id,
            "question": question,
            "generatedSql": "",
            "goldSql": gold_sql,
            "firstPassExecutionAccuracy": False,
            "debugRecoveryRate": None,
            "intentRepairRate": None,
            "editInterventions": None,
            "timeToCorrectMs": int((time.perf_counter() - started) * 1000),
            "errorType": type(exc).__name__,
            "errorMessage": str(exc),
        }


def _summarize_cases(cases: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(cases)
    correct = sum(1 for item in cases if item.get("firstPassExecutionAccuracy"))
    error_counts: dict[str, int] = {}
    for item in cases:
        error_type = item.get("errorType")
        if error_type:
            error_counts[error_type] = error_counts.get(error_type, 0) + 1
    return {
        "totalCases": total,
        "firstPassExecutionAccuracy": correct / total if total else 0.0,
        "debugRecoveryRate": None,
        "intentRepairRate": None,
        "schemaLinkingCorrectionRate": None,
        "averageEditInterventions": None,
        "repairMetricsAvailable": False,
        "repairMetricsNote": "DRR, IRR, EI, and schema-linking correction require controlled edit scenarios.",
        "averageTimeToCorrectMs": (
            sum(int(item.get("timeToCorrectMs") or 0) for item in cases) / total if total else 0.0
        ),
        "errorTypeDistribution": error_counts,
    }


def _classify_failure(stored: dict[str, Any], result: dict[str, Any] | None) -> str:
    metadata = (stored.get("plan") or {}).get("metadata") or {}
    ir = stored.get("ir") or {}
    if metadata.get("requires_replan") or ir.get("intent_type") == "agent_trace_error":
        return "planning"
    if result and _has_execution_error(result):
        return "execution"
    generated_sql = ((stored.get("plan") or {}).get("executable") or {}).get("content")
    return "sql_generation" if generated_sql else "planning"


def _has_execution_error(result: dict[str, Any]) -> bool:
    return any(row.get("error") for row in result.get("rows") or [] if isinstance(row, dict))


def _normalized_rows(rows: Any) -> list[str]:
    return sorted(json.dumps(row, sort_keys=True, default=str) for row in (rows or []))


def _evaluation_cases_csv(cases: list[dict[str, Any]]) -> str:
    buffer = io.StringIO()
    fieldnames = [
        "caseId",
        "benchmark",
        "dbId",
        "question",
        "planId",
        "firstPassExecutionAccuracy",
        "errorType",
        "timeToCorrectMs",
        "generatedSql",
        "goldSql",
    ]
    writer = csv.DictWriter(buffer, fieldnames=fieldnames)
    writer.writeheader()
    for item in cases:
        writer.writerow({key: item.get(key) for key in fieldnames})
    return buffer.getvalue()


def _stable_id(prefix: str, payload: dict[str, Any]) -> str:
    digest = hashlib.sha1(json.dumps(payload, sort_keys=True, default=str).encode("utf-8")).hexdigest()[:10]
    return f"{prefix}_{digest}"
