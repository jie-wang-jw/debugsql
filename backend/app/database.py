from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import create_engine

from app.config import get_settings


def create_db_engine() -> Engine:
    settings = get_settings()
    return create_engine(settings.database_url, pool_pre_ping=True)


def check_database() -> dict:
    try:
        engine = create_db_engine()
        with engine.connect() as connection:
            value = connection.execute(text("SELECT 1")).scalar_one()
        return {"status": "ok", "database": "postgres", "result": value}
    except SQLAlchemyError as exc:
        return {"status": "error", "database": "postgres", "message": str(exc)}
