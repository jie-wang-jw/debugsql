from __future__ import annotations

from fastapi import HTTPException, Request

from app.auth import resolve_request_user
from app.config import get_settings
from app.database import session_scope


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
