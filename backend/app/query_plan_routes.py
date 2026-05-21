from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.demo_pipeline import (
    create_plan_run,
    get_plan_graph,
    get_plan_run,
    reset_plan_run,
    run_full_plan,
    step_plan_run,
    update_plan_node,
)


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
    return {"success": True, "data": graph}


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


@router.post("/{plan_id}/runs")
def start_query_plan_run(plan_id: str) -> dict:
    run = create_plan_run(plan_id)
    if run is None:
        raise HTTPException(status_code=404, detail=f"Query plan {plan_id} was not found")
    return {"success": True, "data": run}


@router.get("/{plan_id}/runs/{run_id}")
def get_query_plan_run(plan_id: str, run_id: str) -> dict:
    run = get_plan_run(run_id)
    if run is None or run["planId"] != plan_id:
        raise HTTPException(status_code=404, detail=f"Plan run {run_id} was not found")
    return {"success": True, "data": run}


@router.post("/{plan_id}/runs/{run_id}/step")
def step_query_plan_run(plan_id: str, run_id: str) -> dict:
    run = step_plan_run(plan_id, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail=f"Plan run {run_id} was not found")
    return {"success": True, "data": run}


@router.post("/{plan_id}/runs/{run_id}/full")
def run_query_plan_to_completion(plan_id: str, run_id: str) -> dict:
    run = run_full_plan(plan_id, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail=f"Plan run {run_id} was not found")
    return {"success": True, "data": run}


@router.post("/{plan_id}/runs/{run_id}/reset")
def reset_query_plan_run(plan_id: str, run_id: str) -> dict:
    run = reset_plan_run(plan_id, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail=f"Plan run {run_id} was not found")
    return {"success": True, "data": run}
