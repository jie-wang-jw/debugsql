from __future__ import annotations

from app.config import get_settings
from app.demo_pipeline import generate_plan_for_message, get_plan_graph, merge_plan_nodes
from app.evaluation_routes import _summarize_cases
from app.planning.internal_provider import InternalIRToPlanProvider
from app.planning.schemas import PlanningRequest
from app.nl2ir.kddcup_provider import _ensure_vendor_import_path, _trace_to_ir
from app.nl2ir.schemas import NL2IRRequest


def _reset_settings() -> None:
    get_settings.cache_clear()


def test_fastapi_app_imports() -> None:
    from app.main import app

    assert app.title == "DebugSQL Backend"


def test_stub_provider_keeps_schema_fallback(monkeypatch) -> None:
    monkeypatch.setenv("NL2IR_PROVIDER", "stub")
    _reset_settings()

    stored = generate_plan_for_message(
        "how many games?",
        "pytest-session",
        {"benchmark": "bird", "dbId": "card_games"},
    )

    assert stored["ir"]["provider"] == "simple_schema_fallback"
    assert stored["plan"]["executable"]["content"]


def test_kddcup_provider_without_key_returns_inspectable_error_ir(monkeypatch) -> None:
    monkeypatch.setenv("NL2IR_PROVIDER", "kddcup")
    monkeypatch.delenv("KDDCUP_AGENT_API_KEY", raising=False)
    monkeypatch.setenv("KDDCUP_LLM_API_KEY", "")
    _reset_settings()

    stored = generate_plan_for_message(
        "how many games?",
        "pytest-session",
        {"benchmark": "bird", "dbId": "card_games"},
    )

    assert stored["ir"]["intent_type"] == "agent_trace_error"
    assert stored["plan"]["metadata"]["requires_replan"] is True
    assert stored["plan"]["executable"]["content"] == ""


def test_kddcup_llm_api_key_accepts_legacy_alias(monkeypatch) -> None:
    monkeypatch.delenv("KDDCUP_LLM_API_KEY", raising=False)
    monkeypatch.setenv("KDDCUP_AGENT_API_KEY", "legacy-secret")
    _reset_settings()

    assert get_settings().kddcup_llm_api_key == "legacy-secret"


def test_trace_to_ir_extracts_last_executed_sql() -> None:
    trace = {
        "task_id": "task_1",
        "succeeded": True,
        "answer": {"columns": ["n"], "rows": [[1]]},
        "steps": [
            {
                "step_index": 1,
                "thought": "run sql",
                "action": "execute_context_sql",
                "action_input": {
                    "path": "database.sqlite",
                    "sql": "SELECT COUNT(*) AS n FROM cards",
                },
                "observation": {"ok": True},
                "ok": True,
            }
        ],
    }

    result = _trace_to_ir(
        NL2IRRequest(
            message="how many cards?",
            schema_context={"tables": [{"name": "cards"}]},
        ),
        trace,
    )

    assert result.intent_ir["intent_type"] == "agent_trace_sql"
    assert result.selected_sql == "SELECT COUNT(*) AS n FROM cards"
    assert len(result.intent_ir["operations"]) == 1


def test_internal_planner_builds_sql_trace_operation_nodes() -> None:
    plan = InternalIRToPlanProvider().generate_plan(
        PlanningRequest(
            intent_ir={
                "provider": "kddcup_data_agent",
                "intent_type": "agent_trace_sql",
                "selected_sql": (
                    "SELECT store_id, SUM(amount) AS total_sales "
                    "FROM sales_transactions "
                    "WHERE state = 'TX' "
                    "GROUP BY store_id "
                    "ORDER BY total_sales DESC "
                    "LIMIT 2"
                ),
                "table": "sales_transactions",
            },
            schema_context={"tables": [{"name": "sales_transactions"}]},
        )
    )

    operation_types = [node.operation_type for node in plan.nodes if node.node_type == "operation"]

    assert plan.metadata["provider"] == "internal"
    assert operation_types == ["scan", "filter", "group_by", "aggregate", "sort", "limit", "execute_sql"]


def test_merge_adjacent_operation_nodes_updates_graph(monkeypatch) -> None:
    monkeypatch.setenv("NL2IR_PROVIDER", "stub")
    _reset_settings()
    stored = generate_plan_for_message("rank stores by revenue in the last 30 days", "pytest-session")

    graph = merge_plan_nodes(stored["plan"]["plan_id"], ["op_group_by", "op_aggregate"])

    assert graph is not None
    assert graph["lastEditResult"]["status"] == "graph_updated"
    assert graph["lastEditResult"]["mergedNodeIds"] == ["op_group_by", "op_aggregate"]
    assert get_plan_graph(stored["plan"]["plan_id"])["nodes"]


def test_evaluation_summary_reports_accuracy_and_errors() -> None:
    summary = _summarize_cases(
        [
            {"firstPassExecutionAccuracy": True, "timeToCorrectMs": 10},
            {"firstPassExecutionAccuracy": False, "timeToCorrectMs": 30, "errorType": "planning"},
        ]
    )

    assert summary["totalCases"] == 2
    assert summary["firstPassExecutionAccuracy"] == 0.5
    assert summary["errorTypeDistribution"] == {"planning": 1}


def test_vendored_starter_kit_imports() -> None:
    _ensure_vendor_import_path()

    from data_agent_baseline.agents.react import ReActAgent
    from data_agent_baseline.tools.registry import create_default_tool_registry

    assert ReActAgent.__name__ == "ReActAgent"
    assert len(create_default_tool_registry().specs) >= 8
