from fastapi import APIRouter, HTTPException, Query, Request, Response

from app.persistence import conversation_detail, history_summary, operation_logs_export
from app.request_auth import request_user_id


router = APIRouter(prefix="/history", tags=["history"])


@router.get("/summary")
def summary(
    request: Request,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> dict:
    return {
        "success": True,
        "data": history_summary(limit=limit, offset=offset, user_id=request_user_id(request)),
    }


@router.get("/conversations/{conversation_id}")
def conversation(conversation_id: str, request: Request) -> dict:
    detail = conversation_detail(conversation_id, user_id=request_user_id(request))
    if not detail:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return {"success": True, "data": detail}


@router.get("/operation-logs/export")
def export_operation_logs(
    request: Request,
    format: str = Query(default="json", pattern="^(json|csv)$"),
    limit: int = Query(default=200, ge=1, le=1000),
):
    data = operation_logs_export(
        user_id=request_user_id(request),
        limit=limit,
        output_format=format,
    )
    if format == "csv":
        return Response(
            content=str(data),
            media_type="text/csv",
            headers={"Content-Disposition": 'attachment; filename="debugsql-operation-logs.csv"'},
        )
    return {"success": True, "data": data}
