from __future__ import annotations

import uuid
from typing import Any

from app.tools.registry import get_connector, normalize_context
from app.tools.schemas import DatasetContext, ToolDefinition, ToolResult


TOOL_CATALOG: list[ToolDefinition] = [
    ToolDefinition(
        name="introspect_schema",
        label="Inspect schema",
        description="List tables, columns, and relationships for the selected database.",
        requiresApproval=False,
    ),
    ToolDefinition(
        name="list_tables",
        label="List tables",
        description="Return all tables available in the current database.",
        requiresApproval=False,
    ),
    ToolDefinition(
        name="describe_table",
        label="Describe table",
        description="Return column metadata for a single table.",
        requiresApproval=False,
        parameters={"table": "string"},
    ),
    ToolDefinition(
        name="sample_rows",
        label="Sample rows",
        description="Fetch a small sample of rows from a table.",
        requiresApproval=False,
        parameters={"table": "string", "limit": "integer"},
    ),
    ToolDefinition(
        name="get_relationships",
        label="Get relationships",
        description="Return foreign-key style relationships when available.",
        requiresApproval=False,
    ),
    ToolDefinition(
        name="explain_sql",
        label="Explain SQL",
        description="Run EXPLAIN for a read-only query when supported.",
        requiresApproval=False,
        parameters={"sql": "string"},
    ),
    ToolDefinition(
        name="run_sql_preview",
        label="Validate SQL",
        description="Check whether a query passes the read-only policy without executing it.",
        requiresApproval=False,
        parameters={"sql": "string"},
    ),
    ToolDefinition(
        name="run_sql",
        label="Run SQL",
        description="Execute a read-only SELECT/WITH query and return rows.",
        requiresApproval=True,
        parameters={"sql": "string"},
    ),
]


def list_tools_for_context(context: DatasetContext) -> list[ToolDefinition]:
    connector = get_connector(context)
    caps = connector.capabilities()
    tools: list[ToolDefinition] = []
    for tool in TOOL_CATALOG:
        if tool.name == "explain_sql" and not caps.supportsExplain:
            continue
        if tool.name == "sample_rows" and not caps.supportsSampleRows:
            continue
        if tool.name == "get_relationships" and not caps.supportsRelationships:
            continue
        tools.append(tool)
    return tools


def execute_tool(
    tool_name: str,
    arguments: dict[str, Any],
    context: DatasetContext | dict | None,
    *,
    approved: bool = False,
    tool_call_id: str | None = None,
) -> ToolResult:
    normalized = normalize_context(context)
    connector = get_connector(normalized)
    call_id = tool_call_id or str(uuid.uuid4())
    tool_def = next((tool for tool in TOOL_CATALOG if tool.name == tool_name), None)
    if tool_def is None:
        return ToolResult(toolCallId=call_id, tool=tool_name, success=False, error=f"Unknown tool '{tool_name}'.")

    if tool_def.requiresApproval and not approved:
        return ToolResult(
            toolCallId=call_id,
            tool=tool_name,
            success=False,
            error="This tool requires explicit user approval before execution.",
        )

    try:
        data = _dispatch_tool(connector, normalized, tool_name, arguments)
        if tool_name == "run_sql" and _execution_error_message(data):
            return ToolResult(
                toolCallId=call_id,
                tool=tool_name,
                success=False,
                data=data,
                error=_execution_error_message(data),
            )
        return ToolResult(toolCallId=call_id, tool=tool_name, success=True, data=data)
    except Exception as exc:
        return ToolResult(toolCallId=call_id, tool=tool_name, success=False, error=str(exc))


def _dispatch_tool(
    connector,
    context: DatasetContext,
    tool_name: str,
    arguments: dict[str, Any],
) -> dict[str, Any]:
    if tool_name == "introspect_schema":
        return connector.introspect_schema(context)
    if tool_name == "list_tables":
        return {"tables": connector.list_tables(context)}
    if tool_name == "describe_table":
        table = str(arguments.get("table", "")).strip()
        if not table:
            raise ValueError("describe_table requires a 'table' argument.")
        return connector.describe_table(context, table)
    if tool_name == "sample_rows":
        table = str(arguments.get("table", "")).strip()
        if not table:
            raise ValueError("sample_rows requires a 'table' argument.")
        limit = int(arguments.get("limit") or connector.capabilities().maxSampleRows)
        return connector.sample_rows(context, table, limit=limit)
    if tool_name == "get_relationships":
        return {"relationships": connector.get_relationships(context)}
    if tool_name == "explain_sql":
        sql = str(arguments.get("sql", "")).strip()
        if not sql:
            raise ValueError("explain_sql requires a 'sql' argument.")
        return connector.explain_sql(context, sql)
    if tool_name == "run_sql_preview":
        sql = str(arguments.get("sql", "")).strip()
        if not sql:
            raise ValueError("run_sql_preview requires a 'sql' argument.")
        return connector.validate_sql(sql)
    if tool_name == "run_sql":
        sql = str(arguments.get("sql", "")).strip()
        if not sql:
            raise ValueError("run_sql requires a 'sql' argument.")
        max_rows = int(arguments.get("maxRows") or connector.capabilities().maxRows)
        return connector.execute_readonly(context, sql, max_rows=max_rows)
    raise ValueError(f"Tool '{tool_name}' is not implemented.")


def _execution_error_message(data: dict[str, Any]) -> str | None:
    rows = data.get("rows")
    if not isinstance(rows, list) or not rows:
        return None
    first = rows[0]
    if not isinstance(first, dict) or first.get("error") != "execution_error":
        return None
    message = first.get("message")
    return str(message) if message else "SQL execution failed."
