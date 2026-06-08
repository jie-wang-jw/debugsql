from fastapi import APIRouter, HTTPException, Query, Request

from app.persistence import admin_conversation_detail, admin_history_summary, persist_operation_log
from app.request_auth import request_admin_user


router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/history/summary")
def history_summary(
    request: Request,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> dict:
    request_admin_user(request)
    return {
        "success": True,
        "data": admin_history_summary(limit=limit, offset=offset),
    }


@router.get("/history/conversations/{conversation_id}")
def conversation(conversation_id: str, request: Request) -> dict:
    admin_user = request_admin_user(request)
    detail = admin_conversation_detail(conversation_id)
    if not detail:
        raise HTTPException(status_code=404, detail="Conversation not found")
    persist_operation_log(
        operation_type="admin_history_view",
        target_type="conversation",
        target_id=conversation_id,
        user_id=admin_user.id,
        payload={
            "viewedUser": detail.get("user"),
            "conversationId": conversation_id,
        },
    )
    return {"success": True, "data": detail}
