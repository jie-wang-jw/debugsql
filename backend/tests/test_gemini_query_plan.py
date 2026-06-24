from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from app.config import get_settings
from app.conversation.intent_classifier import classify_message
from app.demo_pipeline import PLAN_STORE, generate_gemini_plan_for_message, generate_plan_for_message, update_plan_node
from app.gemini.graph_mapper import gemini_plan_to_graph
from app.gemini.query_plan_parser import QueryPlanParser
from app.gemini.schemas import GeminiConfigError, GeminiQueryPlan, GeminiQueryPlanStep, QueryPlanParseError
from app.gemini.gemini_service import GeminiService
from app.gemini.openai_compatible_service import OpenAICompatibleService


VALID_PLAN_JSON = json.dumps(
    {
        "can_answer": True,
        "answer": "This query finds active customers.",
        "sql": "SELECT id, name FROM customers WHERE active = 1",
        "explanation": "Use the customers table and keep active rows.",
        "assumptions": ["active = 1 means active customers"],
        "tables_used": ["customers"],
        "confidence": 0.9,
        "clarifying_question": None,
        "steps": [
            {"id": 1, "title": "Locate customers", "description": "Use the customers table"},
            {"id": 2, "title": "Filter active", "description": "Keep active rows only"},
        ],
    }
)


class TestQueryPlanParser:
    def test_parses_valid_json(self) -> None:
        plan = QueryPlanParser().parse(VALID_PLAN_JSON)
        assert plan.answer == "This query finds active customers."
        assert plan.sql is not None
        assert len(plan.steps) == 2

    def test_strips_markdown_fence(self) -> None:
        fenced = f"```json\n{VALID_PLAN_JSON}\n```"
        plan = QueryPlanParser().parse(fenced)
        assert plan.answer == "This query finds active customers."

    def test_rejects_forbidden_sql(self) -> None:
        payload = json.dumps(
            {
                "can_answer": True,
                "answer": "Drop tables",
                "sql": "DROP TABLE customers",
                "explanation": "Bad.",
                "assumptions": [],
                "tables_used": [],
                "confidence": 0.1,
                "steps": [{"id": 1, "title": "Drop", "description": "Bad"}],
            }
        )
        with pytest.raises(QueryPlanParseError):
            QueryPlanParser().parse(payload)

    def test_rejects_duplicate_step_ids(self) -> None:
        payload = json.dumps(
            {
                "can_answer": True,
                "answer": "Bad plan",
                "sql": "SELECT 1",
                "explanation": "Bad.",
                "assumptions": [],
                "tables_used": [],
                "confidence": 0.1,
                "steps": [
                    {"id": 1, "title": "A", "description": "One"},
                    {"id": 1, "title": "B", "description": "Duplicate"},
                ],
            }
        )
        with pytest.raises(QueryPlanParseError):
            QueryPlanParser().parse(payload)

    def test_accepts_schema_answer_without_sql(self) -> None:
        payload = json.dumps(
            {
                "mode": "schema_answer",
                "can_answer": True,
                "answer": "The database has cards and sets tables.",
                "sql": None,
                "explanation": "This is a schema-only answer.",
                "assumptions": [],
                "tables_used": [],
                "confidence": 0.9,
                "clarifying_question": None,
                "steps": [],
            }
        )
        plan = QueryPlanParser().parse(payload)
        assert plan.mode == "schema_answer"
        assert plan.sql is None


class TestGraphMapper:
    def test_maps_steps_to_linear_graph(self) -> None:
        plan = GeminiQueryPlan(
            answer="Find active customers",
            sql="SELECT id FROM customers",
            explanation="Use customers.",
            assumptions=[],
            tables_used=["customers"],
            confidence=0.9,
            steps=[
                GeminiQueryPlanStep(id=1, title="Locate customers", description="Step one"),
                GeminiQueryPlanStep(id=2, title="Filter active", description="Step two"),
            ],
        )
        graph = gemini_plan_to_graph(plan, "show active customers")
        node_ids = [node["id"] for node in graph["nodes"]]
        assert node_ids[0] == "intent"
        assert "step_1" in node_ids
        assert "op_sql" in node_ids
        assert "data_result" in node_ids
        assert graph["queryLabel"] == "show active customers"

        sql_node = next(node for node in graph["nodes"] if node["id"] == "op_sql")
        assert sql_node["data"]["operationType"] == "SQL"
        assert sql_node["data"]["fragmentSql"] == "SELECT id FROM customers"


class TestGeminiService:
    def test_missing_api_key_raises_config_error(self, monkeypatch) -> None:
        monkeypatch.setenv("GEMINI_API_KEY", "")
        monkeypatch.setenv("QUERY_PLAN_PROVIDER", "gemini")
        get_settings.cache_clear()
        service = GeminiService()
        with pytest.raises(GeminiConfigError):
            service.generate_query_plan("show customers")

    def test_generate_query_plan_parses_model_response(self, monkeypatch) -> None:
        monkeypatch.setenv("GEMINI_API_KEY", "test-key")
        monkeypatch.setenv("QUERY_PLAN_PROVIDER", "gemini")
        get_settings.cache_clear()

        with patch.object(GeminiService, "_call_gemini", return_value=VALID_PLAN_JSON):
            plan = GeminiService().generate_query_plan("show active customers")
        assert plan.answer == "This query finds active customers."
        assert plan.sql is not None


class TestOpenAICompatibleService:
    def test_missing_openai_compatible_config_raises_config_error(self, monkeypatch) -> None:
        monkeypatch.setenv("QUERY_PLAN_PROVIDER", "openai_compatible")
        monkeypatch.setenv("LLM_API_BASE_URL", "")
        monkeypatch.setenv("LLM_API_KEY", "")
        get_settings.cache_clear()
        service = OpenAICompatibleService()
        with pytest.raises(GeminiConfigError):
            service.generate_query_plan("show customers")

    def test_generate_query_plan_parses_openai_compatible_response(self, monkeypatch) -> None:
        monkeypatch.setenv("QUERY_PLAN_PROVIDER", "openai_compatible")
        monkeypatch.setenv("LLM_API_BASE_URL", "https://example.test/v1")
        monkeypatch.setenv("LLM_API_KEY", "test-key")
        monkeypatch.setenv("LLM_MODEL", "qwen-plus")
        get_settings.cache_clear()

        with patch.object(OpenAICompatibleService, "_call_openai_compatible", return_value=VALID_PLAN_JSON):
            plan = OpenAICompatibleService().generate_query_plan("show active customers")
        assert plan.answer == "This query finds active customers."
        assert plan.sql is not None


class TestGeminiPipelineIntegration:
    def test_generate_gemini_plan_for_message_stores_plan(self, monkeypatch) -> None:
        monkeypatch.setenv("GEMINI_API_KEY", "test-key")
        monkeypatch.setenv("QUERY_PLAN_PROVIDER", "gemini")
        get_settings.cache_clear()
        PLAN_STORE.clear()

        plan = GeminiQueryPlan(
            answer="Count rows",
            sql="SELECT COUNT(*) AS total FROM cards",
            explanation="Count all cards.",
            assumptions=[],
            tables_used=["cards"],
            confidence=0.9,
            steps=[GeminiQueryPlanStep(id=1, title="Count", description="Count all rows")],
        )

        with patch.object(GeminiService, "generate_query_plan", return_value=plan):
            stored = generate_gemini_plan_for_message(
                "how many cards?",
                session_id="session-1",
                dataset_context={"benchmark": "spider", "dbId": "card_games"},
            )

        plan_id = stored["plan"]["plan_id"]
        assert plan_id in PLAN_STORE
        assert stored["plan"]["metadata"]["template"] == "gemini"
        assert stored["plan"]["executable"]["content"].startswith("SELECT")

    def test_generate_plan_falls_back_when_gemini_fails(self, monkeypatch) -> None:
        monkeypatch.setenv("GEMINI_API_KEY", "test-key")
        monkeypatch.setenv("QUERY_PLAN_PROVIDER", "gemini")
        monkeypatch.setenv("NL2IR_PROVIDER", "stub")
        get_settings.cache_clear()
        PLAN_STORE.clear()

        with patch.object(
            GeminiService,
            "generate_query_plan",
            side_effect=QueryPlanParseError("bad json"),
        ):
            stored = generate_plan_for_message(
                "show total sales in texas grouped by store",
                session_id="session-2",
            )

        assert stored["plan"]["plan_id"] in PLAN_STORE

    def test_gemini_sql_node_edit_updates_executable(self, monkeypatch) -> None:
        monkeypatch.setenv("GEMINI_API_KEY", "test-key")
        monkeypatch.setenv("QUERY_PLAN_PROVIDER", "gemini")
        get_settings.cache_clear()
        PLAN_STORE.clear()

        plan = GeminiQueryPlan(
            answer="Count rows",
            sql="SELECT COUNT(*) AS total FROM cards",
            explanation="Count all cards.",
            assumptions=[],
            tables_used=["cards"],
            confidence=0.9,
            steps=[GeminiQueryPlanStep(id=1, title="Count", description="Count all rows")],
        )
        with patch.object(GeminiService, "generate_query_plan", return_value=plan):
            stored = generate_gemini_plan_for_message("how many cards?", session_id="session-3")

        plan_id = stored["plan"]["plan_id"]
        graph = update_plan_node(
            plan_id,
            "op_sql",
            {
                "kind": "operation",
                "operationType": "SQL",
                "label": "Generated SQL",
                "detail": "SELECT COUNT(*) AS total FROM cards",
                "fragmentSql": "SELECT COUNT(*) AS edited FROM cards",
            },
        )
        assert graph is not None
        assert PLAN_STORE[plan_id]["plan"]["executable"]["content"] == "SELECT COUNT(*) AS edited FROM cards"


class TestIntentClassifier:
    def test_routes_unmatched_benchmark_question_when_gemini_configured(self, monkeypatch) -> None:
        monkeypatch.setenv("GEMINI_API_KEY", "test-key")
        monkeypatch.setenv("QUERY_PLAN_PROVIDER", "gemini")
        monkeypatch.setenv("NL2IR_PROVIDER", "stub")
        get_settings.cache_clear()

        intent = classify_message(
            "list every legendary creature card name",
            {"benchmark": "spider", "dbId": "card_games"},
        )
        assert intent.intent_type == "benchmark_query"
        assert intent.requires_plan is False

    def test_routes_unmatched_benchmark_question_when_openai_compatible_configured(self, monkeypatch) -> None:
        monkeypatch.setenv("QUERY_PLAN_PROVIDER", "openai_compatible")
        monkeypatch.setenv("LLM_API_BASE_URL", "https://example.test/v1")
        monkeypatch.setenv("LLM_API_KEY", "test-key")
        monkeypatch.setenv("NL2IR_PROVIDER", "stub")
        get_settings.cache_clear()

        intent = classify_message(
            "list every legendary creature card name",
            {"benchmark": "spider", "dbId": "card_games"},
        )
        assert intent.intent_type == "benchmark_query"
        assert intent.requires_plan is False

    def test_unsupported_when_gemini_not_configured(self, monkeypatch) -> None:
        monkeypatch.setenv("GEMINI_API_KEY", "")
        monkeypatch.setenv("QUERY_PLAN_PROVIDER", "gemini")
        monkeypatch.setenv("LLM_API_BASE_URL", "")
        monkeypatch.setenv("LLM_API_KEY", "")
        monkeypatch.setenv("NL2IR_PROVIDER", "stub")
        get_settings.cache_clear()

        intent = classify_message(
            "list every legendary creature card name",
            {"benchmark": "spider", "dbId": "card_games"},
        )
        assert intent.intent_type == "unsupported"

    def test_refine_terms_are_not_blocked_as_plan_edit(self, monkeypatch) -> None:
        monkeypatch.setenv("QUERY_PLAN_PROVIDER", "openai_compatible")
        monkeypatch.setenv("LLM_API_BASE_URL", "https://example.test/v1")
        monkeypatch.setenv("LLM_API_KEY", "test-key")
        get_settings.cache_clear()

        for message in ["limit to 10", "sort by name", "add filter for black border"]:
            intent = classify_message(message, {"benchmark": "bird", "dbId": "card_games"})
            assert intent.intent_type == "benchmark_query"
