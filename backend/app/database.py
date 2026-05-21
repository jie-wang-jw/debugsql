from contextlib import contextmanager
from functools import lru_cache
from collections.abc import Iterator

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
    return create_engine(settings.database_url, pool_pre_ping=True)


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
    try:
        engine = get_engine()
        with engine.connect() as connection:
            value = connection.execute(text("SELECT 1")).scalar_one()
        return {"status": "ok", "database": "postgres", "result": value}
    except SQLAlchemyError as exc:
        return {"status": "error", "database": "postgres", "message": str(exc)}
