from pydantic import BaseModel
from fastapi import APIRouter

from app.demo_pipeline import generate_plan_for_message


router = APIRouter(tags=["chat"])


class ChatQueryRequest(BaseModel):
    message: str
    sessionId: str = "dev-session"
    datasetContext: dict | None = None


@router.post("/query")
def query(request: ChatQueryRequest) -> dict:
    stored = generate_plan_for_message(request.message, request.sessionId, request.datasetContext)
    plan = stored["plan"]
    sql = (plan.get("executable") or {}).get("content", "")
    return {
        "success": True,
        "data": {
            "content": stored.get("assistant_content")
            or "I generated a backend stub IR and query plan for this request.",
            "planId": plan["plan_id"],
            "sql": sql,
            "explanation": "Backend stub: NL -> IR -> Query Plan -> SQL preview.",
        },
    }
