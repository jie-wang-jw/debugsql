from typing import Literal

from pydantic import BaseModel, Field

from app.tools.schemas import ProposedToolAction


IntentType = Literal[
    "help",
    "benchmark_query",
    "edit_plan",
    "unsupported",
    "error",
]

ConversationMode = Literal["new_query", "refine_query", "schema_answer", "clarify"]


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
    proposedActions: list[ProposedToolAction] = Field(default_factory=list)
    requiresApproval: bool = False
    confidence: float | None = None
    assumptions: list[str] = Field(default_factory=list)
    tablesUsed: list[str] = Field(default_factory=list)
    usedContext: bool = False
    conversationMode: ConversationMode | None = None
    workingStateRevision: int | None = None
