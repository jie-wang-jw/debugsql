from fastapi import APIRouter, HTTPException

from app.auth import ensure_dev_user, user_to_dict
from app.config import get_settings
from app.database import session_scope


router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/me")
def me() -> dict:
    settings = get_settings()
    if not settings.debugsql_auto_login:
        raise HTTPException(status_code=401, detail="No authenticated user")
    with session_scope() as session:
        user = ensure_dev_user(session)
        return {"success": True, "data": user_to_dict(user)}


@router.post("/logout")
def logout() -> dict:
    return {"success": True, "data": None}


@router.get("/github/login")
def github_login() -> dict:
    raise HTTPException(status_code=501, detail="GitHub OAuth is not configured yet")
