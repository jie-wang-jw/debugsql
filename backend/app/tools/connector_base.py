from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from app.tools.schemas import ConnectorCapabilities, DatasetContext


class DatabaseConnector(ABC):
    """Pluggable connector for multi-DB introspection and read-only execution."""

    @abstractmethod
    def capabilities(self) -> ConnectorCapabilities:
        raise NotImplementedError

    @abstractmethod
    def list_tables(self, context: DatasetContext) -> list[dict[str, Any]]:
        raise NotImplementedError

    @abstractmethod
    def describe_table(self, context: DatasetContext, table: str) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def get_relationships(self, context: DatasetContext) -> list[dict[str, Any]]:
        raise NotImplementedError

    @abstractmethod
    def sample_rows(
        self,
        context: DatasetContext,
        table: str,
        limit: int = 5,
    ) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def introspect_schema(self, context: DatasetContext) -> dict[str, Any]:
        raise NotImplementedError

    def explain_sql(self, context: DatasetContext, sql: str) -> dict[str, Any]:
        return {"supported": False, "plan": None, "message": "EXPLAIN is not supported for this connector."}

    def validate_sql(self, sql: str) -> dict[str, Any]:
        from app.tools.policy import is_safe_read_query

        safe = is_safe_read_query(sql)
        return {
            "valid": safe,
            "readOnly": safe,
            "message": "Query passes read-only policy." if safe else "Only SELECT/WITH read-only queries are allowed.",
        }

    @abstractmethod
    def execute_readonly(self, context: DatasetContext, sql: str, max_rows: int = 100) -> dict[str, Any]:
        raise NotImplementedError
