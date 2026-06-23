from __future__ import annotations

import hashlib
import csv
import io
import json
import time
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request, Response
from pydantic import BaseModel
from sqlalchemy import select

from app.auth import ensure_dev_user
from app.benchmark_registry import benchmark_questions, execute_benchmark_sql
from app.database import session_scope
from app.demo_pipeline import generate_plan_for_message
from app.models.auth import User
from app.models.history import ExecutionRun, PlanEdit, RepairCase
from app.persistence import persist_operation_log
from app.request_auth import request_user_id


router = APIRouter(prefix="/evaluation", tags=["evaluation"])

EVALUATION_RUNS: dict[str, dict[str, Any]] = {}


class EvaluationRunRequest(BaseModel):
    benchmark: str
    dbId: str | None = None
    limit: int = 20


class RepairCaseRequest(BaseModel):
    planId: str
    originalRunId: str | None = None
    postEditRunId: str | None = None
    goldSql: str | None = None
    goldResult: dict[str, Any] | None = None


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


@router.post("/repair-cases")
def create_repair_case(payload: RepairCaseRequest, request: Request) -> dict:
    user_id = request_user_id(request)
    case_id = _stable_id("repair_case", {"plan": payload.planId, "time": time.time()})
    with session_scope() as session:
        user = session.get(User, user_id) if user_id else ensure_dev_user(session)
        if not user:
            raise HTTPException(status_code=404, detail="User was not found")
        effective_user_id = user.id
        metrics, original_run_id, post_edit_run_id = _compute_repair_metrics(
            session,
            effective_user_id,
            payload.planId,
            payload.originalRunId,
            payload.postEditRunId,
        )
        repair_case = RepairCase(
            id=case_id,
            user_id=effective_user_id,
            plan_id=payload.planId,
            original_run_id=original_run_id,
            post_edit_run_id=post_edit_run_id,
            gold_sql=payload.goldSql,
            gold_result=payload.goldResult,
            metrics=metrics,
        )
        session.add(repair_case)
        session.flush()
        data = _repair_case_json(repair_case)
    persist_operation_log(
        operation_type="repair_case_evaluated",
        target_type="repair_case",
        target_id=case_id,
        payload=data,
        user_id=user_id,
    )
    return {"success": True, "data": data}


@router.get("/repair-cases/{case_id}")
def get_repair_case(case_id: str, request: Request) -> dict:
    user_id = request_user_id(request)
    with session_scope() as session:
        repair_case = session.get(RepairCase, case_id)
        if not repair_case or (user_id and repair_case.user_id != user_id):
            raise HTTPException(status_code=404, detail=f"Repair case {case_id} was not found")
        return {"success": True, "data": _repair_case_json(repair_case)}


@router.get("/repair-summary")
def get_repair_summary(request: Request) -> dict:
    user_id = request_user_id(request)
    with session_scope() as session:
        user = ensure_dev_user(session) if not user_id else None
        effective_user_id = user_id or user.id
        cases = session.execute(
            select(RepairCase).where(RepairCase.user_id == effective_user_id).order_by(RepairCase.created_at)
        ).scalars().all()
    return {"success": True, "data": _repair_summary(cases)}


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
    if metadata.get("requires_replan"):
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


def _compute_repair_metrics(
    session,
    user_id: str,
    plan_id: str,
    original_run_id: str | None,
    post_edit_run_id: str | None,
) -> tuple[dict[str, Any], str | None, str | None]:
    runs = session.execute(
        select(ExecutionRun)
        .where(ExecutionRun.user_id == user_id, ExecutionRun.plan_id == plan_id, ExecutionRun.run_type == "sql")
        .order_by(ExecutionRun.created_at)
    ).scalars().all()
    original = session.get(ExecutionRun, original_run_id) if original_run_id else next(
        (run for run in runs if _execution_failed(run)),
        None,
    )
    post_edit = session.get(ExecutionRun, post_edit_run_id) if post_edit_run_id else next(
        (run for run in runs if original and run.created_at > original.created_at and _execution_succeeded(run)),
        None,
    )
    if (
        not original
        or not post_edit
        or original.user_id != user_id
        or post_edit.user_id != user_id
        or original.plan_id != plan_id
        or post_edit.plan_id != plan_id
        or post_edit.created_at <= original.created_at
    ):
        return _unavailable_repair_metrics(), getattr(original, "id", None), getattr(post_edit, "id", None)

    edits = session.execute(
        select(PlanEdit)
        .where(
            PlanEdit.user_id == user_id,
            PlanEdit.plan_id == plan_id,
            PlanEdit.created_at >= original.created_at,
            PlanEdit.created_at <= post_edit.created_at,
        )
        .order_by(PlanEdit.created_at)
    ).scalars().all()
    if not edits:
        return _unavailable_repair_metrics(), original.id, post_edit.id

    recovered = _execution_failed(original) and _execution_succeeded(post_edit)
    schema_edits = [edit for edit in edits if _changes_schema_binding(edit.old_data, edit.new_data)]
    return {
        "metricsAvailable": True,
        "debugRecoveryRate": recovered,
        "intentRepairRate": any(edit.node_id == "intent" for edit in edits),
        "editInterventions": len(edits),
        "timeToCorrectMs": max(0, int((post_edit.created_at - original.created_at).total_seconds() * 1000)),
        "schemaLinkingCorrectionRate": recovered if schema_edits else None,
        "schemaLinkingMetricsAvailable": bool(schema_edits),
    }, original.id, post_edit.id


def _execution_failed(run: ExecutionRun) -> bool:
    return run.status in {"error", "failed"} or any(
        isinstance(row, dict) and row.get("error")
        for row in ((run.result_preview or {}).get("rows") or [])
    )


def _execution_succeeded(run: ExecutionRun) -> bool:
    return run.status == "success" and not _execution_failed(run)


def _changes_schema_binding(old_data: dict[str, Any] | None, new_data: dict[str, Any] | None) -> bool:
    binding_keys = {"table", "tableName", "column", "columns", "targetColumns", "groupBy"}
    old_data = old_data or {}
    new_data = new_data or {}
    return any(old_data.get(key) != new_data.get(key) for key in binding_keys if key in old_data or key in new_data)


def _unavailable_repair_metrics() -> dict[str, Any]:
    return {
        "metricsAvailable": False,
        "debugRecoveryRate": None,
        "intentRepairRate": None,
        "editInterventions": None,
        "timeToCorrectMs": None,
        "schemaLinkingCorrectionRate": None,
        "schemaLinkingMetricsAvailable": False,
    }


def _repair_case_json(repair_case: RepairCase) -> dict[str, Any]:
    return {
        "caseId": repair_case.id,
        "planId": repair_case.plan_id,
        "originalRunId": repair_case.original_run_id,
        "postEditRunId": repair_case.post_edit_run_id,
        "goldSql": repair_case.gold_sql,
        "goldResult": repair_case.gold_result,
        "metrics": repair_case.metrics or _unavailable_repair_metrics(),
        "createdAt": repair_case.created_at.isoformat(),
    }


def _repair_summary(cases: list[RepairCase]) -> dict[str, Any]:
    available = [case.metrics or {} for case in cases if (case.metrics or {}).get("metricsAvailable")]
    schema_available = [metrics for metrics in available if metrics.get("schemaLinkingMetricsAvailable")]
    return {
        "totalCases": len(cases),
        "controlledCases": len(available),
        "metricsAvailable": bool(available),
        "debugRecoveryRate": _boolean_rate(available, "debugRecoveryRate"),
        "intentRepairRate": _boolean_rate(available, "intentRepairRate"),
        "averageEditInterventions": _number_average(available, "editInterventions"),
        "averageTimeToCorrectMs": _number_average(available, "timeToCorrectMs"),
        "schemaLinkingCorrectionRate": _boolean_rate(schema_available, "schemaLinkingCorrectionRate"),
        "schemaLinkingMetricsAvailable": bool(schema_available),
    }


def _boolean_rate(items: list[dict[str, Any]], key: str) -> float | None:
    values = [bool(item[key]) for item in items if item.get(key) is not None]
    return sum(values) / len(values) if values else None


def _number_average(items: list[dict[str, Any]], key: str) -> float | None:
    values = [float(item[key]) for item in items if item.get(key) is not None]
    return sum(values) / len(values) if values else None


def _stable_id(prefix: str, payload: dict[str, Any]) -> str:
    digest = hashlib.sha1(json.dumps(payload, sort_keys=True, default=str).encode("utf-8")).hexdigest()[:10]
    return f"{prefix}_{digest}"
