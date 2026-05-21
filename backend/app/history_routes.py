from fastapi import APIRouter

from app.persistence import history_summary


router = APIRouter(prefix="/history", tags=["history"])


@router.get("/summary")
def summary(limit: int = 20) -> dict:
    return {"success": True, "data": history_summary(limit=limit)}
