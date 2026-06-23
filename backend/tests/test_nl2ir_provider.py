from __future__ import annotations

from app.config import get_settings
from app.demo_pipeline import generate_plan_for_message, get_plan_graph, merge_plan_nodes
from app.evaluation_routes import _summarize_cases


def _reset_settings() -> None:
    get_settings.cache_clear()


def test_fastapi_app_imports() -> None:
    from app.main import app

    assert app.title == "DebugSQL Backend"


def test_stub_provider_keeps_schema_fallback(monkeypatch) -> None:
    monkeypatch.setenv("NL2IR_PROVIDER", "stub")
    monkeypatch.setenv("QUERY_PLAN_PROVIDER", "stub")
    monkeypatch.setenv("GEMINI_API_KEY", "")
    _reset_settings()

    stored = generate_plan_for_message(
        "show cards",
        "pytest-session",
        {"benchmark": "bird", "dbId": "card_games"},
    )

    # Stub NL2IR provider should still allow the schema-aware fallback SQL path.
    assert stored["plan"]["metadata"]["template"] == "schema_fallback_sql"
    assert stored["plan"]["executable"]["content"]


def test_default_runtime_uses_stub_provider(monkeypatch) -> None:
    monkeypatch.delenv("NL2IR_PROVIDER", raising=False)
    _reset_settings()

    assert get_settings().nl2ir_provider == "stub"


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


