from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class SimpleNL2SQLResult:
    intent_ir: dict[str, Any]
    sql: str
    explanation: str


def build_simple_schema_nl2sql(
    message: str,
    schema_context: dict[str, Any] | None,
) -> SimpleNL2SQLResult | None:
    """Small schema-aware NL2SQL fallback for demos before the real provider is connected."""
    if not schema_context:
        return None

    text = _normalize(message)
    tables = [table for table in schema_context.get("tables", []) if table.get("name")]
    if not tables:
        return None

    table = _choose_table(text, tables)
    if not table:
        return None

    table_name = str(table["name"])
    columns = [str(column) for column in table.get("columns", []) if column and column != "*"]
    lower_columns = {column.lower(): column for column in columns}

    limit = _extract_limit(text) or (10 if _is_top_query(text) else None)
    mentioned_columns = _mentioned_columns(text, columns)
    group_by = _group_by_columns(text, columns)

    if _is_count_query(text):
        sql = f"SELECT COUNT(*) AS row_count\nFROM {_quote_identifier(table_name)}"
        intent_ir = _intent(
            message=message,
            table=table_name,
            target_columns=["*"],
            aggregation="count",
            group_by=[],
            limit=None,
        )
        return SimpleNL2SQLResult(
            intent_ir=intent_ir,
            sql=f"{sql};",
            explanation=f"Demo fallback counted rows in table `{table_name}`.",
        )

    aggregation = _aggregation(text)
    metric = _choose_metric(text, columns)
    if aggregation and metric:
        target_columns = [metric]
        select_parts = []
        if group_by:
            select_parts.extend(_quote_identifier(column) for column in group_by)
        alias = f"{aggregation}_{metric}"
        select_parts.append(f"{aggregation.upper()}({_quote_identifier(metric)}) AS {_quote_identifier(alias)}")
        sql_parts = [
            f"SELECT {', '.join(select_parts)}",
            f"FROM {_quote_identifier(table_name)}",
        ]
        if group_by:
            sql_parts.append(f"GROUP BY {', '.join(_quote_identifier(column) for column in group_by)}")
        if _is_top_query(text):
            sql_parts.append(f"ORDER BY {_quote_identifier(alias)} DESC")
        if limit:
            sql_parts.append(f"LIMIT {limit}")
        intent_ir = _intent(
            message=message,
            table=table_name,
            target_columns=target_columns,
            aggregation=aggregation,
            group_by=group_by,
            order_by={"column": alias, "direction": "DESC"} if _is_top_query(text) else None,
            limit=limit,
        )
        return SimpleNL2SQLResult(
            intent_ir=intent_ir,
            sql=";\n".join(["\n".join(sql_parts)]).rstrip(";") + ";",
            explanation=f"Demo fallback generated an aggregate query over `{table_name}`.",
        )

    selected_columns = mentioned_columns or _default_columns(columns)
    if not selected_columns:
        selected_columns = ["*"]

    filters = _build_filters(text, columns)
    if filters:
        selected_columns = ["*"]

    sql_parts = [
        "SELECT " + ", ".join("*" if column == "*" else _quote_identifier(column) for column in selected_columns),
        f"FROM {_quote_identifier(table_name)}",
    ]
    if filters:
        sql_parts.append("WHERE " + " AND ".join(filters))
    order_column = _choose_order_column(text, columns)
    if order_column:
        sql_parts.append(f"ORDER BY {_quote_identifier(order_column)} DESC")
    if limit:
        sql_parts.append(f"LIMIT {limit}")

    intent_ir = _intent(
        message=message,
        table=table_name,
        target_columns=selected_columns,
        aggregation=None,
        group_by=[],
        order_by={"column": order_column, "direction": "DESC"} if order_column else None,
        limit=limit,
        filters=filters,
    )
    return SimpleNL2SQLResult(
        intent_ir=intent_ir,
        sql="\n".join(sql_parts) + ";",
        explanation=f"Demo fallback selected columns from table `{table_name}`.",
    )


def can_generate_simple_schema_nl2sql(message: str, schema_context: dict[str, Any] | None) -> bool:
    return build_simple_schema_nl2sql(message, schema_context) is not None


def _intent(
    *,
    message: str,
    table: str,
    target_columns: list[str],
    aggregation: str | None,
    group_by: list[str],
    order_by: dict[str, str] | None = None,
    limit: int | None = None,
    filters: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "intent_type": "schema_fallback",
        "table": table,
        "target_columns": target_columns,
        "group_by": group_by,
        "filters": filters or [],
        "aggregation": aggregation,
        "order_by": order_by,
        "limit": limit,
        "raw_query": message,
        "needs_clarification": False,
        "provider": "simple_schema_fallback",
    }


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower().strip())


def _choose_table(text: str, tables: list[dict[str, Any]]) -> dict[str, Any] | None:
    explicit = _explicit_table(text, tables)
    if explicit:
        return explicit

    table_scores: list[tuple[int, dict[str, Any]]] = []
    for index, table in enumerate(tables):
        name = str(table.get("name", ""))
        tokens = _name_tokens(name)
        score = 0
        for token in tokens:
            if _contains_word(text, token) or _contains_word(text, _singular(token)):
                score += 4
        for column in table.get("columns", []):
            for token in _name_tokens(str(column)):
                if len(token) > 2 and _contains_word(text, token):
                    score += 1
        if score:
            table_scores.append((score * 100 - index, table))
    if table_scores:
        return max(table_scores, key=lambda item: item[0])[1]
    if _is_generic_schema_query(text):
        return tables[0]
    return None


def _explicit_table(text: str, tables: list[dict[str, Any]]) -> dict[str, Any] | None:
    patterns = (
        r"\bin (?:the )?([a-zA-Z_][\w]*)\s+table\b",
        r"\bfrom (?:the )?([a-zA-Z_][\w]*)\s+table\b",
        r"\btable ([a-zA-Z_][\w]*)\b",
    )
    for pattern in patterns:
        match = re.search(pattern, text)
        if not match:
            continue
        candidate = match.group(1).lower()
        for table in tables:
            name = str(table.get("name", "")).lower()
            if candidate == name or candidate == _singular(name):
                return table
    return None


def _build_filters(text: str, columns: list[str]) -> list[str]:
    filters: list[str] = []
    seen: set[str] = set()

    for literal in _extract_quoted_literals(text):
        clause = _literal_filter_clause(literal, columns)
        if clause and clause not in seen:
            filters.append(clause)
            seen.add(clause)

    named = _extract_named_entity(text, columns)
    if named:
        column, value = named
        clause = f"{_quote_identifier(column)} = {_quote_literal(value)}"
        if clause not in seen:
            filters.append(clause)
            seen.add(clause)

    return filters


def _extract_quoted_literals(message: str) -> list[str]:
    literals: list[str] = []
    for match in re.finditer(r'"([^"]+)"|\'([^\']+)\'', message):
        value = (match.group(1) or match.group(2) or "").strip()
        if value:
            literals.append(value)
    return literals


def _extract_named_entity(text: str, columns: list[str]) -> tuple[str, str] | None:
    for column in columns:
        col_lower = column.lower()
        patterns = (
            rf"\b{re.escape(col_lower)}\s+(?:is|are|named|called)\s+([a-zA-Z][\w .'-]+)",
            rf"\bby\s+{re.escape(col_lower)}\s+([a-zA-Z][\w .'-]+)",
            rf"\bfor\s+(?:the\s+)?{re.escape(col_lower)}\s+([a-zA-Z][\w .'-]+)",
            rf"\bthe\s+{re.escape(col_lower)}\s+([a-zA-Z][\w .'-]+)",
        )
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                value = match.group(1).strip()
                value = re.split(r"\s+(?:in|from|on|with|where|and|or)\b", value, maxsplit=1)[0].strip()
                if value:
                    return column, value
    return None


def _literal_filter_clause(literal: str, columns: list[str]) -> str | None:
    preferred = [column for column in columns if column.lower() in {"artist", "name", "title", "author"}]
    search_columns = preferred or columns[:3]
    if not search_columns:
        return None
    if len(search_columns) == 1:
        column = search_columns[0]
        return f"{_quote_identifier(column)} = {_quote_literal(literal)}"
    parts = [
        f"LOWER({_quote_identifier(column)}) LIKE LOWER({_quote_literal(f'%{literal}%')})"
        for column in search_columns
    ]
    return "(" + " OR ".join(parts) + ")"


def _quote_literal(value: str) -> str:
    escaped = value.replace("'", "''")
    return f"'{escaped}'"


def _mentioned_columns(text: str, columns: list[str]) -> list[str]:
    return [
        column
        for column in columns
        if any(_contains_word(text, token) for token in _name_tokens(column))
    ][:6]


def _group_by_columns(text: str, columns: list[str]) -> list[str]:
    by_match = re.search(r"\bby\s+([a-zA-Z0-9_ ]+)$", text)
    if not by_match:
        return []
    phrase = by_match.group(1)
    return [
        column
        for column in columns
        if any(_contains_word(phrase, token) for token in _name_tokens(column))
    ][:3]


def _choose_metric(text: str, columns: list[str]) -> str | None:
    mentioned = _mentioned_columns(text, columns)
    numeric_hint = ("amount", "total", "price", "cost", "score", "age", "count", "number", "size")
    for column in mentioned:
        lowered = column.lower()
        if any(hint in lowered for hint in numeric_hint):
            return column
    return mentioned[0] if mentioned else None


def _choose_order_column(text: str, columns: list[str]) -> str | None:
    if not _is_top_query(text):
        return None
    preferred = ("id", "amount", "total", "price", "score", "date", "year")
    mentioned = _mentioned_columns(text, columns)
    for column in mentioned + columns:
        lowered = column.lower()
        if any(hint in lowered for hint in preferred):
            return column
    return columns[0] if columns else None


def _default_columns(columns: list[str]) -> list[str]:
    return columns[:5]


def _aggregation(text: str) -> str | None:
    if any(term in text for term in ("average", "avg", "mean")):
        return "avg"
    if any(term in text for term in ("sum", "total")):
        return "sum"
    if any(term in text for term in ("max", "highest", "largest")):
        return "max"
    if any(term in text for term in ("min", "lowest", "smallest")):
        return "min"
    return None


def _is_count_query(text: str) -> bool:
    return bool(re.search(r"\b(how many|count|number of)\b", text))


def _is_top_query(text: str) -> bool:
    return bool(re.search(r"\b(top|most|highest|largest|rank)\b", text))


def _is_generic_schema_query(text: str) -> bool:
    return _is_count_query(text) or any(term in text for term in ("show", "list", "what are", "which are", "find"))


def _extract_limit(text: str) -> int | None:
    match = re.search(r"\b(?:top|limit|first)\s+(\d{1,3})\b", text)
    if not match:
        return None
    value = int(match.group(1))
    return value if value > 0 else None


def _name_tokens(name: str) -> list[str]:
    return [token for token in re.split(r"[^a-zA-Z0-9]+", name.lower()) if token]


def _contains_word(text: str, word: str) -> bool:
    return bool(word and re.search(rf"\b{re.escape(word)}\b", text))


def _singular(token: str) -> str:
    return token[:-1] if token.endswith("s") and len(token) > 3 else token


def _quote_identifier(identifier: str) -> str:
    escaped = identifier.replace('"', '""')
    return f'"{escaped}"'
