from __future__ import annotations

from pydantic import BaseModel, Field, field_validator, model_validator


class GeminiQueryPlanStep(BaseModel):
    id: int
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(min_length=1, max_length=1000)


class GeminiQueryPlan(BaseModel):
    goal: str = Field(min_length=1, max_length=500)
    sql: str | None = Field(default=None, max_length=8000)
    steps: list[GeminiQueryPlanStep] = Field(min_length=1, max_length=12)

    @field_validator("sql")
    @classmethod
    def normalize_sql(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None

    @model_validator(mode="after")
    def validate_unique_step_ids(self) -> GeminiQueryPlan:
        step_ids = [step.id for step in self.steps]
        if len(step_ids) != len(set(step_ids)):
            raise ValueError("Step ids must be unique.")
        return self


class GeminiConfigError(RuntimeError):
    """Raised when Gemini is not configured (missing API key)."""


class QueryPlanParseError(ValueError):
    """Raised when Gemini output cannot be parsed or validated."""
