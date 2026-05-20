from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.demo_pipeline import get_plan_graph, update_plan_node


router = APIRouter(prefix="/query-plan", tags=["query-plan"])


class NodeUpdateRequest(BaseModel):
    nodeId: str
    data: dict[str, Any]


@router.get("/{plan_id}")
def get_query_plan(plan_id: str) -> dict:
    graph = get_plan_graph(plan_id)
    if graph is None:
        raise HTTPException(status_code=404, detail=f"Query plan {plan_id} was not found")
    return {"success": True, "data": graph}


@router.patch("/{plan_id}/nodes/{node_id}")
def patch_query_plan_node(plan_id: str, node_id: str, request: NodeUpdateRequest) -> dict:
    graph = update_plan_node(plan_id, node_id, request.data)
    if graph is None:
        raise HTTPException(status_code=404, detail=f"Query plan {plan_id} was not found")
    return {"success": True, "data": None}


@router.post("/{plan_id}/snapshot")
def save_query_plan_snapshot(plan_id: str) -> dict:
    if get_plan_graph(plan_id) is None:
        raise HTTPException(status_code=404, detail=f"Query plan {plan_id} was not found")
    return {
        "success": True,
        "data": {
            "snapshotId": f"snapshot_{plan_id}",
            "label": "Backend stub snapshot",
            "createdAt": "dev-mode",
        },
    }
