from __future__ import annotations

import hashlib
import json
import re
import shutil
import sys
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from pathlib import Path
from typing import Any

from app.benchmark_registry import SQLITE_ROOTS
from app.config import get_settings
from app.nl2ir.schemas import NL2IRRequest, NL2IRResult


BACKEND_ROOT = Path(__file__).resolve().parents[2]
VENDOR_ROOT = BACKEND_ROOT / "vendor" / "kddcup2026-data-agents-starter-kit"
VENDOR_SRC = VENDOR_ROOT / "src"


class KDDCupTraceNL2IRProvider:
    """Runs the vendored KDDCup data-agent baseline and converts its trace to DebugSQL IR."""

    provider_name = "kddcup"

    def generate_ir(self, request: NL2IRRequest) -> NL2IRResult:
        settings = get_settings()
        if not settings.kddcup_agent_api_key:
            return _setup_error_result(
                request,
                "KDDCup NL2IR provider is enabled, but KDDCUP_AGENT_API_KEY is not configured.",
            )
        if not VENDOR_SRC.is_dir():
            return _setup_error_result(
                request,
                f"Vendored KDDCup starter kit was not found at {VENDOR_ROOT}.",
            )

        try:
            _ensure_vendor_import_path()
            result = self._run_agent_with_timeout(request)
            return _trace_to_ir(request, result)
        except Exception as exc:  # noqa: BLE001 - convert provider failures into inspectable IR.
            return _setup_error_result(request, f"KDDCup provider failed: {exc}")

    def _run_agent_with_timeout(self, request: NL2IRRequest) -> dict[str, Any]:
        timeout_seconds = max(1, int(get_settings().kddcup_agent_timeout_seconds))
        executor = ThreadPoolExecutor(max_workers=1)
        future = executor.submit(self._run_agent, request)
        try:
            return future.result(timeout=timeout_seconds)
        except TimeoutError:
            future.cancel()
            raise TimeoutError(f"KDDCup agent timed out after {timeout_seconds} seconds.") from None
        finally:
            executor.shutdown(wait=False, cancel_futures=True)

    def _run_agent(self, request: NL2IRRequest) -> dict[str, Any]:
        from data_agent_baseline.agents.model import OpenAIModelAdapter
        from data_agent_baseline.agents.react import ReActAgent, ReActAgentConfig
        from data_agent_baseline.benchmark.schema import PublicTask, TaskAssets, TaskRecord
        from data_agent_baseline.tools.registry import create_default_tool_registry

        settings = get_settings()
        task = _build_task(request)
        model = OpenAIModelAdapter(
            model=settings.kddcup_agent_model,
            api_base=settings.kddcup_agent_api_base,
            api_key=settings.kddcup_agent_api_key,
            temperature=0.0,
        )
        agent = ReActAgent(
            model=model,
            tools=create_default_tool_registry(),
            config=ReActAgentConfig(max_steps=settings.kddcup_agent_max_steps),
        )
        run_result = agent.run(task).to_dict()
        run_result["task_id"] = task.task_id
        return run_result


def _ensure_vendor_import_path() -> None:
    vendor_src = str(VENDOR_SRC)
    if vendor_src not in sys.path:
        sys.path.insert(0, vendor_src)


def _build_task(request: NL2IRRequest) -> Any:
    from data_agent_baseline.benchmark.schema import PublicTask, TaskAssets, TaskRecord

    settings = get_settings()
    work_root = Path(settings.kddcup_work_dir)
    digest = hashlib.sha1(
        json.dumps(
            {
                "message": request.message,
                "dataset": request.dataset_context,
                "time": time.time(),
            },
            sort_keys=True,
            default=str,
        ).encode("utf-8")
    ).hexdigest()[:10]
    task_id = f"task_{digest}"
    task_dir = work_root / task_id
    context_dir = task_dir / "context"
    context_dir.mkdir(parents=True, exist_ok=False)

    sqlite_path = _sqlite_path(request.dataset_context)
    if sqlite_path and sqlite_path.is_file():
        shutil.copy2(sqlite_path, context_dir / "database.sqlite")

    (context_dir / "schema_context.json").write_text(
        json.dumps(request.schema_context or {}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (task_dir / "task.json").write_text(
        json.dumps(
            {
                "task_id": task_id,
                "difficulty": "debugsql-interactive",
                "question": request.message,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    return PublicTask(
        record=TaskRecord(
            task_id=task_id,
            difficulty="debugsql-interactive",
            question=request.message,
        ),
        assets=TaskAssets(task_dir=task_dir, context_dir=context_dir),
    )


def _sqlite_path(dataset_context: dict[str, Any] | None) -> Path | None:
    benchmark = (dataset_context or {}).get("benchmark")
    db_id = (dataset_context or {}).get("dbId")
    if benchmark not in SQLITE_ROOTS or not db_id:
        return None
    return SQLITE_ROOTS[benchmark] / str(db_id) / f"{db_id}.sqlite"


def _trace_to_ir(request: NL2IRRequest, run_result: dict[str, Any]) -> NL2IRResult:
    steps = list(run_result.get("steps") or [])
    selected_sql = _last_executed_sql(steps)
    answer = run_result.get("answer") if isinstance(run_result.get("answer"), dict) else None
    operations = [_step_to_operation(step) for step in steps]
    provider_status = "success" if run_result.get("succeeded") else "error"
    failure_reason = run_result.get("failure_reason")

    intent_ir = {
        "provider": "kddcup_data_agent",
        "intent_type": "agent_trace_sql" if selected_sql else "agent_trace",
        "raw_query": request.message,
        "selected_sql": selected_sql,
        "table": _infer_table(selected_sql, request.schema_context),
        "target_columns": _answer_columns(answer),
        "group_by": _infer_group_by(selected_sql),
        "filters": [],
        "aggregation": _infer_aggregation(selected_sql),
        "operations": operations,
        "answer": answer,
        "provider_status": provider_status,
        "failure_reason": failure_reason,
        "needs_clarification": False,
    }
    if request.dataset_context:
        intent_ir["dataset_context"] = request.dataset_context

    return NL2IRResult(
        intent_ir=intent_ir,
        selected_sql=selected_sql,
        answer=answer,
        trace={
            "task_id": run_result.get("task_id"),
            "succeeded": bool(run_result.get("succeeded")),
            "failure_reason": failure_reason,
            "steps": operations,
        },
        provider_name="kddcup",
        succeeded=bool(run_result.get("succeeded")),
        error_message=str(failure_reason) if failure_reason else None,
    )


def _step_to_operation(step: dict[str, Any]) -> dict[str, Any]:
    observation = step.get("observation") if isinstance(step.get("observation"), dict) else {}
    return {
        "op": step.get("action"),
        "step_index": step.get("step_index"),
        "thought": step.get("thought"),
        "action_input": _compact(step.get("action_input")),
        "ok": bool(step.get("ok")),
        "observation": _compact(observation),
    }


def _last_executed_sql(steps: list[dict[str, Any]]) -> str | None:
    for step in reversed(steps):
        if step.get("action") != "execute_context_sql":
            continue
        action_input = step.get("action_input")
        if not isinstance(action_input, dict):
            continue
        sql = str(action_input.get("sql") or "").strip()
        if sql:
            return sql
    return None


def _answer_columns(answer: dict[str, Any] | None) -> list[str]:
    if not answer:
        return []
    columns = answer.get("columns")
    return [str(column) for column in columns] if isinstance(columns, list) else []


def _infer_table(sql: str | None, schema_context: dict[str, Any] | None) -> str | None:
    if sql:
        match = re.search(r"\bfrom\s+[`\"]?([a-zA-Z_][\w]*)[`\"]?", sql, flags=re.IGNORECASE)
        if match:
            return match.group(1)
    tables = (schema_context or {}).get("tables") or []
    if tables and isinstance(tables[0], dict):
        return tables[0].get("name")
    return None


def _infer_group_by(sql: str | None) -> list[str]:
    if not sql:
        return []
    match = re.search(r"\bgroup\s+by\s+(.+?)(?:\border\s+by\b|\blimit\b|$)", sql, flags=re.IGNORECASE | re.DOTALL)
    if not match:
        return []
    return [item.strip().strip("`\"") for item in match.group(1).split(",") if item.strip()]


def _infer_aggregation(sql: str | None) -> str | None:
    if not sql:
        return None
    lowered = sql.lower()
    for name in ("count", "sum", "avg", "min", "max"):
        if f"{name}(" in lowered:
            return name
    return None


def _compact(value: Any, *, max_string: int = 1200, max_items: int = 12) -> Any:
    if isinstance(value, str):
        return value[:max_string] + ("..." if len(value) > max_string else "")
    if isinstance(value, list):
        compacted = [_compact(item, max_string=max_string, max_items=max_items) for item in value[:max_items]]
        if len(value) > max_items:
            compacted.append({"truncated": len(value) - max_items})
        return compacted
    if isinstance(value, dict):
        return {
            str(key): _compact(item, max_string=max_string, max_items=max_items)
            for key, item in list(value.items())[:max_items]
        }
    return value


def _setup_error_result(request: NL2IRRequest, message: str) -> NL2IRResult:
    intent_ir = {
        "provider": "kddcup_data_agent",
        "intent_type": "agent_trace_error",
        "raw_query": request.message,
        "selected_sql": None,
        "operations": [],
        "provider_status": "error",
        "failure_reason": message,
        "needs_clarification": False,
    }
    if request.dataset_context:
        intent_ir["dataset_context"] = request.dataset_context
    return NL2IRResult(
        intent_ir=intent_ir,
        selected_sql=None,
        trace={"succeeded": False, "failure_reason": message, "steps": []},
        provider_name="kddcup",
        succeeded=False,
        error_message=message,
    )
