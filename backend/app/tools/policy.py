from __future__ import annotations

import re


_BLOCK_COMMENT = re.compile(r"/\*.*?\*/", re.DOTALL)
_LINE_COMMENT = re.compile(r"(--|#).*$", re.MULTILINE)
_DANGEROUS_KEYWORDS = re.compile(
    r"\b(attach|alter|create|delete|detach|drop|grant|insert|pragma|replace|revoke|truncate|update|vacuum)\b",
    re.IGNORECASE,
)


def is_safe_read_query(sql: str) -> bool:
    """Central read-only SQL policy for all database connectors."""
    stripped = sql.strip()
    if not stripped:
        return False

    if _BLOCK_COMMENT.search(stripped) or _LINE_COMMENT.search(stripped):
        return False

    # Allow one optional trailing semicolon, but reject stacked statements.
    without_trailing = stripped[:-1].strip() if stripped.endswith(";") else stripped
    if ";" in without_trailing:
        return False

    lowered = without_trailing.lower()
    if not (lowered.startswith("select") or lowered.startswith("with")):
        return False
    return _DANGEROUS_KEYWORDS.search(without_trailing) is None
