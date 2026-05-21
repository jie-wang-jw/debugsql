from fastapi import APIRouter, HTTPException, Request

from app.persistence import conversation_detail, history_summary
from app.request_auth import request_user_id


router = APIRouter(prefix="/history", tags=["history"])


@router.get("/summary")
def summary(request: Request, limit: int = 20) -> dict:
    return {"success": True, "data": history_summary(limit=limit, user_id=request_user_id(request))}


@router.get("/conversations/{conversation_id}")
def conversation(conversation_id: str, request: Request) -> dict:
    detail = conversation_detail(conversation_id, user_id=request_user_id(request))
    if not detail:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return {"success": True, "data": detail}
