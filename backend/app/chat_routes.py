from pydantic import BaseModel
from fastapi import APIRouter, Request

from app.conversation.handlers import handle_chat_message
from app.conversation.schemas import ConversationResponse
from app.persistence import persist_chat_failure, persist_chat_interaction
from app.request_auth import request_user_id


router = APIRouter(tags=["chat"])


class ChatQueryRequest(BaseModel):
    message: str
    sessionId: str = "dev-session"
    datasetContext: dict | None = None


@router.post("/query")
def query(request: ChatQueryRequest, http_request: Request) -> dict:
    user_id = request_user_id(http_request)
    try:
        response = handle_chat_message(request.message, request.sessionId, request.datasetContext)
    except Exception as exc:
        response = _chat_error_response(exc)
        response_data = response.model_dump()
        persist_chat_failure(
            session_id=request.sessionId,
            user_message=request.message,
            assistant_content=response.content,
            dataset_context=request.datasetContext,
            error_type=type(exc).__name__,
            error_message=str(exc),
            user_id=user_id,
        )
        return {"success": True, "data": response_data}

    response_data = response.model_dump()
    persist_chat_interaction(
        session_id=request.sessionId,
        user_message=request.message,
        assistant_content=response.content,
        dataset_context=request.datasetContext,
        response=response_data,
        user_id=user_id,
    )
    return {
        "success": True,
        "data": response_data,
    }


def _chat_error_response(exc: Exception) -> ConversationResponse:
    return ConversationResponse(
        content=(
            "I could not complete this request, but I saved the attempt for review.\n\n"
            f"Error: {type(exc).__name__}: {exc}"
        ),
        intentType="error",
        requiresPlan=False,
        requiresExecution=False,
        explanation=str(exc),
    )
