from typing import Literal

from pydantic import BaseModel


IntentType = Literal[
    "help",
    "benchmark_query",
    "edit_plan",
    "unsupported",
]


class ConversationIntent(BaseModel):
    intent_type: IntentType
    confidence: float = 1.0
    requires_plan: bool = False
    requires_execution: bool = False
    reason: str = ""


class ConversationResponse(BaseModel):
    content: str
    intentType: IntentType
    requiresPlan: bool = False
    requiresExecution: bool = False
    planId: str | None = None
    sql: str | None = None
    explanation: str | None = None
