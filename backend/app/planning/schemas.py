from typing import Any, Literal

from pydantic import BaseModel, Field


DataSourceType = Literal["relational", "json", "knowledge_graph", "image"]
PlanType = Literal["tree", "dag"]
NodeType = Literal["intent", "operation", "data"]
NodeStatus = Literal["pending", "ready", "running", "success", "error", "edited"]
EdgeType = Literal["control_flow", "data_flow"]


class PlanOptions(BaseModel):
    data_source_type: DataSourceType = "relational"
    plan_type: PlanType = "tree"
    dialect: str = "sqlite"


class PlanningRequest(BaseModel):
    intent_ir: dict[str, Any] = Field(default_factory=dict)
    schema_context: dict[str, Any] = Field(default_factory=dict)
    options: PlanOptions = Field(default_factory=PlanOptions)


class PlanNode(BaseModel):
    node_id: str
    node_type: NodeType
    label: str
    status: NodeStatus = "pending"
    editable: bool = True
    payload: dict[str, Any] = Field(default_factory=dict)
    operation_type: str | None = None


class PlanEdge(BaseModel):
    source: str
    target: str
    edge_type: EdgeType = "control_flow"


class ExecutablePlan(BaseModel):
    type: str = "sql"
    dialect: str = "sqlite"
    content: str = ""


class QueryPlan(BaseModel):
    plan_id: str
    plan_type: PlanType = "tree"
    data_source_type: DataSourceType = "relational"
    nodes: list[PlanNode] = Field(default_factory=list)
    edges: list[PlanEdge] = Field(default_factory=list)
    executable: ExecutablePlan | None = None
    warnings: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class PlanningResponse(BaseModel):
    plan: QueryPlan
