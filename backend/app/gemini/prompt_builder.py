from __future__ import annotations

import json
from typing import Any


class PromptBuilder:
    """Builds Gemini prompts for answer-first SQL generation."""

    SYSTEM_INSTRUCTION = (
        "You are a SQL planning assistant for DebugSQL. "
        "Given a natural-language question and optional database schema, "
        "produce a concise user answer and SQLite-compatible SELECT SQL. "
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
            '- "can_answer": boolean; false when the question is ambiguous or unsupported\n'
            '- "answer": one short user-facing answer or proposal\n'
            '- "sql": a single read-only SELECT/WITH statement, or null when can_answer is false\n'
            '- "explanation": concise explanation of tables, filters, joins, grouping, or limits\n'
            '- "assumptions": array of assumptions made about the user request\n'
            '- "tables_used": array of table names used by the SQL\n'
            '- "confidence": number from 0 to 1\n'
            '- "clarifying_question": question to ask the user when can_answer is false\n'
            '- "steps": optional brief planning steps with integer "id", "title", and "description"\n'
            "If the schema does not support the request, set can_answer=false and do not invent SQL."
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
                "can_answer": {"type": "boolean"},
                "answer": {"type": "string"},
                "sql": {"type": ["string", "null"]},
                "explanation": {"type": "string"},
                "assumptions": {"type": "array", "items": {"type": "string"}},
                "tables_used": {"type": "array", "items": {"type": "string"}},
                "confidence": {"type": "number"},
                "clarifying_question": {"type": ["string", "null"]},
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
            "required": ["can_answer", "answer", "sql", "explanation", "assumptions", "tables_used", "confidence"],
        }

    def schema_as_json(self) -> str:
        return json.dumps(self.response_json_schema(), indent=2)
