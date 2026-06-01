from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class NL2IRRequest(BaseModel):
    message: str
    schema_context: dict[str, Any] | None = None
    dataset_context: dict[str, Any] | None = None


class NL2IRResult(BaseModel):
    intent_ir: dict[str, Any] = Field(default_factory=dict)
    selected_sql: str | None = None
    answer: dict[str, Any] | None = None
    trace: dict[str, Any] = Field(default_factory=dict)
    provider_name: str = "stub"
    succeeded: bool = True
    error_message: str | None = None

