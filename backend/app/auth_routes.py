from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel
from sqlalchemy.exc import SQLAlchemyError

from app.auth import (
    create_session_record,
    dev_user_dict,
    email_code_hash,
    ensure_dev_user,
    expire_pending_email_codes,
    expire_session_token,
    get_user_by_session_token,
    latest_pending_email_code,
    normalize_email,
    upsert_email_user,
    user_to_dict,
)
from app.config import get_settings
from app.database import session_scope
from app.email_sender import EmailDeliveryError, send_login_code
from app.models.auth import EmailLoginCode, utc_now


router = APIRouter(prefix="/auth", tags=["auth"])


class EmailCodeRequest(BaseModel):
    email: str


class EmailCodeVerifyRequest(BaseModel):
    email: str
    code: str


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


@router.post("/email/request-code")
def request_email_code(payload: EmailCodeRequest, request: Request) -> dict:
    settings = get_settings()
    try:
        email = normalize_email(payload.email)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    now = utc_now()
    code = f"{secrets.randbelow(1_000_000):06d}"
    client_ip = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")

    try:
        with session_scope() as session:
            latest = latest_pending_email_code(session, email)
            if latest:
                latest_created = _with_timezone(latest.created_at)
                latest_expires = _with_timezone(latest.expires_at)
                if latest_expires <= now:
                    latest.status = "expired"
                elif latest_created + timedelta(seconds=settings.email_login_resend_seconds) > now:
                    raise HTTPException(status_code=429, detail="Please wait before requesting another code")
                else:
                    expire_pending_email_codes(session, email)

            record = EmailLoginCode(
                id=f"code_{secrets.token_hex(12)}",
                email=email,
                code_hash=email_code_hash(email, code),
                status="pending",
                attempt_count=0,
                expires_at=now + timedelta(minutes=settings.email_login_code_ttl_minutes),
                created_at=now,
                request_ip=client_ip,
                user_agent=user_agent,
            )
            session.add(record)
    except HTTPException:
        raise
    except SQLAlchemyError as exc:
        raise HTTPException(status_code=500, detail="System database unavailable") from exc

    try:
        delivery = send_login_code(email, code)
    except EmailDeliveryError as exc:
        _expire_email_code(email, code)
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return {
        "success": True,
        "data": {
            "email": email,
            "expiresInSeconds": settings.email_login_code_ttl_minutes * 60,
            "resendAfterSeconds": settings.email_login_resend_seconds,
            **delivery,
        },
    }


@router.post("/email/verify-code")
def verify_email_code(payload: EmailCodeVerifyRequest, response: Response) -> dict:
    settings = get_settings()
    try:
        email = normalize_email(payload.email)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    code = payload.code.strip()
    if not code.isdigit() or len(code) != 6:
        raise HTTPException(status_code=400, detail="Enter the 6-digit verification code")

    now = utc_now()
    error: tuple[int, str] | None = None
    token: str | None = None
    data: dict | None = None
    try:
        with session_scope() as session:
            record = latest_pending_email_code(session, email)
            if not record:
                raise HTTPException(status_code=400, detail="No active verification code for this email")

            if _with_timezone(record.expires_at) <= now:
                record.status = "expired"
                error = (400, "Verification code expired")
            elif record.attempt_count >= settings.email_login_max_attempts:
                record.status = "expired"
                error = (429, "Too many verification attempts")
            elif not secrets.compare_digest(record.code_hash, email_code_hash(email, code)):
                record.attempt_count += 1
                if record.attempt_count >= settings.email_login_max_attempts:
                    record.status = "expired"
                    error = (429, "Too many verification attempts")
                else:
                    error = (400, "Invalid verification code")
            else:
                user = upsert_email_user(session, email)
                token, _record = create_session_record(session, user)
                record.status = "used"
                record.used_at = now
                data = user_to_dict(user)
                data["persistence"] = "database"
    except HTTPException:
        raise
    except SQLAlchemyError as exc:
        print(f"[auth] Email verification database error for {email}: {exc}", flush=True)
        raise HTTPException(status_code=500, detail="Login service failed while verifying the code") from exc

    if error:
        raise HTTPException(status_code=error[0], detail=error[1])
    if not token or data is None:
        raise HTTPException(status_code=400, detail="Unable to verify code")

    _set_session_cookie(response, token)
    return {"success": True, "data": data}


@router.get("/github/login")
@router.get("/github/callback")
@router.get("/google/login")
@router.get("/google/callback")
def oauth_disabled() -> dict:
    raise HTTPException(status_code=410, detail="OAuth login has been disabled. Use email verification login.")


def _set_session_cookie(response: Response, token: str) -> None:
    settings = get_settings()
    response.set_cookie(
        settings.auth_cookie_name,
        token,
        httponly=True,
        secure=settings.auth_cookie_secure,
        samesite="lax",
        path="/",
        max_age=7 * 24 * 60 * 60,
    )


def _expire_email_code(email: str, code: str) -> None:
    try:
        with session_scope() as session:
            record = latest_pending_email_code(session, email)
            if record and secrets.compare_digest(record.code_hash, email_code_hash(email, code)):
                record.status = "expired"
    except SQLAlchemyError:
        pass


def _with_timezone(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value
