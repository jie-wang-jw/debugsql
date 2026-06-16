from __future__ import annotations

import json
import re
from typing import Any

from app.tools.policy import is_safe_read_query
from app.gemini.schemas import GeminiQueryPlan, QueryPlanParseError


class QueryPlanParser:
    """Validates and normalizes Gemini JSON into a typed query plan."""

    def parse(self, raw_text: str) -> GeminiQueryPlan:
        payload = self._load_json(raw_text)
        try:
            plan = GeminiQueryPlan.model_validate(payload)
        except Exception as exc:
            raise QueryPlanParseError(f"Query plan JSON failed validation: {exc}") from exc

        if plan.sql:
            self._validate_sql(plan.sql)

        return plan

    def _load_json(self, raw_text: str) -> dict[str, Any]:
        text = (raw_text or "").strip()
        if not text:
            raise QueryPlanParseError("Gemini returned an empty response.")

        text = self._strip_code_fence(text)
        try:
            payload = json.loads(text)
        except json.JSONDecodeError as exc:
            raise QueryPlanParseError(f"Gemini response was not valid JSON: {exc}") from exc

        if not isinstance(payload, dict):
            raise QueryPlanParseError("Gemini response must be a JSON object.")

        return payload

    def _strip_code_fence(self, text: str) -> str:
        if text.startswith("```"):
            text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
            text = re.sub(r"\s*```$", "", text)
        return text.strip()

    def _validate_sql(self, sql: str) -> None:
        normalized = sql.strip()
        if not normalized:
            raise QueryPlanParseError("SQL must not be empty when provided.")

        if not is_safe_read_query(normalized):
            raise QueryPlanParseError("Only a single read-only SELECT/WITH query is allowed.")
