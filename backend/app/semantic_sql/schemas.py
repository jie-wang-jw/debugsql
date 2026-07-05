from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class NLFilterOp(BaseModel):
    op_id: str
    table: str
    table_alias: str
    column: str
    predicate: str


class ResolvedMatch(BaseModel):
    key: str
    score: float


class ResolvedOperator(BaseModel):
    op_id: str
    strategy: Literal["prefilter"] = "prefilter"
    table: str
    column: str
    predicate: str
    matches: list[ResolvedMatch] = Field(default_factory=list)


class RewriteResult(BaseModel):
    sql: str
    original_sql: str
    operators: list[ResolvedOperator] = Field(default_factory=list)
    explanation: str = ""
    assumptions: list[str] = Field(default_factory=list)


class SemanticSQLError(Exception):
    """Raised when semantic SQL cannot be parsed, gated, or rewritten."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message
