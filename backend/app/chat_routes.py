from pydantic import BaseModel
from fastapi import APIRouter

from app.conversation.handlers import handle_chat_message


router = APIRouter(tags=["chat"])


class ChatQueryRequest(BaseModel):
    message: str
    sessionId: str = "dev-session"
    datasetContext: dict | None = None


@router.post("/query")
def query(request: ChatQueryRequest) -> dict:
    response = handle_chat_message(request.message, request.sessionId, request.datasetContext)
    return {
        "success": True,
        "data": response.model_dump(),
    }
