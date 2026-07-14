from __future__ import annotations

import json
from typing import Any


class PromptBuilder:
    """Builds LLM prompts for answer-first SQL generation."""

    SYSTEM_INSTRUCTION = (
        "You are a SQL planning assistant for DebugSQL. "
        "Given a natural-language question and optional database schema, "
        "produce a concise user answer and SQLite-compatible SELECT SQL. "
        "When the schema describes semantic SQL operators, use those operators exactly as documented. "
        "Return only JSON matching the required schema. "
        "Do not wrap the response in markdown fences."
    )

    def build(
        self,
        message: str,
        schema_context: dict[str, Any] | None = None,
        dialect: str = "sqlite",
        working_state: dict[str, Any] | None = None,
        conversation_history: list[dict[str, Any]] | None = None,
    ) -> tuple[str, str]:
        schema_block = self._format_schema(schema_context)
        history_block = self._format_conversation_history(conversation_history)
        context_block = self._format_working_state(working_state)
        user_prompt = (
            f"{history_block}"
            f"{context_block}"
            f"Current user request:\n{message.strip()}\n\n"
            f"SQL dialect: {dialect}\n"
            f"{schema_block}\n"
            "Respond with JSON containing:\n"
            '- "mode": one of "new_query", "refine_query", "schema_answer", "clarify"\n'
            '- "can_answer": boolean; false when the question is ambiguous or unsupported\n'
            '- "answer": one short user-facing answer or proposal\n'
            '- "sql": a single read-only SELECT/WITH statement, or null when can_answer is false\n'
            '- "explanation": concise explanation of tables, filters, joins, grouping, or limits\n'
            '- "assumptions": array of assumptions made about the user request\n'
            '- "tables_used": array of table names used by the SQL\n'
            '- "confidence": number from 0 to 1\n'
            '- "clarifying_question": question to ask the user when can_answer is false\n'
            '- "steps": optional brief planning steps with integer "id", "title", and "description"\n'
            "Use mode=refine_query only when the current request clearly modifies the previous working query. "
            "For refine_query, rewrite the previous SQL into a complete new SQL statement. "
            "Use mode=schema_answer for schema/table/column questions that do not need SQL. "
            "If the schema does not support the request, set can_answer=false and do not invent SQL."
        )
        return self.SYSTEM_INSTRUCTION, user_prompt

    def _format_conversation_history(self, conversation_history: list[dict[str, Any]] | None) -> str:
        if not conversation_history:
            return ""
        lines = [
            "Full conversation history for this user/session:",
            "Use this history to resolve follow-up requests, but never execute SQL without approval.",
        ]
        for item in conversation_history:
            role = str(item.get("role") or "unknown").strip().lower()
            content = self._truncate(str(item.get("content") or "").strip(), 1500)
            if not content:
                continue
            lines.append(f"- {role}: {content}")
            sql = str(item.get("sql") or "").strip()
            if sql:
                lines.append(f"  SQL: {self._truncate(sql, 1200)}")
        block = "\n".join(lines)
        return self._truncate(block, 12000) + "\n\n"

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

        semantic = schema_context.get("semanticSql")
        if isinstance(semantic, dict):
            lines.extend(["", "Semantic SQL support:"])
            instructions = str(semantic.get("instructions") or "").strip()
            if instructions:
                lines.append(f"- {instructions}")
            operators = semantic.get("operators") or []
            if operators:
                lines.append(f"- Available operators: {', '.join(str(item) for item in operators)}")
            example = str(semantic.get("exampleSql") or "").strip()
            if example:
                lines.append(f"- Example semantic SQL:\n{example}")

        return "\n".join(lines)

    def _format_working_state(self, working_state: dict[str, Any] | None) -> str:
        if not working_state:
            return ""
        lines = [
            "Previous working query context:",
            f"- Original question: {self._truncate(str(working_state.get('original_question') or ''), 500)}",
            f"- Latest request: {self._truncate(str(working_state.get('latest_user_request') or ''), 500)}",
        ]
        sql = str(working_state.get("current_sql") or "").strip()
        if sql:
            lines.append(f"- Previous SQL:\n{self._truncate(sql, 2000)}")
        explanation = str(working_state.get("explanation") or "").strip()
        if explanation:
            lines.append(f"- Previous explanation: {self._truncate(explanation, 700)}")
        assumptions = working_state.get("assumptions") or []
        if assumptions:
            lines.append(f"- Previous assumptions: {self._truncate(json.dumps(assumptions, default=str), 500)}")
        latest_result = str(working_state.get("latest_result_summary") or "").strip()
        if latest_result:
            lines.append(f"- Latest execution result summary: {self._truncate(latest_result, 700)}")
        return "\n".join(lines) + "\n\n"

    def _truncate(self, value: str, limit: int) -> str:
        if len(value) <= limit:
            return value
        return value[: max(0, limit - 3)] + "..."

    def response_json_schema(self) -> dict[str, Any]:
        """JSON schema requested from the configured LLM provider."""
        return {
            "type": "object",
            "properties": {
                "mode": {"type": "string", "enum": ["new_query", "refine_query", "schema_answer", "clarify"]},
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
            "required": ["mode", "can_answer", "answer", "sql", "explanation", "assumptions", "tables_used", "confidence"],
        }

    def schema_as_json(self) -> str:
        return json.dumps(self.response_json_schema(), indent=2)
