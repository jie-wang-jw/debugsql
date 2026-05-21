from pydantic import BaseModel
from fastapi import APIRouter, Request

from app.conversation.handlers import handle_chat_message
from app.persistence import persist_chat_interaction, persist_query_plan
from app.request_auth import request_user_id


router = APIRouter(tags=["chat"])


class ChatQueryRequest(BaseModel):
    message: str
    sessionId: str = "dev-session"
    datasetContext: dict | None = None


@router.post("/query")
def query(request: ChatQueryRequest, http_request: Request) -> dict:
    user_id = request_user_id(http_request)
    response = handle_chat_message(request.message, request.sessionId, request.datasetContext)
    response_data = response.model_dump()
    persist_chat_interaction(
        session_id=request.sessionId,
        user_message=request.message,
        assistant_content=response.content,
        dataset_context=request.datasetContext,
        response=response_data,
        user_id=user_id,
    )
    if response.planId:
        persist_query_plan(response.planId, request.sessionId, user_id=user_id)
    return {
        "success": True,
        "data": response_data,
    }
