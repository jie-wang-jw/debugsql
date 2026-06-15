from __future__ import annotations

import json
from typing import Any


class PromptBuilder:
    """Builds Gemini prompts for structured query-plan generation."""

    SYSTEM_INSTRUCTION = (
        "You are a SQL planning assistant for DebugSQL. "
        "Given a natural-language question and optional database schema, "
        "produce a concise execution plan and SQLite-compatible SELECT SQL. "
        "Return only JSON matching the required schema. "
        "Do not wrap the response in markdown fences."
    )

    def build(
        self,
        message: str,
        schema_context: dict[str, Any] | None = None,
        dialect: str = "sqlite",
    ) -> tuple[str, str]:
        schema_block = self._format_schema(schema_context)
        user_prompt = (
            f"Natural language question:\n{message.strip()}\n\n"
            f"SQL dialect: {dialect}\n"
            f"{schema_block}\n"
            "Respond with JSON containing:\n"
            '- "goal": short summary of what the query accomplishes\n'
            '- "sql": a single read-only SELECT statement (no DDL/DML)\n'
            '- "steps": ordered planning steps with integer "id", "title", and "description"\n'
            "Use 2-8 steps that explain how to answer the question."
        )
        return self.SYSTEM_INSTRUCTION, user_prompt

    def _format_schema(self, schema_context: dict[str, Any] | None) -> str:
        if not schema_context:
            return "Database schema: not provided. Infer reasonable table/column names."

        tables = schema_context.get("tables") or []
        if not tables:
            return "Database schema: empty."

        lines = ["Database schema:"]
        for table in tables[:20]:
            name = table.get("name") or table.get("table") or "unknown"
            columns = table.get("columns") or []
            column_names = [
                column.get("name") if isinstance(column, dict) else str(column)
                for column in columns[:40]
            ]
            lines.append(f"- {name}({', '.join(column_names)})")

        return "\n".join(lines)

    def response_json_schema(self) -> dict[str, Any]:
        """JSON schema passed to Gemini structured output."""
        return {
            "type": "object",
            "properties": {
                "goal": {"type": "string"},
                "sql": {"type": "string"},
                "steps": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "id": {"type": "integer"},
                            "title": {"type": "string"},
                            "description": {"type": "string"},
                        },
                        "required": ["id", "title", "description"],
                    },
                },
            },
            "required": ["goal", "steps"],
        }

    def schema_as_json(self) -> str:
        return json.dumps(self.response_json_schema(), indent=2)
