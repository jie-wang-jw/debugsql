from __future__ import annotations

from app.tools.connector_base import DatabaseConnector
from app.tools.connectors.multimodal_demo import MultimodalDemoConnector
from app.tools.connectors.craigslist import CraigslistConnector
from app.tools.connectors.postgres import PostgresConnector
from app.tools.connectors.sqlite_benchmark import BenchmarkSQLiteConnector
from app.tools.schemas import DatasetContext


_CONNECTORS: dict[str, DatabaseConnector] = {
    "sqlite_benchmark": BenchmarkSQLiteConnector(),
    "postgres": PostgresConnector(),
    "multimodal_demo": MultimodalDemoConnector(),
    "craigslist": CraigslistConnector(),
}


def normalize_context(raw: dict | DatasetContext | None) -> DatasetContext:
    if isinstance(raw, DatasetContext):
        return raw
    payload = raw or {}
    db_type = payload.get("dbType") or payload.get("db_type")
    if not db_type:
        db_type = "sqlite_benchmark" if payload.get("benchmark") else "postgres"
    return DatasetContext(
        dbType=db_type,
        benchmark=payload.get("benchmark"),
        dbId=payload.get("dbId") or payload.get("db_id"),
    )


def get_connector(context: DatasetContext) -> DatabaseConnector:
    connector = _CONNECTORS.get(context.dbType)
    if connector is None:
        raise ValueError(f"Unsupported database type '{context.dbType}'.")
    return connector
