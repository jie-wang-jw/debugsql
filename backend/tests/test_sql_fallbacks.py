from __future__ import annotations

import app.conversation.sql_resolver as sql_resolver
from app.simple_nl2sql import build_simple_schema_nl2sql
from app.tools.schemas import DatasetContext


def test_simple_fallback_accepts_structured_column_metadata() -> None:
    result = build_simple_schema_nl2sql(
        "show price from the furniture table",
        {
            "tables": [
                {
                    "name": "furniture",
                    "columns": [{"name": "aid"}, {"name": "title"}, {"name": "price"}],
                }
            ]
        },
    )

    assert result is not None
    assert 'SELECT "price"' in result.sql
    assert "{'name':" not in result.sql


def test_craigslist_does_not_use_non_semantic_fallback_when_llm_fails(monkeypatch) -> None:
    monkeypatch.setattr(sql_resolver, "_should_use_llm", lambda: True)
    monkeypatch.setattr(sql_resolver, "_resolve_with_llm", lambda *_args, **_kwargs: None)

    result = sql_resolver.resolve_sql_for_message(
        "Show red furniture images sorted by price",
        DatasetContext(dbType="craigslist", benchmark="craigslist", dbId="craigslist"),
        {
            "tables": [
                {
                    "name": "furniture",
                    "columns": [{"name": "aid"}, {"name": "title"}, {"name": "price"}],
                }
            ]
        },
    )

    assert result.sql is None
    assert result.provider == "none"
    assert "no fallback SQL was generated" in (result.answer or "")
