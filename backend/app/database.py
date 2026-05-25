from contextlib import contextmanager
from functools import lru_cache
from collections.abc import Iterator
from pathlib import Path
from urllib.parse import unquote, urlparse

from sqlalchemy import text
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import create_engine

from app.config import get_settings


class Base(DeclarativeBase):
    pass


def create_db_engine() -> Engine:
    settings = get_settings()
    _ensure_sqlite_parent_dir(settings.database_url)
    return create_engine(settings.database_url, pool_pre_ping=True)


def _ensure_sqlite_parent_dir(database_url: str) -> None:
    parsed = urlparse(database_url)
    if parsed.scheme != "sqlite":
        return
    if database_url in {"sqlite://", "sqlite:///:memory:"}:
        return

    path = unquote(parsed.path)
    if not path:
        return
    if parsed.netloc:
        path = f"//{parsed.netloc}{path}"
    if len(path) >= 4 and path[0] == "/" and path[2] == ":":
        path = path[1:]
    sqlite_path = Path(path)
    sqlite_path.parent.mkdir(parents=True, exist_ok=True)


@lru_cache(maxsize=1)
def get_engine() -> Engine:
    return create_db_engine()


@lru_cache(maxsize=1)
def get_session_factory() -> sessionmaker[Session]:
    return sessionmaker(bind=get_engine(), autoflush=False, expire_on_commit=False)


@contextmanager
def session_scope() -> Iterator[Session]:
    session = get_session_factory()()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def check_database() -> dict:
    database_type = urlparse(get_settings().database_url).scheme or "database"
    try:
        engine = get_engine()
        with engine.connect() as connection:
            value = connection.execute(text("SELECT 1")).scalar_one()
        return {"status": "ok", "database": database_type, "result": value}
    except SQLAlchemyError as exc:
        return {"status": "error", "database": database_type, "message": str(exc)}
