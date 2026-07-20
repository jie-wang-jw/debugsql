from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.craigslist.registry import dataset_ready as craigslist_dataset_ready
from app.craigslist.registry import load_images
from app.database import Base, get_engine, get_session_factory
from app.gemini.openai_compatible_service import OpenAICompatibleService
from app.gemini.schemas import GeminiQueryPlan
from app.semantic_sql import (
    KeywordMediaResolver,
    SemanticSQLError,
    contains_semantic_operators,
    rewrite_semantic_sql,
)
from app.tools.connectors.multimodal_demo import (
    _SEMANTIC_TABLES,
    _TABLE_COLUMNS,
    NL_FILTER_EXAMPLE_SQL,
)
from app.tools.connectors.craigslist import NL_FILTER_EXAMPLE_SQL as CRAIGSLIST_NL_FILTER_EXAMPLE_SQL
from app.tools.policy import is_safe_read_query
from app.semantic_sql.schemas import ResolvedMatch
from app.evaluation.craigslist import load_benchmark_queries
from app.tools.connectors.craigslist import (
    _SEMANTIC_TABLES as CRAIGSLIST_SEMANTIC_TABLES,
    _TABLE_COLUMNS as CRAIGSLIST_TABLE_COLUMNS,
    _load_tables as load_craigslist_tables,
)


@pytest.fixture(autouse=True)
def isolated_sqlite(monkeypatch, tmp_path):
    db_path = tmp_path / "debugsql-test.sqlite"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")
    monkeypatch.setenv("DEBUGSQL_AUTO_LOGIN", "1")
    monkeypatch.setenv("QUERY_PLAN_PROVIDER", "stub")
    monkeypatch.setenv("GEMINI_API_KEY", "")
    monkeypatch.setenv("LLM_API_BASE_URL", "")
    monkeypatch.setenv("LLM_API_KEY", "")
    get_settings.cache_clear()
    get_engine.cache_clear()
    get_session_factory.cache_clear()

    import app.models.auth  # noqa: F401
    import app.models.history  # noqa: F401

    Base.metadata.create_all(get_engine())
    yield
    get_settings.cache_clear()
    get_engine.cache_clear()
    get_session_factory.cache_clear()


def _client() -> TestClient:
    from app.main import app

    return TestClient(app)


MULTIMODAL_CONTEXT = {"dbType": "multimodal_demo", "dbId": "multimodal_demo"}
CRAIGSLIST_CONTEXT = {"dbType": "craigslist", "benchmark": "craigslist", "dbId": "craigslist"}
SPIDER_CONTEXT = {"dbType": "sqlite_benchmark", "benchmark": "spider", "dbId": "academic"}


def _run_sql(client: TestClient, sql: str, context: dict) -> dict:
    response = client.post(
        "/tools/execute",
        json={
            "tool": "run_sql",
            "toolCallId": "pytest-semantic-sql",
            "arguments": {"sql": sql},
            "context": context,
            "approved": True,
        },
    )
    assert response.status_code == 200
    return response.json()["data"]["data"]


@pytest.fixture
def fake_craigslist_resolver(monkeypatch):
    from app.craigslist.resolver import CraigslistSemanticResolver

    image_rows = load_images()[:8]
    image_ids = [row["img"] for row in image_rows]
    title_ids = list(dict.fromkeys(row["aid"] for row in image_rows))

    def resolve(self, op):
        ids = image_ids if op.table == "images" else title_ids
        return [ResolvedMatch(key=item, score=0.9 - index * 0.01) for index, item in enumerate(ids)]

    monkeypatch.setattr(CraigslistSemanticResolver, "resolve_filter", resolve)


# ---------------------------------------------------------------------------
# Unified benchmark registry
# ---------------------------------------------------------------------------


def test_unified_benchmark_descriptors_include_supported_datasets() -> None:
    data = _client().get("/benchmarks").json()["data"]
    by_id = {item["id"]: item for item in data}
    assert {"spider", "bird", "multimodal_demo", "craigslist"} <= set(by_id)

    for benchmark_id in ("spider", "bird"):
        descriptor = by_id[benchmark_id]
        assert descriptor["connector"] == "sqlite_benchmark"
        assert descriptor["modalities"] == ["table"]
        assert "structured_sql" in descriptor["capabilities"]
        assert "ai_fuzzy_match" not in descriptor["capabilities"]
        # Legacy keys preserved for the existing frontend selector.
        assert {"id", "label", "status", "databaseCount"} <= set(descriptor)

    multimodal = by_id["multimodal_demo"]
    assert multimodal["connector"] == "multimodal_demo"
    assert {"image", "audio", "video"} <= set(multimodal["modalities"])
    assert "ai_fuzzy_match" in multimodal["capabilities"]
    assert "image_semantic_predicate" in multimodal["capabilities"]

    craigslist = by_id["craigslist"]
    assert craigslist["connector"] == "craigslist"
    assert {"table", "text", "image"} <= set(craigslist["modalities"])
    assert "ai_fuzzy_match" in craigslist["capabilities"]


def test_craigslist_database_and_capabilities_are_discoverable() -> None:
    client = _client()
    databases = client.get("/benchmarks/craigslist/databases").json()["data"]
    assert len(databases) == 1
    assert databases[0]["dbId"] == "craigslist"
    assert databases[0]["tableCount"] == 2

    capabilities = client.get(
        "/capabilities?dbType=craigslist&benchmark=craigslist&dbId=craigslist"
    ).json()["data"]
    assert capabilities["connector"]["dbType"] == "craigslist"
    assert capabilities["benchmark"]["id"] == "craigslist"
    assert {table["name"] for table in capabilities["schemaPreview"]["tables"]} == {
        "furniture",
        "images",
    }
    semantic_examples = [
        example["content"] for example in capabilities["examples"] if example["kind"] == "sql"
    ]
    assert any("NL_FILTER" in sql for sql in semantic_examples)


def test_multimodal_datasets_alias_keeps_legacy_shape_and_adds_capabilities() -> None:
    data = _client().get("/multimodal/datasets").json()["data"]
    assert len(data) == 1
    dataset = data[0]
    assert dataset["id"] == "multimodal_demo"
    assert dataset["mediaCounts"]["image"] >= 1
    assert "ai_fuzzy_match" in dataset["capabilities"]


def test_benchmark_databases_endpoint_covers_multimodal() -> None:
    data = _client().get("/benchmarks/multimodal_demo/databases").json()["data"]
    assert len(data) == 1
    assert data[0]["dbId"] == "multimodal_demo"


def test_capabilities_endpoint_surfaces_descriptor_and_labels() -> None:
    payload = _client().get("/capabilities?dbType=multimodal_demo").json()["data"]
    assert payload["benchmark"]["id"] == "multimodal_demo"
    assert "ai_fuzzy_match" in payload["benchmark"]["capabilities"]
    assert any("fuzzy" in label.lower() for label in payload["capabilityLabels"])
    example_sqls = [ex["content"] for ex in payload["examples"] if ex["kind"] == "sql"]
    assert any("NL_FILTER" in sql for sql in example_sqls)


# ---------------------------------------------------------------------------
# Capability gate: Spider/BIRD reject semantic SQL
# ---------------------------------------------------------------------------


def test_spider_rejects_nl_filter_with_friendly_message() -> None:
    result = _run_sql(
        _client(),
        "SELECT * FROM head WHERE NL_FILTER(name, 'famous person')",
        SPIDER_CONTEXT,
    )
    assert result["rows"][0]["error"] == "execution_error"
    message = result["rows"][0]["message"]
    assert "does not support AI semantic predicates" in message
    assert "no such function" not in message.lower()


def test_spider_nl_filter_run_sql_marks_tool_failed() -> None:
    response = _client().post(
        "/tools/execute",
        json={
            "tool": "run_sql",
            "toolCallId": "pytest-semantic-sql-failed-wrapper",
            "arguments": {"sql": "SELECT * FROM head WHERE NL_FILTER(name, 'famous person')"},
            "context": SPIDER_CONTEXT,
            "approved": True,
        },
    )
    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["success"] is False
    assert "does not support AI semantic predicates" in payload["error"]
    assert payload["data"]["rows"][0]["error"] == "execution_error"


def test_spider_sql_preview_flags_nl_filter_invalid() -> None:
    response = _client().post(
        "/tools/execute",
        json={
            "tool": "run_sql_preview",
            "arguments": {"sql": "SELECT * FROM head WHERE NL_FILTER(name, 'x')"},
            "context": SPIDER_CONTEXT,
        },
    )
    data = response.json()["data"]["data"]
    assert data["valid"] is False
    assert "does not support AI semantic predicates" in data["message"]


# ---------------------------------------------------------------------------
# Semantic SQL rewrite (unit level)
# ---------------------------------------------------------------------------


def _rewrite(sql: str):
    return rewrite_semantic_sql(
        sql,
        resolver=KeywordMediaResolver(),
        table_columns=_TABLE_COLUMNS,
        semantic_tables=_SEMANTIC_TABLES,
    )


def test_rewrite_produces_readonly_sql_with_cte_pk_join_and_scores() -> None:
    result = _rewrite(NL_FILTER_EXAMPLE_SQL)
    assert is_safe_read_query(result.sql)
    assert "WITH nlf_0" in result.sql
    assert "VALUES" in result.sql
    # Prefilter CTE joins on the media table primary key.
    assert "nlf_0.match_key = a.id" in result.sql
    # Boolean membership plus exposed scores.
    assert "nlf_0.score AS score" in result.sql
    assert "nlf_0.score AS nlf_0_score" in result.sql
    assert result.operators[0].predicate == "red car"
    assert result.operators[0].strategy == "prefilter"
    assert len(result.operators[0].matches) >= 1
    keys = [match.key for match in result.operators[0].matches]
    assert "img_car_red_mercedes" in keys


def test_rewrite_rejects_nl_join_with_clear_message() -> None:
    sql = (
        "SELECT e.name FROM entities e JOIN media_assets a "
        "ON NL_JOIN(e.description, a.caption, 'same object')"
    )
    with pytest.raises(SemanticSQLError, match="NL_JOIN is planned"):
        _rewrite(sql)


def test_rewrite_rejects_nl_filter_on_non_semantic_table() -> None:
    sql = "SELECT e.name FROM entities e WHERE NL_FILTER(e.description, 'red car')"
    with pytest.raises(SemanticSQLError, match="not supported"):
        _rewrite(sql)


def test_contains_semantic_operators_detection() -> None:
    assert contains_semantic_operators("SELECT * FROM t WHERE NL_FILTER(c, 'x')")
    assert contains_semantic_operators("select nl_join(a, b, 'x')")
    assert not contains_semantic_operators("SELECT name FROM entities")


def test_rewrite_preserves_or_with_left_join_membership() -> None:
    class Resolver:
        def resolve_filter(self, op):
            key = "img-a" if op.table == "images" else "aid-b"
            return [ResolvedMatch(key=key, score=0.9)]

    result = rewrite_semantic_sql(
        "SELECT * FROM images i, furniture f WHERE "
        "(NL_FILTER(i.img, 'blue chair') OR NL_FILTER(f.title_u, 'wood')) "
        "AND i.aid = f.aid",
        resolver=Resolver(),
        table_columns={"images": ["img", "aid"], "furniture": ["aid", "title_u"]},
        semantic_tables={"images": "img", "furniture": "aid"},
    )
    normalized = result.sql.upper()
    assert normalized.count("LEFT JOIN") == 2
    assert " OR " in normalized
    assert normalized.count("NOT NLF_") == 2
    assert normalized.count("IS NULL") == 2


def test_legacy_nl_alias_is_supported() -> None:
    class Resolver:
        def resolve_filter(self, op):
            return [ResolvedMatch(key="img-a", score=0.9)]

    result = rewrite_semantic_sql(
        "SELECT * FROM images WHERE nl(img, 'blue chair')",
        resolver=Resolver(),
        table_columns={"images": ["img", "aid"]},
        semantic_tables={"images": "img"},
    )
    assert "NL(" not in result.sql.upper()
    assert "LEFT JOIN" in result.sql.upper()


@pytest.mark.skipif(not craigslist_dataset_ready(), reason="Craigslist benchmark files are not installed")
def test_all_craigslist_benchmark_queries_parse_rewrite_and_execute() -> None:
    class Resolver:
        def resolve_filter(self, op):
            rows = load_images()[:12]
            ids = [row["img"] for row in rows] if op.table == "images" else list({row["aid"] for row in rows})
            return [ResolvedMatch(key=item, score=0.9) for item in ids]

    queries = load_benchmark_queries()
    assert len(queries) == 25
    with sqlite3.connect(":memory:") as connection:
        load_craigslist_tables(connection)
        for query in queries:
            rewritten = rewrite_semantic_sql(
                query.sql,
                resolver=Resolver(),
                table_columns=CRAIGSLIST_TABLE_COLUMNS,
                semantic_tables=CRAIGSLIST_SEMANTIC_TABLES,
            )
            assert "NL(" not in rewritten.sql.upper()
            connection.execute(rewritten.sql).fetchall()


# ---------------------------------------------------------------------------
# Multimodal connector end-to-end
# ---------------------------------------------------------------------------


def test_multimodal_nl_filter_end_to_end_with_previews_and_scores() -> None:
    result = _run_sql(_client(), NL_FILTER_EXAMPLE_SQL, MULTIMODAL_CONTEXT)
    assert result["rows"], "expected at least one matched row"
    row = result["rows"][0]
    assert row["asset_id"] == "img_car_red_mercedes"
    assert row["score"] > 0
    assert row["nlf_0_score"] == row["score"]

    # Executed SQL is the rewritten plain SQLite SQL.
    assert "WITH nlf_0" in result["sql"]
    assert "NL_FILTER" not in result["sql"].upper().replace("NLF_0", "")

    # Media previews keep working via asset_id/score in rows.
    previews = result["mediaPreviews"]
    assert previews and previews[0]["asset_id"] == "img_car_red_mercedes"
    assert previews[0]["preview_url"].startswith("/api/multimodal/assets/")

    semantic = result["semantic"]
    assert semantic["operators"][0]["opId"] == "nlf_0"
    assert semantic["operators"][0]["matchCount"] >= 1
    assert semantic["originalSql"] == NL_FILTER_EXAMPLE_SQL


def test_multimodal_nl_filter_without_matches_returns_empty_result() -> None:
    sql = (
        "SELECT e.name, a.id AS asset_id FROM entities e "
        "JOIN media_assets a ON a.entity_id = e.id "
        "WHERE NL_FILTER(a.caption, 'purple submarine xylophone')"
    )
    result = _run_sql(_client(), sql, MULTIMODAL_CONTEXT)
    assert result["rows"] == []
    assert result["mediaPreviews"] == []
    assert result["semantic"]["operators"][0]["matchCount"] == 0


def test_multimodal_plain_sql_path_is_unchanged() -> None:
    result = _run_sql(
        _client(),
        "SELECT name, price FROM entities ORDER BY price DESC LIMIT 3",
        MULTIMODAL_CONTEXT,
    )
    assert len(result["rows"]) == 3
    assert "semantic" not in result


@pytest.mark.skipif(not craigslist_dataset_ready(), reason="Craigslist benchmark files are not installed")
def test_craigslist_llm_semantic_sql_executes_and_returns_real_images(
    monkeypatch, fake_craigslist_resolver
) -> None:
    monkeypatch.setenv("QUERY_PLAN_PROVIDER", "openai_compatible")
    monkeypatch.setenv("LLM_API_BASE_URL", "https://example.test/v1")
    monkeypatch.setenv("LLM_API_KEY", "test-key")
    get_settings.cache_clear()

    def fake_generate(
        self,
        message,
        schema_context=None,
        working_state=None,
        conversation_history=None,
    ):
        assert "blue chair" in message.lower()
        semantic_sql = CRAIGSLIST_NL_FILTER_EXAMPLE_SQL
        return GeminiQueryPlan(
            mode="new_query",
            answer="Prepared a semantic image query.",
            sql=semantic_sql,
            explanation="Join listings to images and apply a visual NL_FILTER predicate.",
            assumptions=["Raw image embeddings and a vision reranker are used."],
            tables_used=["furniture", "images"],
            confidence=0.9,
        )

    monkeypatch.setattr(OpenAICompatibleService, "generate_query_plan", fake_generate)
    client = _client()
    query = client.post(
        "/query",
        json={
            "message": "Show blue chair images under 200 dollars",
            "sessionId": "pytest-craigslist-llm",
            "datasetContext": CRAIGSLIST_CONTEXT,
        },
    )
    assert query.status_code == 200
    proposal = query.json()["data"]
    assert proposal["sql"] == CRAIGSLIST_NL_FILTER_EXAMPLE_SQL
    run_action = next(action for action in proposal["proposedActions"] if action["tool"] == "run_sql")

    executed = client.post(
        "/tools/execute",
        json={
            "tool": "run_sql",
            "toolCallId": "pytest-craigslist-run",
            "arguments": run_action["arguments"],
            "context": CRAIGSLIST_CONTEXT,
            "approved": True,
            "sessionId": "pytest-craigslist-llm",
        },
    )
    assert executed.status_code == 200
    envelope = executed.json()["data"]
    assert envelope["success"] is True
    result = envelope["data"]
    assert result["rows"]
    assert "NL_FILTER" not in result["sql"]
    assert result["semantic"]["operators"][0]["predicate"] == "blue chair"
    assert result["mediaPreviews"]
    preview_url = result["mediaPreviews"][0]["preview_url"]
    assert preview_url.startswith("/api/craigslist/preview?img=")
    assert client.get(preview_url.removeprefix("/api")).status_code == 200


@pytest.mark.skipif(not craigslist_dataset_ready(), reason="Craigslist benchmark files are not installed")
def test_craigslist_runtime_query_never_opens_hidden_annotations(
    monkeypatch, fake_craigslist_resolver
) -> None:
    original_open = Path.open
    original_read_text = Path.read_text

    def guarded_open(path, *args, **kwargs):
        assert "_label.json" not in path.name
        return original_open(path, *args, **kwargs)

    def guarded_read_text(path, *args, **kwargs):
        assert "_label.json" not in path.name
        return original_read_text(path, *args, **kwargs)

    monkeypatch.setattr(Path, "open", guarded_open)
    monkeypatch.setattr(Path, "read_text", guarded_read_text)
    result = _run_sql(_client(), CRAIGSLIST_NL_FILTER_EXAMPLE_SQL, CRAIGSLIST_CONTEXT)
    assert result["rows"]


def test_craigslist_preview_rejects_unknown_and_traversal_paths() -> None:
    client = _client()
    assert client.get("/craigslist/preview", params={"img": "missing.jpg"}).status_code == 404
    assert client.get("/craigslist/preview", params={"img": "../../.env"}).status_code == 404


@pytest.mark.skipif(not craigslist_dataset_ready(), reason="Craigslist benchmark files are not installed")
def test_craigslist_red_furniture_example_executes_in_price_order(fake_craigslist_resolver) -> None:
    result = _run_sql(
        _client(),
        (
            "SELECT f.aid, f.title, f.price, i.img AS asset_id "
            "FROM furniture f JOIN images i ON i.aid = f.aid "
            "WHERE NL_FILTER(i.img, 'Show red furniture images sorted by price') "
            "ORDER BY f.price ASC LIMIT 20"
        ),
        CRAIGSLIST_CONTEXT,
    )

    assert result["rows"]
    prices = [row["price"] for row in result["rows"] if row["price"] is not None]
    assert prices == sorted(prices)
    assert result["mediaPreviews"]


@pytest.mark.skipif(not craigslist_dataset_ready(), reason="Craigslist benchmark files are not installed")
def test_craigslist_wooden_table_example_executes_two_semantic_filters(
    fake_craigslist_resolver,
) -> None:
    result = _run_sql(
        _client(),
        (
            "SELECT f.aid, f.title, f.price, i.img AS asset_id "
            "FROM furniture f JOIN images i ON i.aid = f.aid "
            "WHERE NL_FILTER(f.title_u, 'wooden table') "
            "AND NL_FILTER(i.img, 'table photo') "
            "ORDER BY nlf_0_score DESC, nlf_1_score DESC LIMIT 20"
        ),
        CRAIGSLIST_CONTEXT,
    )

    assert result["rows"]
    assert result["rows"][0].get("error") is None
    assert len(result["semantic"]["operators"]) == 2
    assert all(operator["matchCount"] > 0 for operator in result["semantic"]["operators"])
    assert result["mediaPreviews"]


def test_unsafe_sql_still_rejected_with_semantic_operators() -> None:
    client = _client()
    delete_result = _run_sql(
        client,
        "DELETE FROM media_assets WHERE NL_FILTER(caption, 'red car')",
        MULTIMODAL_CONTEXT,
    )
    assert delete_result["rows"][0]["error"] == "execution_error"

    stacked_result = _run_sql(
        client,
        "SELECT 1; DROP TABLE entities",
        MULTIMODAL_CONTEXT,
    )
    assert stacked_result["rows"][0]["error"] == "execution_error"


def test_nl_join_rejected_at_execution_with_friendly_message() -> None:
    result = _run_sql(
        _client(),
        (
            "SELECT e.name FROM entities e JOIN media_assets a "
            "ON NL_JOIN(e.description, a.caption, 'same object')"
        ),
        MULTIMODAL_CONTEXT,
    )
    assert "NL_JOIN is planned but not supported yet" in result["rows"][0]["message"]
