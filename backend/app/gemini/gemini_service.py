from __future__ import annotations

import logging
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from typing import Any

from app.config import Settings, get_settings
from app.gemini.graph_mapper import gemini_plan_to_graph
from app.gemini.prompt_builder import PromptBuilder
from app.gemini.query_plan_parser import QueryPlanParser
from app.gemini.schemas import GeminiConfigError, GeminiQueryPlan, QueryPlanParseError

logger = logging.getLogger(__name__)


class GeminiService:
    """Calls Google Gemini and returns validated query plans."""

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
        return bool(self._settings.gemini_api_key.strip())

    def generate_query_plan(
        self,
        message: str,
        schema_context: dict[str, Any] | None = None,
    ) -> GeminiQueryPlan:
        if not self.is_configured:
            raise GeminiConfigError(
                "GEMINI_API_KEY is not set. Add it to the repo-root .env file."
            )

        request_id = uuid.uuid4().hex[:12]
        system_instruction, user_prompt = self._prompt_builder.build(message, schema_context)
        started = time.perf_counter()

        logger.info(
            "gemini_request_start request_id=%s model=%s message_len=%d",
            request_id,
            self._settings.gemini_model,
            len(message),
        )

        try:
            raw_text = self._call_gemini(system_instruction, user_prompt)
        except FuturesTimeoutError as exc:
            logger.warning("gemini_request_timeout request_id=%s", request_id)
            raise TimeoutError(
                f"Gemini request timed out after {self._settings.gemini_timeout_seconds}s."
            ) from exc
        except Exception as exc:
            logger.exception("gemini_request_failed request_id=%s error=%s", request_id, type(exc).__name__)
            raise RuntimeError(f"Gemini API call failed: {exc}") from exc

        elapsed_ms = int((time.perf_counter() - started) * 1000)
        logger.info(
            "gemini_request_complete request_id=%s latency_ms=%d response_len=%d",
            request_id,
            elapsed_ms,
            len(raw_text or ""),
        )

        try:
            plan = self._parser.parse(raw_text)
        except QueryPlanParseError:
            logger.warning("gemini_parse_failed request_id=%s", request_id)
            raise

        logger.info(
            "gemini_parse_ok request_id=%s steps=%d has_sql=%s",
            request_id,
            len(plan.steps),
            bool(plan.sql),
        )
        return plan

    def generate_query_plan_graph(
        self,
        message: str,
        schema_context: dict[str, Any] | None = None,
    ) -> tuple[GeminiQueryPlan, dict[str, Any]]:
        plan = self.generate_query_plan(message, schema_context)
        graph = gemini_plan_to_graph(plan, message)
        return plan, graph

    def _call_gemini(self, system_instruction: str, user_prompt: str) -> str:
        try:
            from google import genai
            from google.genai import types
        except ModuleNotFoundError as exc:
            raise GeminiConfigError(
                "google-genai is not installed. Install backend dependencies before using Gemini."
            ) from exc

        client = genai.Client(api_key=self._settings.gemini_api_key)
        config = types.GenerateContentConfig(
            system_instruction=system_instruction,
            temperature=0.2,
            response_mime_type="application/json",
            response_json_schema=self._prompt_builder.response_json_schema(),
        )

        def _invoke() -> str:
            response = client.models.generate_content(
                model=self._settings.gemini_model,
                contents=user_prompt,
                config=config,
            )
            text = (response.text or "").strip()
            if not text:
                raise QueryPlanParseError("Gemini returned an empty response body.")
            return text

        timeout = max(1, int(self._settings.gemini_timeout_seconds))
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(_invoke)
            return future.result(timeout=timeout)


def log_gemini_startup(settings: Settings | None = None) -> None:
    current = settings or get_settings()
    if current.gemini_api_key.strip() and current.query_plan_provider.lower() == "gemini":
        logger.info(
            "Gemini configured: model=%s timeout_seconds=%d",
            current.gemini_model,
            current.gemini_timeout_seconds,
        )
    elif current.query_plan_provider.lower() == "gemini":
        logger.warning("QUERY_PLAN_PROVIDER=gemini but GEMINI_API_KEY is not set.")
