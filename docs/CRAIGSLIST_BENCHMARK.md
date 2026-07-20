# Craigslist Multimodal Benchmark

## Runtime and Evaluation Boundary

The online DebugSQL service may read only these benchmark inputs:

```text
data/benchmarks/Craigslist/
  furnitures.csv
  imgs.csv
  furniture_imgs/
  queries.sql
```

Hidden annotations belong outside the runtime mount:

```text
data/evaluation/craigslist/
  craigslist_imgs_label.json
  craigslist_furnitures_title_label.json
```

Runtime modules do not import the evaluation package. Image previews are authorized by
`imgs.csv`, and preview captions come from the original listing title. The annotations are
loaded only by the explicit evaluation command after retrieval and SQL execution.

## Build the Semantic Index

Install the locked CPU dependencies, then build both indexes:

```bash
cd backend
uv sync --frozen --extra dev
python -m app.semantic_index build --benchmark craigslist
```

After the model files have been downloaded once, restricted-network hosts can
reuse the local cache without making Hugging Face metadata requests:

```bash
HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 \
  python -m app.evaluation run --benchmark craigslist --mode clip-only \
  --output data/evaluation/craigslist/clip_only_report.json
```

The server must retain or mount the Hugging Face model cache as well as the
generated index. The index contains media vectors, but query encoding still
needs the matching OpenCLIP and MiniLM model weights.

The first build downloads OpenCLIP `ViT-B-32/laion2b_s34b_b79k` and MiniLM model weights.
It reads the raw JPEG bytes, skips and reports corrupt files, and writes generated artifacts to:

```text
data/indexes/craigslist/
  image_embeddings.npy
  image_ids.json
  title_embeddings.npy
  title_ids.json
  manifest.json
  vision_scores.sqlite
```

Generated indexes, provider score caches, and model caches are not committed to Git. A repeat
build reuses vectors whose source checksum and model identity have not changed.

## Runtime Configuration

```dotenv
SEMANTIC_RESOLVER=clip_vlm
SEMANTIC_INDEX_DIR=/app/data/indexes
CLIP_MODEL=ViT-B-32
CLIP_PRETRAINED=laion2b_s34b_b79k
TEXT_EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2
CLIP_CANDIDATE_COUNT=200

VISION_PROVIDER=openai_compatible
VISION_API_BASE_URL=https://goapi.gptnb.ai/v1
VISION_API_KEY=
VISION_MODEL=gpt-4o-mini
VISION_RERANK_COUNT=24
VISION_TIMEOUT_SECONDS=60
VISION_ALLOW_CLIP_ONLY=false
```

`VISION_ALLOW_CLIP_ONLY=false` is required for benchmark mode. If the provider is unavailable,
the query fails clearly instead of using labels or returning plausible fallback matches. Set it
to `true` only when deliberately demonstrating the documented CLIP-only baseline.

## Semantic SQL

Both `NL_FILTER` and the benchmark's legacy `NL` spelling are accepted:

```sql
SELECT f.aid, f.title, f.price, i.img AS asset_id
FROM furniture AS f
JOIN images AS i ON i.aid = f.aid
WHERE f.price < 200
  AND NL_FILTER(i.img, 'blue chair')
ORDER BY nlf_0_score DESC
LIMIT 20;
```

The rewriter resolves each semantic predicate independently, creates score CTEs keyed by the
target table primary key, and uses `LEFT JOIN` membership expressions. This preserves `AND` and
`OR` semantics while still supporting joins, structured filters, aggregates, ordering, and limits.

## Evaluation

Run the two modes separately. Only these commands need access to the hidden annotation directory:

```bash
cd backend
python -m app.evaluation run --benchmark craigslist --mode clip-only \
  --output ../data/evaluation/results/craigslist-clip-only.json

python -m app.evaluation run --benchmark craigslist --mode clip+vlm \
  --output ../data/evaluation/results/craigslist-clip-vlm.json
```

Each report records the model configuration, index manifest and checksum, deterministic split,
retrieval metrics, query result comparisons, aggregate error, latency, and VLM request counts.
Provider cost remains `null` unless a stable provider pricing source is added; the report does not
invent a cost estimate.

The split is deterministic by asset ID: 20% calibration and 80% test. Test annotations do not
influence model inputs, vector construction, prompts, score caches, or resolver output.

## Server Deployment

The backend receives raw benchmark and generated index mounts separately:

```dotenv
BENCHMARK_HOST_DATA_DIR=/data/debugsql/data/benchmarks
SEMANTIC_INDEX_HOST_DIR=/data/debugsql/data/indexes
```

Build the index on a prepared machine and copy `data/indexes/craigslist/` to the server, or run the
index command inside the backend container after mounting the index directory read-write. Do not
mount `data/evaluation/` into the normal backend service.
