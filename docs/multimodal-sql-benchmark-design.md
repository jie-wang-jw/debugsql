# Multimodal SQL Benchmark — Design Draft

Status: **design only, no code changes yet**
Scope: unified benchmark registry + capability model, and a `semantic_sql` parse→rewrite layer for `NL_FILTER` / `NL_JOIN` with **hybrid** execution semantics.

This document is grounded in the current code:

- `backend/app/benchmark_registry.py` — Spider/BIRD registry (hardcoded IDs, filesystem-driven)
- `backend/app/multimodal/registry.py` + `multimodal/query_planner.py` + `multimodal/retrieval.py` — multimodal demo (keyword retrieval → `VALUES` CTE)
- `backend/app/tools/registry.py` + `tools/connectors/multimodal_demo.py` — connector layer (dbType → execution backend)
- `backend/app/tools/schemas.py` — `DatasetContext`, `ConnectorCapabilities`, `CapabilitiesResponse`
- `frontend/src/components/capabilities/CapabilitiesPanel.tsx` — capability display

---

## 0. Problem recap

We want to extend the "database benchmark" idea (Spider/BIRD) to image/audio/video, and support SQL-like queries with **AI predicates** (`NL_FILTER`, `NL_JOIN`) in `WHERE`/`JOIN`.

Three concrete gaps in today's code:

1. **Three parallel registries**, none unified:
   - `benchmark_registry.list_benchmarks()` returns a hardcoded `[spider, bird]` list.
   - `multimodal/registry.dataset_info()` returns a single `multimodal_demo` dataset, exposed under a *separate* API (`/multimodal/datasets`).
   - `tools/registry._CONNECTORS` maps `dbType` → connector.
   Adding a new benchmark (COCO, MultiModalQA, Clotho) today means editing all three.

2. **No SQL parser.** Every SQL transform is regex/string (`demo_pipeline._replace_sql_limit`, `benchmark_registry._is_safe_read_query`, `tools/policy.is_safe_read_query`, frontend `SQLPreview.tsx` tokenizer marked TODO). There is no place to recognize a semantic operator.

3. **Semantics live outside SQL.** `multimodal/query_planner._build_sql` runs keyword retrieval first, then injects results as a `WITH media_matches(asset_id, score) AS (VALUES ...)` CTE. NL predicates are computed *before* SQL runs; SQL itself has no notion of them.

The design below turns (3) from an implicit, hardcoded shape into an explicit operator that a rewriter produces — while **reusing the exact `VALUES`-CTE mechanism that already works**.

---

## 1. Unified benchmark registry + capability model

### 1.1 Descriptor (new module: `backend/app/benchmarks/descriptor.py`)

```python
from typing import Literal
from pydantic import BaseModel, Field

Modality = Literal["table", "text", "image", "audio", "video"]
Capability = Literal[
    "structured_sql",          # plain relational SQL
    "cross_table_join",        # FK / multi-table joins
    "image_semantic_predicate",
    "audio_semantic_predicate",
    "video_semantic_predicate",
    "ai_fuzzy_match",          # NL_FILTER / NL_JOIN available
]

class BenchmarkDescriptor(BaseModel):
    id: str                                  # "spider" | "bird" | "multimodal_demo" | "multimodalqa" ...
    label: str
    status: Literal["ready", "missing", "partial"] = "missing"
    connector: str                           # dbType key in tools/registry._CONNECTORS
    modalities: list[Modality] = Field(default_factory=lambda: ["table"])
    capabilities: list[Capability] = Field(default_factory=lambda: ["structured_sql"])
    databaseCount: int = 0
    description: str = ""
    # optional, benchmark-specific extras (media counts, dataset dir, etc.)
    extra: dict = Field(default_factory=dict)
```

This is the single object the frontend needs to render the "This benchmark supports: …" panel. `capabilities` directly drives that list — no frontend hardcoding.

### 1.2 Provider protocol

Each benchmark family implements a small provider so the registry becomes extensible instead of a hardcoded switch:

```python
from typing import Protocol
from pydantic import BaseModel

class BenchmarkProvider(Protocol):
    def descriptors(self) -> list[BenchmarkDescriptor]: ...
    def list_databases(self, benchmark_id: str) -> list[dict]: ...
    def schema_context(self, benchmark_id: str, db_id: str | None) -> dict | None: ...
    def gold_sql(self, benchmark_id: str, db_id: str | None, question: str) -> str | None: ...
    # execution stays with the connector layer; provider only supplies metadata + gold
```

Concrete providers (wrap existing code, do not rewrite it):

| Provider | Wraps | Descriptor(s) produced |
|---|---|---|
| `RelationalBenchmarkProvider` | existing `benchmark_registry` fns | `spider`, `bird` — `modalities=[table]`, `capabilities=[structured_sql, cross_table_join]` |
| `MultimodalBenchmarkProvider` | existing `multimodal/registry` + connector | `multimodal_demo` — `modalities=[table,image,audio,video]`, `capabilities=[..., image/audio/video_semantic_predicate, ai_fuzzy_match, cross_table_join]` |
| (later) `MultiModalQAProvider` | new ingest | `multimodalqa` — `modalities=[table,text,image]` |

### 1.3 Registry facade (new: `backend/app/benchmarks/registry.py`)

```python
_PROVIDERS: list[BenchmarkProvider] = [
    RelationalBenchmarkProvider(),
    MultimodalBenchmarkProvider(),
]

def all_descriptors() -> list[BenchmarkDescriptor]:
    return [d for p in _PROVIDERS for d in p.descriptors()]

def find(benchmark_id: str) -> BenchmarkDescriptor | None: ...
def provider_for(benchmark_id: str) -> BenchmarkProvider | None: ...
```

### 1.4 API changes (backward compatible)

- `GET /benchmarks` → now returns unified descriptors (superset of today's `[spider, bird]` shape; keep `id/label/status/databaseCount` keys so the existing frontend selector keeps working, add `modalities`, `capabilities`, `connector`).
- `GET /multimodal/datasets` → keep as a thin alias that filters `all_descriptors()` where `connector == "multimodal_demo"` (avoids breaking `multimodal/routes.py` consumers during migration; can be deprecated later).
- `CapabilitiesResponse` (in `tools/schemas.py`) → add `benchmark: BenchmarkDescriptor | None` so the capabilities endpoint can surface `capabilities[]` to the panel.

### 1.5 Frontend (`CapabilitiesPanel.tsx`)

- `dbType` select stays, but the benchmark dropdown is populated from unified descriptors.
- Add a **"This benchmark supports"** block rendered from `descriptor.capabilities` (map capability enum → human label). This replaces any hardcoded modality text.

### 1.6 Migration ordering (keeps app green throughout)

1. Add `descriptor.py` + providers wrapping existing functions. No behavior change.
2. Point `benchmark_routes` at the facade; assert response superset compatibility with a test.
3. Add capability block to the panel.
4. Only then start adding new benchmark providers.

---

## 2. `semantic_sql`: parse → rewrite → execute

### 2.1 Dependency

Add **`sqlglot`** to `backend/pyproject.toml`. Do **not** hand-write a grammar. `sqlglot` parses `NL_FILTER(...)`/`NL_JOIN(...)` as `exp.Anonymous` function nodes out of the box, lets us walk/transform the AST, and re-emits SQLite-dialect SQL.

### 2.2 New module layout: `backend/app/semantic_sql/`

```
semantic_sql/
  __init__.py
  operators.py     # extraction of NL_FILTER / NL_JOIN nodes from an AST
  planner.py       # hybrid cost decision: UDF vs prefilter per operator
  rewriter.py      # AST -> executable SQL (+ resolver artifacts)
  udf.py           # SQLite scalar UDF registration (nl_match)
  resolver.py      # bridges operators to app.multimodal.retrieval (pluggable)
  schemas.py       # SemanticQuery, ResolvedOperator, RewriteResult
```

### 2.3 Operator syntax (the dialect surface)

```sql
NL_FILTER(<column>, '<predicate text>')            -- boolean, used in WHERE
NL_JOIN(<left_col>, <right_col>, '<predicate text>')  -- boolean, used in JOIN ... ON / WHERE
```

Optional threshold form (future): `NL_FILTER(col, 'red car', 0.6)`.

### 2.4 Data contracts (`semantic_sql/schemas.py`)

```python
class NLFilterOp(BaseModel):
    op_id: str                 # stable id, e.g. "nlf_0"
    column: str                # e.g. "media_assets.file_path" or "a.caption"
    predicate: str             # 'red car'
    threshold: float | None = None

class NLJoinOp(BaseModel):
    op_id: str
    left_col: str
    right_col: str
    predicate: str
    threshold: float | None = None

class ResolvedMatch(BaseModel):
    key: str                   # asset_id / row key on the semantic side
    score: float

class ResolvedOperator(BaseModel):
    op_id: str
    strategy: Literal["udf", "prefilter"]
    matches: list[ResolvedMatch] = Field(default_factory=list)  # prefilter only

class RewriteResult(BaseModel):
    sql: str                                    # final executable SQLite SQL
    resolved: list[ResolvedOperator]
    udf_registrations: list[str]                # op_ids needing a UDF bound at exec time
    explanation: str
    assumptions: list[str] = Field(default_factory=list)
```

### 2.5 Hybrid execution strategy (your choice)

The planner picks **per operator**:

| Condition | Strategy | Why |
|---|---|---|
| `NL_JOIN` (any) | **prefilter** | join is a cross product; per-row model calls explode. Resolve pairs first, inject as `VALUES` CTE. |
| `NL_FILTER` on a table whose estimated row count ≤ `PREFILTER_ROW_THRESHOLD` (default 500) | **prefilter** | small candidate set; batch the resolver once, inject `VALUES`, deterministic + cacheable. |
| `NL_FILTER` on a large table, or combined with other non-semantic filters that already narrow rows | **udf** | let SQLite drive row selection; UDF called only on rows that survive other predicates. |
| Resolver has no per-row callable (e.g. pure precomputed index) | **prefilter** | fall back. |

Threshold + strategy overridable via config (`config.py`): `semantic_sql_prefilter_row_threshold`, `semantic_sql_force_strategy`.

Row-count estimate source: connector `sample_rows`/introspection metadata; for the multimodal demo it's tiny, so it will use UDF or prefilter equivalently — correctness is identical, only the plan shape differs.

### 2.6 Rewrite — prefilter path (reuses existing `VALUES` CTE)

Given:

```sql
SELECT e.name, e.price, a.file_path
FROM entities e
JOIN media_assets a ON a.entity_id = e.id
WHERE e.price < 100
  AND NL_FILTER(a.file_path, 'a red backpack')
```

Rewriter:

1. Extract `NLFilterOp(op_id="nlf_0", column="a.file_path", predicate="a red backpack")`.
2. Call `resolver.resolve_filter(op)` → `search_media('a red backpack', ...)` (existing `multimodal/retrieval.search_media`) → list of `(asset_id, score)`.
3. Replace the `NL_FILTER(...)` boolean node with a membership test against an injected CTE, and add the CTE:

```sql
WITH nlf_0(match_key, score) AS (
  VALUES ('img_004', 0.83), ('img_009', 0.71)
)
SELECT e.name, e.price, a.file_path, nlf_0.score AS nlf_0_score
FROM entities e
JOIN media_assets a ON a.entity_id = e.id
JOIN nlf_0 ON nlf_0.match_key = a.id           -- key column resolved from the operator's table
WHERE e.price < 100
ORDER BY nlf_0.score DESC;
```

This is **exactly** the structure `multimodal/query_planner._build_sql` already emits — we are generalizing it, not inventing it. The `_media_previews` logic in `multimodal_demo.py` already keys off `asset_id`/`score`, so previews keep working if the rewriter exposes those columns.

### 2.7 Rewrite — UDF path

1. Register a scalar UDF on the in-memory connection at execution time:

```python
def nl_match(op_id: str, value: str) -> int:
    return 1 if resolver.match_row(op_id, value) else 0
conn.create_function("nl_match", 2, nl_match)  # deterministic=True where supported
```

2. Rewrite `NL_FILTER(a.file_path, 'red car')` → `nl_match('nlf_0', a.file_path) = 1`, and pass `op_id → predicate` binding via `RewriteResult.udf_registrations`.
3. `resolver.match_row` uses the same term-overlap logic as `search_media` today (single-row scoring), with an in-process LRU cache keyed by `(op_id, value)` so repeated values don't recompute.

> Note: SQLite UDFs can't take extra bound context easily, so the predicate is looked up by `op_id` from a per-execution resolver registry — not passed inline. This keeps the SQL clean and cache keys stable.

### 2.8 Execution integration

Add strategy in the connector, not a new execution engine. In `MultimodalDemoConnector.execute_readonly` (and later a shared base):

```python
def execute_readonly(self, context, sql, max_rows=100):
    if semantic_sql.contains_operators(sql):
        rewrite = semantic_sql.rewrite(sql, resolver=self._resolver(context),
                                       schema=self.introspect_schema(context))
        with sqlite3.connect(":memory:") as conn:
            _load_demo_tables(conn)
            semantic_sql.bind_udfs(conn, rewrite)     # no-op if all prefilter
            cursor = conn.execute(rewrite.sql)
            ...
        # attach rewrite.explanation / assumptions to the result payload
    else:
        # existing plain path
```

`benchmark_registry.execute_benchmark_sql` (Spider/BIRD) does **not** get semantic operators — its descriptor lacks the `ai_fuzzy_match` capability, so the planner/policy rejects `NL_*` there with a clear error.

### 2.9 Safety / policy

- Extend `tools/policy.is_safe_read_query` awareness: `NL_FILTER`/`NL_JOIN` are allowed **only** when the active descriptor has `ai_fuzzy_match`. Otherwise return a friendly "this benchmark does not support AI predicates" error.
- The rewriter emits only `SELECT/WITH`; it must never introduce DDL/DML. Add a post-rewrite assertion that the output still passes `is_safe_read_query`.
- UDF is read-only by construction (returns int), registered per-connection on the ephemeral in-memory DB.

### 2.10 Resolver is pluggable (future embeddings)

`resolver.py` defines:

```python
class SemanticResolver(Protocol):
    def resolve_filter(self, op: NLFilterOp) -> list[ResolvedMatch]: ...   # prefilter
    def match_row(self, op_id: str, value: str) -> bool: ...               # udf
    def resolve_join(self, op: NLJoinOp) -> list[tuple[str, str, float]]:  # prefilter
```

Phase-2 default impl = today's keyword overlap (`multimodal/retrieval`). Swapping to CLIP/audio embeddings later means one new resolver class; **no SQL-interface change**.

---

## 3. First vertical slice — ThalamusDB cars (`image_sql_demo`)

Goal: prove `parse → rewrite → execute → frontend preview` end-to-end on data we already have (`data/multimodal_demo/metadata/assets.json` has `thalamusdb_cars` images).

1. Reuse existing entities/assets tables (no schema change needed for cars).
2. Implement `NL_FILTER` only (skip `NL_JOIN` in this slice).
3. Wire `MultimodalDemoConnector` through `semantic_sql` (section 2.8) with the keyword resolver.
4. Add example query to the connector's `exampleQuestions` / capability examples:
   ```sql
   SELECT e.name, e.price, a.file_path
   FROM entities e JOIN media_assets a ON a.entity_id = e.id
   WHERE NL_FILTER(a.caption, 'a red car')
   ```
5. Confirm `mediaPreviews` still render (they key on `asset_id` + `score`, which the rewrite preserves).

Acceptance: user issues the `NL_FILTER` query in chat → run_sql tool → previews show red-car images ranked by score.

---

## 4. Phase 2 — MultiModalQA subset (registry extensibility + join)

- New `MultiModalQAProvider` producing descriptor `modalities=[table,text,image]`.
- Ingest script `scripts/clean_multimodalqa.py` mirroring `clean_spider.py`/`clean_bird.py`: map MMQA context → `entities` (Wikipedia entities / table rows) + `media_assets` (images), write `processed/` JSON.
- Use this to exercise `NL_JOIN` and `cross_table_join`. MMQA's multi-hop questions validate registry + join, **not** single-predicate accuracy (cars demo covers that).

---

## 5. What this design deliberately does NOT do

- No new execution engine — SQLite stays the executor; we only rewrite SQL and (optionally) bind a UDF.
- No frontend SQL grammar parser yet — `SQLPreview.tsx` tokenizer TODO is out of scope; backend `sqlglot` is the source of truth.
- No embedding/vision model in phase 1 — resolver stays keyword-overlap behind a swappable interface.
- Spider/BIRD paths are untouched except for being surfaced through the unified registry facade.

---

## 6. Open decisions to confirm before coding

1. **Descriptor location** — new `app/benchmarks/` package vs. extending `benchmark_registry.py` in place. (Recommend new package; leave old module as a thin provider wrapper.)
2. **`/multimodal/datasets` deprecation timeline** — keep as alias indefinitely, or migrate frontend fully to `/benchmarks`?
3. **Key-column resolution for prefilter join** — for `NL_FILTER(a.file_path, ...)` the CTE joins on `a.id`. We need a convention mapping the operator's column's table → its primary key. Propose: resolver returns matches keyed by the semantic table's PK, and rewriter reads PK from `introspect_schema`.
4. **Threshold semantics** — is `NL_FILTER(col, pred)` a hard boolean (top-N by score with a cutoff) or always score-ranked with `ORDER BY`? Propose: boolean membership via cutoff (`threshold`, default from config), plus expose `<op_id>_score` column for ordering.
