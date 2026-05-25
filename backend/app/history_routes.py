from fastapi import APIRouter, HTTPException, Query, Request

from app.persistence import conversation_detail, history_summary
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
