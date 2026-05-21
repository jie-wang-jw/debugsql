from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from app.demo_pipeline import get_execution_result, run_demo_execution
from app.request_auth import request_user_id


router = APIRouter(prefix="/execute", tags=["execution"])


class ExecutionRequest(BaseModel):
    sql: str
    sessionId: str = "dev-session"
    planId: str | None = None


@router.post("")
def execute(request: ExecutionRequest, http_request: Request) -> dict:
    run = run_demo_execution(
        request.sql,
        request.sessionId,
        request.planId,
        user_id=request_user_id(http_request),
    )
    return {"success": True, "data": run}


@router.get("/{run_id}/result")
def execution_result(run_id: str) -> dict:
    result = get_execution_result(run_id)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Execution run {run_id} was not found")
    return {"success": True, "data": result}


@router.delete("/{run_id}")
def cancel_execution(run_id: str) -> dict:
    return {"success": True, "data": None}
