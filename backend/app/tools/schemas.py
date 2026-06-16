from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


DbType = Literal["sqlite_benchmark", "postgres"]


class DatasetContext(BaseModel):
    """Connection context shared by chat, capabilities, and tool execution."""

    dbType: DbType = "sqlite_benchmark"
    benchmark: str | None = None
    dbId: str | None = None


class ConnectorCapabilities(BaseModel):
    dbType: DbType
    label: str
    supportsExplain: bool = False
    supportsSampleRows: bool = True
    supportsRelationships: bool = True
    readOnly: bool = True
    maxRows: int = 100
    maxSampleRows: int = 10


class ToolDefinition(BaseModel):
    name: str
    label: str
    description: str
    requiresApproval: bool = False
    parameters: dict[str, Any] = Field(default_factory=dict)


class ToolCall(BaseModel):
    id: str
    tool: str
    label: str
    description: str = ""
    arguments: dict[str, Any] = Field(default_factory=dict)
    requiresApproval: bool = False
    status: Literal["proposed", "approved", "completed", "failed"] = "proposed"


class ToolResult(BaseModel):
    toolCallId: str
    tool: str
    success: bool
    data: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None


class CapabilityExample(BaseModel):
    id: str
    kind: Literal["prompt", "sql"]
    label: str
    content: str


class CapabilitiesResponse(BaseModel):
    context: DatasetContext
    connector: ConnectorCapabilities
    tools: list[ToolDefinition]
    schemaPreview: dict[str, Any] = Field(default_factory=dict)
    policies: dict[str, Any] = Field(default_factory=dict)
    examples: list[CapabilityExample] = Field(default_factory=list)


class ToolExecuteRequest(BaseModel):
    tool: str
    toolCallId: str | None = None
    arguments: dict[str, Any] = Field(default_factory=dict)
    context: DatasetContext
    approved: bool = False


class ProposedToolAction(BaseModel):
    id: str
    tool: str
    label: str
    description: str = ""
    arguments: dict[str, Any] = Field(default_factory=dict)
    requiresApproval: bool = False
