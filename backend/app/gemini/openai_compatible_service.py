from __future__ import annotations

import logging
import time
import uuid
from typing import Any

from app.config import Settings, get_settings
from app.gemini.graph_mapper import gemini_plan_to_graph
from app.gemini.prompt_builder import PromptBuilder
from app.gemini.query_plan_parser import QueryPlanParser
from app.gemini.schemas import GeminiConfigError, GeminiQueryPlan, QueryPlanParseError

logger = logging.getLogger(__name__)


class OpenAICompatibleService:
    """Calls any OpenAI-compatible chat API and returns validated SQL plans."""

    def __init__(
        self,
        settings: Settings | None = None,
        prompt_builder: PromptBuilder | None = None,
        parser: QueryPlanParser | None = None,
    ) -> None:
        self._settings = settings or get_settings()
        self._prompt_builder = prompt_builder or PromptBuilder()
        self._parser = parser or QueryPlanParser()

    @property
    def is_configured(self) -> bool:
        return bool(self._settings.llm_api_key.strip() and self._settings.llm_api_base_url.strip())

    def generate_query_plan(
        self,
        message: str,
        schema_context: dict[str, Any] | None = None,
        working_state: dict[str, Any] | None = None,
    ) -> GeminiQueryPlan:
        if not self.is_configured:
            raise GeminiConfigError(
                "LLM_API_BASE_URL and LLM_API_KEY are required for openai_compatible provider."
            )

        request_id = uuid.uuid4().hex[:12]
        system_instruction, user_prompt = self._prompt_builder.build(
            message,
            schema_context,
            working_state=working_state,
        )
        started = time.perf_counter()

        logger.info(
            "openai_compatible_request_start request_id=%s model=%s message_len=%d",
            request_id,
            self._settings.llm_model,
            len(message),
        )

        try:
            raw_text = self._call_openai_compatible(system_instruction, user_prompt)
        except Exception as exc:
            logger.exception(
                "openai_compatible_request_failed request_id=%s error=%s",
                request_id,
                type(exc).__name__,
            )
            raise RuntimeError(f"OpenAI-compatible API call failed: {exc}") from exc

        elapsed_ms = int((time.perf_counter() - started) * 1000)
        logger.info(
            "openai_compatible_request_complete request_id=%s latency_ms=%d response_len=%d",
            request_id,
            elapsed_ms,
            len(raw_text or ""),
        )

        try:
            plan = self._parser.parse(raw_text)
        except QueryPlanParseError:
            logger.warning("openai_compatible_parse_failed request_id=%s", request_id)
            raise

        logger.info(
            "openai_compatible_parse_ok request_id=%s steps=%d has_sql=%s",
            request_id,
            len(plan.steps),
            bool(plan.sql),
        )
        return plan

    def generate_query_plan_graph(
        self,
        message: str,
        schema_context: dict[str, Any] | None = None,
        working_state: dict[str, Any] | None = None,
    ) -> tuple[GeminiQueryPlan, dict[str, Any]]:
        plan = self.generate_query_plan(message, schema_context, working_state=working_state)
        graph = gemini_plan_to_graph(plan, message)
        return plan, graph

    def _call_openai_compatible(self, system_instruction: str, user_prompt: str) -> str:
        try:
            from openai import OpenAI
        except ModuleNotFoundError as exc:
            raise GeminiConfigError(
                "openai is not installed. Install backend dependencies before using openai_compatible."
            ) from exc

        client = OpenAI(
            api_key=self._settings.llm_api_key,
            base_url=self._settings.llm_api_base_url.rstrip("/"),
            timeout=max(1, int(self._settings.llm_timeout_seconds)),
        )
        messages = [
            {"role": "system", "content": system_instruction},
            {"role": "user", "content": user_prompt},
        ]
        kwargs: dict[str, Any] = {
            "model": self._settings.llm_model,
            "messages": messages,
            "temperature": 0.2,
            "response_format": {"type": "json_object"},
        }
        try:
            completion = client.chat.completions.create(**kwargs)
        except Exception as exc:
            if "response_format" not in str(exc):
                raise
            kwargs.pop("response_format", None)
            completion = client.chat.completions.create(**kwargs)
        content = (completion.choices[0].message.content or "").strip()
        if not content:
            raise QueryPlanParseError("OpenAI-compatible provider returned an empty response body.")
        return content


def log_openai_compatible_startup(settings: Settings | None = None) -> None:
    current = settings or get_settings()
    if current.query_plan_provider.lower() != "openai_compatible":
        return
    if current.llm_api_key.strip() and current.llm_api_base_url.strip():
        logger.info(
            "OpenAI-compatible provider configured: model=%s base_url=%s timeout_seconds=%d",
            current.llm_model,
            current.llm_api_base_url,
            current.llm_timeout_seconds,
        )
    else:
        logger.warning("QUERY_PLAN_PROVIDER=openai_compatible but LLM_API_BASE_URL or LLM_API_KEY is not set.")
