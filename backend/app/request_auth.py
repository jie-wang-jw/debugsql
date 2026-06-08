from __future__ import annotations

from fastapi import HTTPException, Request

from app.auth import resolve_request_user
from app.config import get_settings
from app.database import session_scope
from app.models.auth import User


def request_user_id(request: Request | None) -> str | None:
    if request is None:
        return None
    settings = get_settings()
    token = request.cookies.get(settings.auth_cookie_name)
    try:
        with session_scope() as session:
            return resolve_request_user(session, token).id
    except ValueError as exc:
        raise HTTPException(status_code=401, detail="No authenticated user") from exc


def request_current_user(request: Request | None) -> User:
    if request is None:
        raise HTTPException(status_code=401, detail="No authenticated user")
    settings = get_settings()
    token = request.cookies.get(settings.auth_cookie_name)
    try:
        with session_scope() as session:
            return resolve_request_user(session, token)
    except ValueError as exc:
        raise HTTPException(status_code=401, detail="No authenticated user") from exc


def request_admin_user(request: Request | None) -> User:
    user = request_current_user(request)
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")
    return user
