from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator


class GeminiQueryPlanStep(BaseModel):
    id: int
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(min_length=1, max_length=1000)


class GeminiQueryPlan(BaseModel):
    mode: Literal["new_query", "refine_query", "schema_answer", "clarify"] = "new_query"
    can_answer: bool = True
    answer: str = Field(min_length=1, max_length=1000)
    sql: str | None = Field(default=None, max_length=8000)
    explanation: str = Field(default="", max_length=2000)
    assumptions: list[str] = Field(default_factory=list, max_length=10)
    tables_used: list[str] = Field(default_factory=list, max_length=20)
    confidence: float = Field(default=0.7, ge=0.0, le=1.0)
    clarifying_question: str | None = Field(default=None, max_length=500)
    steps: list[GeminiQueryPlanStep] = Field(default_factory=list, max_length=12)

    @field_validator("sql")
    @classmethod
    def normalize_sql(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None

    @property
    def goal(self) -> str:
        return self.answer

    @model_validator(mode="after")
    def validate_unique_step_ids(self) -> GeminiQueryPlan:
        if self.can_answer and self.mode != "schema_answer" and not self.sql and not self.clarifying_question:
            raise ValueError("Answerable responses must include SQL or a clarifying question.")
        step_ids = [step.id for step in self.steps]
        if len(step_ids) != len(set(step_ids)):
            raise ValueError("Step ids must be unique.")
        return self


class GeminiConfigError(RuntimeError):
    """Raised when Gemini is not configured (missing API key)."""


class QueryPlanParseError(ValueError):
    """Raised when Gemini output cannot be parsed or validated."""
