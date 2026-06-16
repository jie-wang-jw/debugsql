from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel

from app.request_auth import request_user_id
from app.tools.capabilities_service import build_capabilities
from app.tools.executor import execute_tool
from app.tools.schemas import DatasetContext, ToolExecuteRequest, ToolResult
from app.tools.registry import normalize_context


router = APIRouter(tags=["capabilities"])


class CapabilitiesQuery(BaseModel):
    dbType: str | None = None
    benchmark: str | None = None
    dbId: str | None = None


@router.get("/capabilities")
def get_capabilities(
    request: Request,
    dbType: str | None = Query(default=None),
    benchmark: str | None = Query(default=None),
    dbId: str | None = Query(default=None),
) -> dict:
    request_user_id(request)
    context = normalize_context({"dbType": dbType, "benchmark": benchmark, "dbId": dbId})
    try:
        payload = build_capabilities(context)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"success": True, "data": payload.model_dump()}


@router.post("/tools/execute")
def post_tool_execute(body: ToolExecuteRequest, request: Request) -> dict:
    request_user_id(request)
    try:
        result: ToolResult = execute_tool(
            body.tool,
            body.arguments,
            body.context,
            approved=body.approved,
            tool_call_id=body.toolCallId,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"success": True, "data": result.model_dump()}
