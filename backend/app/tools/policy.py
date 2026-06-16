from __future__ import annotations


def is_safe_read_query(sql: str) -> bool:
    """Central read-only SQL policy for all database connectors."""
    stripped = sql.strip().rstrip(";").strip()
    if not stripped:
        return False
    lowered = stripped.lower()
    if not (lowered.startswith("select") or lowered.startswith("with")):
        return False
    blocked = (
        " insert ",
        " update ",
        " delete ",
        " drop ",
        " alter ",
        " create ",
        " attach ",
        " pragma ",
        " truncate ",
        " grant ",
        " revoke ",
    )
    return not any(token in f" {lowered} " for token in blocked)
