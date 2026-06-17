from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Any

from app.benchmark_registry import find_benchmark_gold_sql, get_schema_context
from app.config import get_settings
from app.gemini import GeminiService, OpenAICompatibleService
from app.gemini.schemas import GeminiConfigError, QueryPlanParseError
from app.simple_nl2sql import build_simple_schema_nl2sql
from app.tools.schemas import DatasetContext

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ResolvedSQL:
    sql: str | None
    explanation: str
    provider: str
    answer: str | None = None
    assumptions: tuple[str, ...] = ()
    tables_used: tuple[str, ...] = ()
    confidence: float | None = None
    clarifying_question: str | None = None


def resolve_sql_for_message(
    message: str,
    context: DatasetContext,
    schema: dict[str, Any] | None = None,
) -> ResolvedSQL:
    """Resolve NL questions to SQL using the same provider priority as the plan pipeline."""
    if schema is None and context.dbType == "sqlite_benchmark" and context.benchmark and context.dbId:
        schema = get_schema_context(context.benchmark, context.dbId)

    if _should_use_llm():
        resolved = _resolve_with_llm(message, schema)
        if resolved:
            return resolved

    if context.benchmark and context.dbId:
        gold_sql = find_benchmark_gold_sql(context.benchmark, context.dbId, message)
        if gold_sql:
            return ResolvedSQL(
                sql=gold_sql,
                explanation=f"Matched a known {context.benchmark} benchmark question.",
                provider="gold_sql",
                answer="I found a matching benchmark question and prepared its reference SQL.",
            )

    if schema:
        fallback = build_simple_schema_nl2sql(message, schema)
        if fallback:
            has_filters = bool(fallback.intent_ir.get("filters"))
            if not needs_real_nl2sql(message) or has_filters:
                return ResolvedSQL(
                    sql=fallback.sql,
                    explanation=fallback.explanation,
                    provider="simple_fallback",
                    answer="I prepared a simple schema-aware SQL query for this question.",
                )

    return ResolvedSQL(sql=None, explanation="", provider="none")


def needs_real_nl2sql(message: str) -> bool:
    """Return True when a single-table demo fallback would likely misread the question."""
    text = message.lower().strip()
    if re.search(r"""['"].+['"]""", message):
        return True
    if re.search(r"\b(where|named|called|specific|filter|join|whose|belonging to)\b", text):
        return True
    if re.search(r"\b(is|are|equals?|equal to)\s+[\w]", text):
        return True
    if re.search(r"\b(by|for|from|with)\s+(the\s+)?(artist|author|customer|user|player|team)\b", text):
        return True
    return False


def _should_use_llm() -> bool:
    settings = get_settings()
    provider = settings.query_plan_provider.strip().lower()
    if provider == "gemini":
        return bool(settings.gemini_api_key.strip())
    if provider == "openai_compatible":
        return bool(settings.llm_api_key.strip() and settings.llm_api_base_url.strip())
    return False


def _resolve_with_llm(message: str, schema: dict[str, Any] | None) -> ResolvedSQL | None:
    provider = get_settings().query_plan_provider.strip().lower()
    if provider == "openai_compatible":
        service = OpenAICompatibleService()
    elif provider == "gemini":
        service = GeminiService()
    else:
        logger.warning("Unsupported QUERY_PLAN_PROVIDER=%s; skipping LLM SQL resolution.", provider)
        return None
    if not service.is_configured:
        return None
    try:
        logger.warning(
            "llm_sql_resolution_start provider=%s model=%s",
            provider,
            get_settings().llm_model if provider == "openai_compatible" else get_settings().gemini_model,
        )
        plan = service.generate_query_plan(message, schema)
    except (GeminiConfigError, QueryPlanParseError, TimeoutError, RuntimeError) as exc:
        logger.warning("%s SQL resolution failed: %s", provider, exc)
        return None
    provider_name = provider
    if not plan.can_answer:
        return ResolvedSQL(
            sql=None,
            explanation=plan.explanation,
            provider=provider_name,
            answer=plan.answer,
            assumptions=tuple(plan.assumptions),
            tables_used=tuple(plan.tables_used),
            confidence=plan.confidence,
            clarifying_question=plan.clarifying_question,
        )
    if not plan.sql:
        return None
    explanation = plan.explanation.strip() or "Generated from your question and schema."
    return ResolvedSQL(
        sql=plan.sql,
        explanation=explanation,
        provider=provider_name,
        answer=plan.answer,
        assumptions=tuple(plan.assumptions),
        tables_used=tuple(plan.tables_used),
        confidence=plan.confidence,
    )
