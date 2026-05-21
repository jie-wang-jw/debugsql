from __future__ import annotations

import hashlib

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models.auth import User, utc_now


def stable_id(prefix: str, value: str) -> str:
    digest = hashlib.sha1(value.encode("utf-8")).hexdigest()[:16]
    return f"{prefix}_{digest}"


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


def user_to_dict(user: User) -> dict:
    return {
        "id": user.id,
        "email": user.email,
        "displayName": user.display_name,
        "avatarUrl": user.avatar_url,
        "authMode": user.auth_mode,
    }


def dev_user_dict(persistence: str = "database") -> dict:
    settings = get_settings()
    return {
        "id": stable_id("user", settings.debugsql_dev_user_email),
        "email": settings.debugsql_dev_user_email,
        "displayName": settings.debugsql_dev_user_name,
        "avatarUrl": None,
        "authMode": "dev",
        "persistence": persistence,
    }
