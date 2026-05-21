from fastapi import APIRouter, HTTPException
from sqlalchemy.exc import SQLAlchemyError

from app.auth import dev_user_dict, ensure_dev_user, user_to_dict
from app.config import get_settings
from app.database import session_scope


router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/me")
def me() -> dict:
    settings = get_settings()
    if not settings.debugsql_auto_login:
        raise HTTPException(status_code=401, detail="No authenticated user")
    try:
        with session_scope() as session:
            user = ensure_dev_user(session)
            data = user_to_dict(user)
            data["persistence"] = "database"
            return {"success": True, "data": data}
    except SQLAlchemyError as exc:
        return {
            "success": True,
            "data": dev_user_dict(persistence="ephemeral"),
            "warning": {
                "code": "database_unavailable",
                "message": "Dev auto-login is using an ephemeral user because the system database is unavailable.",
                "detail": str(exc),
            },
        }


@router.post("/logout")
def logout() -> dict:
    return {"success": True, "data": None}


@router.get("/github/login")
def github_login() -> dict:
    raise HTTPException(status_code=501, detail="GitHub OAuth is not configured yet")
