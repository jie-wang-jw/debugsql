from __future__ import annotations

from app.config import get_settings
from app.demo_pipeline import generate_plan_for_message
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
    monkeypatch.setenv("KDDCUP_AGENT_API_KEY", "")
    _reset_settings()

    stored = generate_plan_for_message(
        "how many games?",
        "pytest-session",
        {"benchmark": "bird", "dbId": "card_games"},
    )

    assert stored["ir"]["intent_type"] == "agent_trace_error"
    assert stored["plan"]["metadata"]["requires_replan"] is True
    assert stored["plan"]["executable"]["content"] == ""


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


def test_vendored_starter_kit_imports() -> None:
    _ensure_vendor_import_path()

    from data_agent_baseline.agents.react import ReActAgent
    from data_agent_baseline.tools.registry import create_default_tool_registry

    assert ReActAgent.__name__ == "ReActAgent"
    assert len(create_default_tool_registry().specs) >= 8
