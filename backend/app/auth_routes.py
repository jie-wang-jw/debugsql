from __future__ import annotations

import json
import secrets
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request as UrlRequest
from urllib.request import urlopen

from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.responses import RedirectResponse
from sqlalchemy.exc import SQLAlchemyError

from app.auth import (
    create_session_record,
    dev_user_dict,
    ensure_dev_user,
    expire_session_token,
    get_user_by_session_token,
    upsert_oauth_user,
    user_to_dict,
)
from app.config import get_settings
from app.database import session_scope


router = APIRouter(prefix="/auth", tags=["auth"])

OAUTH_STATE_COOKIE = "debugsql_oauth_state"


@router.get("/me")
def me(request: Request) -> dict:
    settings = get_settings()
    token = request.cookies.get(settings.auth_cookie_name)
    try:
        with session_scope() as session:
            user = get_user_by_session_token(session, token)
            if user:
                data = user_to_dict(user)
                data["persistence"] = "database"
                return {"success": True, "data": data}

            if not settings.debugsql_auto_login:
                raise HTTPException(status_code=401, detail="No authenticated user")

            user = ensure_dev_user(session)
            data = user_to_dict(user)
            data["persistence"] = "database"
            return {"success": True, "data": data}
    except HTTPException:
        raise
    except SQLAlchemyError as exc:
        if not settings.debugsql_auto_login:
            raise HTTPException(status_code=500, detail="System database unavailable") from exc
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
def logout(request: Request, response: Response) -> dict:
    settings = get_settings()
    token = request.cookies.get(settings.auth_cookie_name)
    try:
        with session_scope() as session:
            expire_session_token(session, token)
    except SQLAlchemyError:
        pass
    response.delete_cookie(settings.auth_cookie_name, path="/")
    return {"success": True, "data": None}


@router.get("/github/login")
def github_login() -> RedirectResponse:
    settings = get_settings()
    if not settings.github_client_id or not settings.github_client_secret:
        raise HTTPException(status_code=501, detail="GitHub OAuth is not configured yet")
    state = secrets.token_urlsafe(24)
    params = urlencode(
        {
            "client_id": settings.github_client_id,
            "redirect_uri": f"{settings.app_base_url}/auth/github/callback",
            "scope": "read:user user:email",
            "state": state,
        }
    )
    response = RedirectResponse(f"https://github.com/login/oauth/authorize?{params}")
    _set_state_cookie(response, state)
    return response


@router.get("/github/callback")
def github_callback(code: str, state: str, request: Request) -> RedirectResponse:
    _validate_state(request, state)
    settings = get_settings()
    token = _post_json(
        "https://github.com/login/oauth/access_token",
        {
            "client_id": settings.github_client_id,
            "client_secret": settings.github_client_secret,
            "code": code,
            "redirect_uri": f"{settings.app_base_url}/auth/github/callback",
        },
        {"Accept": "application/json"},
    ).get("access_token")
    if not token:
        raise HTTPException(status_code=400, detail="GitHub did not return an access token")

    user = _get_json("https://api.github.com/user", {"Authorization": f"Bearer {token}"})
    email = user.get("email") or _github_primary_email(token)
    if not email:
        raise HTTPException(status_code=400, detail="GitHub account did not provide an email address")
    return _complete_oauth_login(
        provider="github",
        provider_user_id=str(user.get("id")),
        email=email,
        display_name=user.get("name") or user.get("login"),
        avatar_url=user.get("avatar_url"),
        profile=user,
    )


@router.get("/google/login")
def google_login() -> RedirectResponse:
    settings = get_settings()
    if not settings.google_client_id or not settings.google_client_secret:
        raise HTTPException(status_code=501, detail="Google OAuth is not configured yet")
    state = secrets.token_urlsafe(24)
    params = urlencode(
        {
            "client_id": settings.google_client_id,
            "redirect_uri": f"{settings.app_base_url}/auth/google/callback",
            "response_type": "code",
            "scope": "openid email profile",
            "state": state,
        }
    )
    response = RedirectResponse(f"https://accounts.google.com/o/oauth2/v2/auth?{params}")
    _set_state_cookie(response, state)
    return response


@router.get("/google/callback")
def google_callback(code: str, state: str, request: Request) -> RedirectResponse:
    _validate_state(request, state)
    settings = get_settings()
    token_payload = _post_json(
        "https://oauth2.googleapis.com/token",
        {
            "client_id": settings.google_client_id,
            "client_secret": settings.google_client_secret,
            "code": code,
            "redirect_uri": f"{settings.app_base_url}/auth/google/callback",
            "grant_type": "authorization_code",
        },
    )
    access_token = token_payload.get("access_token")
    if not access_token:
        raise HTTPException(status_code=400, detail="Google did not return an access token")

    profile = _get_json("https://www.googleapis.com/oauth2/v2/userinfo", {"Authorization": f"Bearer {access_token}"})
    email = profile.get("email")
    if not email:
        raise HTTPException(status_code=400, detail="Google account did not provide an email address")
    return _complete_oauth_login(
        provider="google",
        provider_user_id=str(profile.get("id")),
        email=email,
        display_name=profile.get("name"),
        avatar_url=profile.get("picture"),
        profile=profile,
    )


def _complete_oauth_login(
    *,
    provider: str,
    provider_user_id: str,
    email: str,
    display_name: str | None,
    avatar_url: str | None,
    profile: dict[str, Any],
) -> RedirectResponse:
    settings = get_settings()
    with session_scope() as session:
        user = upsert_oauth_user(
            session,
            provider=provider,
            provider_user_id=provider_user_id,
            email=email,
            display_name=display_name,
            avatar_url=avatar_url,
            profile=profile,
        )
        token, _record = create_session_record(session, user)

    response = RedirectResponse(settings.frontend_base_url)
    response.set_cookie(
        settings.auth_cookie_name,
        token,
        httponly=True,
        secure=settings.auth_cookie_secure,
        samesite="lax",
        path="/",
        max_age=7 * 24 * 60 * 60,
    )
    response.delete_cookie(OAUTH_STATE_COOKIE, path="/")
    return response


def _set_state_cookie(response: RedirectResponse, state: str) -> None:
    settings = get_settings()
    response.set_cookie(
        OAUTH_STATE_COOKIE,
        state,
        httponly=True,
        secure=settings.auth_cookie_secure,
        samesite="lax",
        path="/",
        max_age=10 * 60,
    )


def _validate_state(request: Request, state: str) -> None:
    expected = request.cookies.get(OAUTH_STATE_COOKIE)
    if not expected or not secrets.compare_digest(expected, state):
        raise HTTPException(status_code=400, detail="Invalid OAuth state")


def _github_primary_email(token: str) -> str | None:
    emails = _get_json("https://api.github.com/user/emails", {"Authorization": f"Bearer {token}"})
    if not isinstance(emails, list):
        return None
    primary = next((item for item in emails if item.get("primary") and item.get("verified")), None)
    fallback = next((item for item in emails if item.get("verified")), None)
    chosen = primary or fallback
    return chosen.get("email") if chosen else None


def _post_json(url: str, payload: dict[str, Any], headers: dict[str, str] | None = None) -> dict[str, Any]:
    encoded = urlencode(payload).encode("utf-8")
    request = UrlRequest(
        url,
        data=encoded,
        headers={"Content-Type": "application/x-www-form-urlencoded", "User-Agent": "DebugSQL", **(headers or {})},
        method="POST",
    )
    return _open_json(request)


def _get_json(url: str, headers: dict[str, str] | None = None) -> Any:
    request = UrlRequest(url, headers={"User-Agent": "DebugSQL", **(headers or {})}, method="GET")
    return _open_json(request)


def _open_json(request: UrlRequest) -> Any:
    try:
        with urlopen(request, timeout=15) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        raise HTTPException(status_code=400, detail=f"OAuth provider error: {exc.read().decode('utf-8')}") from exc
    except (URLError, TimeoutError) as exc:
        raise HTTPException(status_code=400, detail=f"OAuth provider request failed: {exc}") from exc
