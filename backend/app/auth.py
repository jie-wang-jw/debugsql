from __future__ import annotations

import hmac
import hashlib
import re
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models.auth import EmailLoginCode, OAuthAccount, SessionRecord, User, utc_now


SESSION_TTL_DAYS = 7
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def stable_id(prefix: str, value: str) -> str:
    digest = hashlib.sha1(value.encode("utf-8")).hexdigest()[:16]
    return f"{prefix}_{digest}"


def token_hash(token: str) -> str:
    settings = get_settings()
    return hmac.new(
        settings.session_secret.encode("utf-8"),
        token.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def normalize_email(email: str) -> str:
    normalized = email.strip().lower()
    if not EMAIL_RE.match(normalized):
        raise ValueError("Invalid email address")
    return normalized


def email_code_hash(email: str, code: str) -> str:
    return token_hash(f"email-login:{normalize_email(email)}:{code.strip()}")


def ensure_dev_user(session: Session) -> User:
    settings = get_settings()
    email = settings.debugsql_dev_user_email
    user = session.execute(select(User).where(User.email == email)).scalar_one_or_none()
    now = utc_now()
    if user:
        user.last_login_at = now
        user.display_name = user.display_name or settings.debugsql_dev_user_name
        return user

    user = User(
        id=stable_id("user", email),
        email=email,
        display_name=settings.debugsql_dev_user_name,
        auth_mode="dev",
        last_login_at=now,
    )
    session.add(user)
    session.flush()
    return user


def upsert_email_user(session: Session, email: str) -> User:
    normalized = normalize_email(email)
    now = utc_now()
    user = session.execute(select(User).where(User.email == normalized)).scalar_one_or_none()
    if user:
        user.auth_mode = "email"
        user.last_login_at = now
        return user

    user = User(
        id=stable_id("user", normalized),
        email=normalized,
        display_name=normalized.split("@", 1)[0],
        auth_mode="email",
        last_login_at=now,
    )
    session.add(user)
    session.flush()
    return user


def latest_pending_email_code(session: Session, email: str) -> EmailLoginCode | None:
    normalized = normalize_email(email)
    return session.execute(
        select(EmailLoginCode)
        .where(EmailLoginCode.email == normalized, EmailLoginCode.status == "pending")
        .order_by(desc(EmailLoginCode.created_at))
        .limit(1)
    ).scalar_one_or_none()


def expire_pending_email_codes(session: Session, email: str) -> None:
    normalized = normalize_email(email)
    records = session.execute(
        select(EmailLoginCode).where(EmailLoginCode.email == normalized, EmailLoginCode.status == "pending")
    ).scalars()
    for record in records:
        record.status = "expired"


def get_user_by_session_token(session: Session, token: str | None) -> User | None:
    if not token:
        return None
    now = datetime.now(timezone.utc)
    record = session.execute(
        select(SessionRecord).where(
            SessionRecord.session_token_hash == token_hash(token),
            SessionRecord.status == "active",
        )
    ).scalar_one_or_none()
    if not record:
        return None
    expires_at = record.expires_at
    if expires_at and expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at and expires_at < now:
        record.status = "expired"
        return None
    return session.get(User, record.user_id)


def resolve_request_user(session: Session, token: str | None) -> User:
    user = get_user_by_session_token(session, token)
    if user:
        return user
    settings = get_settings()
    if settings.debugsql_auto_login:
        return ensure_dev_user(session)
    raise ValueError("No authenticated user")


def create_session_record(session: Session, user: User) -> tuple[str, SessionRecord]:
    token = secrets.token_urlsafe(32)
    now = utc_now()
    record = SessionRecord(
        id=stable_id("sess", f"{user.id}:{token}"),
        user_id=user.id,
        session_token_hash=token_hash(token),
        status="active",
        expires_at=now + timedelta(days=SESSION_TTL_DAYS),
        created_at=now,
    )
    session.add(record)
    user.last_login_at = now
    session.flush()
    return token, record


def expire_session_token(session: Session, token: str | None) -> None:
    if not token:
        return
    record = session.execute(
        select(SessionRecord).where(SessionRecord.session_token_hash == token_hash(token))
    ).scalar_one_or_none()
    if record:
        record.status = "expired"


def upsert_oauth_user(
    session: Session,
    *,
    provider: str,
    provider_user_id: str,
    email: str,
    display_name: str | None,
    avatar_url: str | None,
    profile: dict[str, Any],
) -> User:
    now = utc_now()
    account = session.execute(
        select(OAuthAccount).where(
            OAuthAccount.provider == provider,
            OAuthAccount.provider_user_id == provider_user_id,
        )
    ).scalar_one_or_none()
    if account:
        user = session.get(User, account.user_id)
        if not user:
            raise ValueError("OAuth account is detached from its user.")
        user.email = user.email or email
        user.display_name = display_name or user.display_name
        user.avatar_url = avatar_url or user.avatar_url
        user.auth_mode = provider
        user.last_login_at = now
        account.provider_email = email
        account.profile = profile
        return user

    user = session.execute(select(User).where(User.email == email)).scalar_one_or_none()
    if not user:
        user = User(
            id=stable_id("user", email),
            email=email,
            display_name=display_name,
            avatar_url=avatar_url,
            auth_mode=provider,
            last_login_at=now,
        )
        session.add(user)
        session.flush()
    else:
        user.display_name = display_name or user.display_name
        user.avatar_url = avatar_url or user.avatar_url
        user.auth_mode = provider
        user.last_login_at = now

    session.add(
        OAuthAccount(
            id=stable_id("oauth", f"{provider}:{provider_user_id}"),
            user_id=user.id,
            provider=provider,
            provider_user_id=provider_user_id,
            provider_email=email,
            profile=profile,
        )
    )
    session.flush()
    return user


def user_to_dict(user: User) -> dict:
    return {
        "id": user.id,
        "email": user.email,
        "displayName": user.display_name,
        "avatarUrl": user.avatar_url,
        "authMode": user.auth_mode,
        "isAdmin": bool(user.is_admin),
    }


def dev_user_dict(persistence: str = "database") -> dict:
    settings = get_settings()
    return {
        "id": stable_id("user", settings.debugsql_dev_user_email),
        "email": settings.debugsql_dev_user_email,
        "displayName": settings.debugsql_dev_user_name,
        "avatarUrl": None,
        "authMode": "dev",
        "isAdmin": False,
        "persistence": persistence,
    }
