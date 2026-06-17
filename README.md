# DebugSQL

DebugSQL is a human-in-the-loop NL2SQL debugging system. This repository currently contains the first runnable engineering skeleton: a React frontend, a FastAPI backend, and a PostgreSQL database managed by Docker Compose.

The first milestone is intentionally simple. It proves that the deployment chain works:

```text
Browser -> Frontend -> Backend -> PostgreSQL
```

## Services

- `frontend`: React + Vite hello-world status page
- `backend`: FastAPI service with health checks, uv-managed Python dependencies, and Alembic migration scaffolding
- `postgres`: PostgreSQL 16 system database

PostgreSQL data is persisted in:

```text
data/postgres/
```

This directory is ignored by Git and survives normal container restarts and rebuilds.

Benchmark files should be stored under:

```text
data/benchmarks/
  bird/
    raw/
    processed/
    sqlite/
  spider/
    raw/
    processed/
    sqlite/
```

Only `.gitkeep` files are committed. Raw benchmark files, processed metadata, and SQLite databases should stay out of Git.

For long-term server deployment, keep benchmark files on the server data disk
and mount them into the backend container. The backend reads:

```env
BENCHMARK_DATA_DIR=/app/data/benchmarks
```

Docker Compose maps the host path with:

```env
BENCHMARK_HOST_DATA_DIR=./data/benchmarks
```

On a production-like server, set `BENCHMARK_HOST_DATA_DIR` to a durable path
such as `/data/debugsql/data/benchmarks`. Do not commit raw benchmark downloads to
Git.

## Spider Dataset Setup

1. Download the Spider dataset from https://yale-lily.github.io/spider
2. Unzip and copy these files into the correct folders:

| File/Folder | Destination |
|---|---|
| `dev.json` | `data/benchmarks/spider/raw/` |
| `tables.json` | `data/benchmarks/spider/raw/` |
| `train_spider.json` | `data/benchmarks/spider/raw/` |
| `database/` | `data/benchmarks/spider/sqlite/` |

3. Set up a virtual environment:

```bash
python -m venv venv
# Windows
venv\Scripts\activate
# Mac/Linux
source venv/bin/activate
```

4. Run the cleaning script:

```bash
python scripts/clean_spider.py
```

If the benchmark data lives outside the repository, either set
`BENCHMARK_DATA_DIR` or pass `--benchmark_dir`:

```bash
BENCHMARK_DATA_DIR=/data/debugsql/data/benchmarks python scripts/clean_spider.py
python scripts/clean_spider.py --benchmark_dir /data/debugsql/data/benchmarks
```

5. Cleaned files will be saved to `data/benchmarks/spider/processed/`

> Note: Raw Spider files and SQLite databases are excluded from Git due to size limits.

## BIRD Dataset Setup

1. Download the BIRD dev dataset from https://bird-bench.github.io/

2. Unzip and copy these files into the correct folders:

| File/Folder       | Destination                    |
| ----------------- | ------------------------------ |
| `dev.json`        | `data/benchmarks/bird/raw/`    |
| `dev_tables.json` | `data/benchmarks/bird/raw/`    |
| `dev_databases/`  | `data/benchmarks/bird/sqlite/` |

3. Run the cleaning script:

```bash
python scripts/clean_bird.py
```

If the benchmark data lives outside the repository, either set
`BENCHMARK_DATA_DIR` or pass `--benchmark_dir`:

```bash
BENCHMARK_DATA_DIR=/data/debugsql/data/benchmarks python scripts/clean_bird.py
python scripts/clean_bird.py --benchmark_dir /data/debugsql/data/benchmarks
```

4. Cleaned files will be saved to:

```text
data/benchmarks/bird/processed/
```

Generated outputs include:

* `clean_dev.json`
* `clean_schema.json`
* `cleaning_report.json`

> Note: Raw BIRD files and SQLite databases are excluded from Git due to size limits.

## Quick Start

Create local environment variables:

```bash
cp .env.example .env
```

For the Linux demo server, use the server template instead:

```bash
cp .env.server.example .env
```

Then replace placeholder secrets such as `POSTGRES_PASSWORD`,
`DATABASE_URL`, `SESSION_SECRET`, and `JWT_SECRET`. Real `.env` files are
ignored by Git; only the example templates should be committed.

Start all services:

```bash
docker compose up -d --build
```

Apply database migrations:

```bash
docker compose exec backend alembic upgrade head
```

After the server is initialized, deploy later updates with:

```bash
bash scripts/deploy_server.sh
```

Check backend:

```bash
curl http://localhost:8000/health
curl http://localhost:8000/db-health
curl http://localhost:8000/auth/me
curl http://localhost:8000/hello
```

PostgreSQL is bound to localhost by default for host-side inspection tools:

```bash
pgcli postgresql://debugsql:debugsql_dev_password@127.0.0.1:5432/debugsql
```

The Compose mapping is intentionally localhost-only:

```yaml
127.0.0.1:${POSTGRES_HOST_PORT:-5432}:5432
```

Do not expose PostgreSQL on `0.0.0.0` for the demo server.

Open frontend:

```text
http://localhost:5173
```

## Local Development Without Docker

Use this mode when developing in PyCharm, VS Code, or a local terminal. Run the
backend and frontend in two separate terminals. Local development uses a SQLite
file by default, so PostgreSQL is not required just to run the app.

The default local database file is:

```text
data/dev/debugsql.sqlite
```

The helper scripts below create this directory and set:

```text
DATABASE_URL=sqlite:///.../data/dev/debugsql.sqlite
```

Run migrations once after creating or resetting the SQLite database:

```powershell
$repo = (Get-Location).Path
New-Item -ItemType Directory -Force -Path "$repo\data\dev" | Out-Null
$env:DATABASE_URL="sqlite:///$($repo.Replace('\','/'))/data/dev/debugsql.sqlite"
cd backend
.\.venv\Scripts\alembic.exe upgrade head
```

If you want to test against PostgreSQL locally, start only the database service
and override `DATABASE_URL` before running the backend:

```powershell
docker compose up -d postgres
$env:DATABASE_URL="postgresql+psycopg://debugsql:debugsql_dev_password@127.0.0.1:5432/debugsql"
cd backend
.\.venv\Scripts\alembic.exe upgrade head
```

The Docker-internal hostname `postgres` only works from containers, not from
PyCharm or a host terminal. Server deployment continues to use PostgreSQL.

### Windows / PyCharm

From the repository root:

```powershell
.\scripts\start_backend.ps1
```

Open a second terminal:

```powershell
.\scripts\start_frontend.ps1
```

Then open:

```text
http://127.0.0.1:5173
```

The frontend dev server proxies `/api/*` requests to:

```text
http://127.0.0.1:8000
```

If you prefer to run commands manually:

```powershell
$repo = "C:\projects\CP683\debugsql"
cd backend
$env:PYTHONPATH="C:\projects\CP683\debugsql\backend"
$env:DATABASE_URL="sqlite:///$($repo.Replace('\','/'))/data/dev/debugsql.sqlite"
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

```powershell
cd frontend
$env:VITE_DEV_API_TARGET="http://127.0.0.1:8000"
npm run dev -- --host 127.0.0.1
```

### macOS / Linux

From the repository root:

```bash
./scripts/start_backend.sh
```

Open a second terminal:

```bash
./scripts/start_frontend.sh
```

Then open:

```text
http://127.0.0.1:5173
```

Manual commands:

```bash
cd backend
export PYTHONPATH="$(pwd)"
export DATABASE_URL="sqlite:///$(cd .. && pwd)/data/dev/debugsql.sqlite"
python -m alembic upgrade head
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

```bash
cd frontend
export VITE_DEV_API_TARGET="http://127.0.0.1:8000"
npm run dev -- --host 127.0.0.1
```

### Notes

- Backend: `http://127.0.0.1:8000`
- Frontend: `http://127.0.0.1:5173`
- API proxy: frontend `/api/*` -> backend `http://127.0.0.1:8000`
- Mock services are disabled by default. Set `VITE_USE_MOCK_SERVICES=true` only for isolated frontend testing.
- Spider SQLite execution requires the Spider files under `data/benchmarks/spider/`.

## Remote Linux Server

If deploying to a remote Linux server, update `.env` before building:

```env
FRONTEND_PORT=80
VITE_API_BASE_URL=/api
CORS_ORIGINS=http://SERVER_IP,http://SERVER_IP:80,http://localhost:5173,http://127.0.0.1:5173
APP_BASE_URL=http://SERVER_IP/api
FRONTEND_BASE_URL=http://SERVER_IP
DEBUGSQL_AUTO_LOGIN=0
BENCHMARK_HOST_DATA_DIR=/data/debugsql/data/benchmarks
BENCHMARK_DATA_DIR=/app/data/benchmarks
EMAIL_DEV_LOG_CODES=0
QUERY_PLAN_PROVIDER=gemini
GEMINI_API_KEY=...
GEMINI_MODEL=gemini-2.0-flash
```

Use `DEBUGSQL_AUTO_LOGIN=1` only for private local debugging. The server should
normally use email verification login with `DEBUGSQL_AUTO_LOGIN=0`. Set
`EMAIL_DEV_LOG_CODES=1` only while debugging email delivery, because it prints
login codes in backend logs.

Create the durable server data directories before starting Compose:

```bash
mkdir -p /data/debugsql/data/benchmarks/{bird,spider}/{raw,processed,sqlite}
mkdir -p /data/debugsql/data/postgres
```

The recommended long-term benchmark layout is:

```text
/data/debugsql/data/benchmarks/
  bird/
    raw/
      dev.json
      dev_tables.json
    processed/
      clean_dev.json
      clean_schema.json
      cleaning_report.json
    sqlite/
      card_games/card_games.sqlite
      ...
  spider/
    raw/
      dev.json
      tables.json
      train_spider.json
    processed/
      clean_dev.json
      clean_train.json
      clean_schema.json
      cleaning_report.json
    sqlite/
      database/
        activity_1/activity_1.sqlite
        ...
```

Run cleaning on the host after downloading or replacing benchmark files. The
cleaning scripts use only the Python standard library:

```bash
python3 scripts/clean_spider.py --benchmark_dir /data/debugsql/data/benchmarks
python3 scripts/clean_bird.py --benchmark_dir /data/debugsql/data/benchmarks
docker compose restart backend
```

Then open:

```text
http://SERVER_IP
```

## Project Layout

```text
debugsql/
  backend/
    app/
    Dockerfile
    requirements.txt
  frontend/
    src/
    Dockerfile
    package.json
  docker-compose.yml
  .env.example
  data/
    .gitkeep
    benchmarks/
  README.md
```

## Current MVP Endpoints

```text
GET /health
GET /db-health
GET /hello
GET /auth/me
POST /auth/logout
POST /auth/email/request-code
POST /auth/email/verify-code
GET /benchmarks
GET /benchmarks/spider/databases
GET /capabilities
POST /tools/execute
POST /query
POST /execute
GET /execute/{run_id}/result
GET /history/summary
GET /history/conversations/{conversation_id}
POST /planning/generate
POST /evaluation/run
GET /evaluation/runs/{run_id}
```

Note: `/query-plan/*` endpoints remain in the backend for legacy debugging, but the primary UI is now the
tool-assisted chat + Capabilities Explorer.

Email verification login uses cookie-backed sessions stored in the system
database. Configure these variables before disabling dev auto-login:

```env
SESSION_SECRET=replace_with_a_long_random_value
AUTH_COOKIE_NAME=debugsql_session
EMAIL_LOGIN_CODE_TTL_MINUTES=10
EMAIL_LOGIN_RESEND_SECONDS=60
EMAIL_LOGIN_MAX_ATTEMPTS=5
EMAIL_DEV_LOG_CODES=1
SMTP_HOST=
SMTP_PORT=587
SMTP_USERNAME=
SMTP_PASSWORD=
SMTP_FROM=DebugSQL <no-reply@debugsql.local>
SMTP_USE_TLS=1
SMTP_USE_SSL=0
```

For 163 Mail, prefer implicit SSL on port 465:

```env
SMTP_HOST=smtp.163.com
SMTP_PORT=465
SMTP_USERNAME=debugsql@163.com
SMTP_PASSWORD=replace_with_163_smtp_authorization_code
SMTP_FROM=DebugSQL <debugsql@163.com>
SMTP_USE_TLS=0
SMTP_USE_SSL=1
```

If `SMTP_HOST` is empty and `EMAIL_DEV_LOG_CODES=1`, verification codes are
printed in backend logs for local/server smoke testing.

## IR-to-Plan Provider

The IR-to-query-plan layer is intentionally replaceable. The backend exposes a stable internal contract:

```text
generate_plan(intent_ir, schema_context, options) -> QueryPlan
```

Provider selection is controlled by environment variables:

```env
IR_TO_PLAN_PROVIDER=internal
IR_TO_PLAN_API_URL=
IR_TO_PLAN_API_KEY=
IR_TO_PLAN_TIMEOUT_SECONDS=30
```

Supported provider slots:

```text
internal  default in-process relational planner for proposal demos
stub      local deterministic baseline for offline frontend/backend development
http      future external API owned by another team
```

The first internal implementation delegates to the deterministic relational planner, but keeps the provider boundary stable for a later algorithm package. It generates a connected relational plan chain:

```text
Intent -> Scan -> Filter -> Join -> Group By -> Aggregate -> Sort -> Limit -> Result Data
```

Only nodes implied by the Intent IR are included. All providers must return the same normalized `QueryPlan` shape:

```json
{
  "plan_id": "plan_stub_001",
  "plan_type": "tree",
  "data_source_type": "relational",
  "nodes": [],
  "edges": [],
  "executable": {
    "type": "sql",
    "dialect": "sqlite",
    "content": "SELECT ..."
  },
  "warnings": [],
  "metadata": {}
}
```

Example request:

```bash
curl -X POST http://localhost:8000/planning/generate \
  -H "Content-Type: application/json" \
  -d '{
    "intent_ir": {
      "intent_type": "aggregation",
      "table": "sales",
      "target_columns": ["amount"],
      "group_by": ["region"],
      "aggregation": "sum",
      "filters": [{"column": "year", "op": "=", "value": 2024}]
    },
    "schema_context": {"tables": [{"name": "sales"}]},
    "options": {"data_source_type": "relational", "plan_type": "tree", "dialect": "sqlite"}
  }'
```

## Backend Development

The backend keeps `requirements.txt` for Docker compatibility and also includes `pyproject.toml` for the intended `uv` workflow.

Install backend dependencies without Docker:

```bash
cd backend
uv venv
source .venv/bin/activate
uv pip install -r requirements.txt
```

Run the backend locally:

```bash
uv run uvicorn app.main:app --reload
```

Alembic is already scaffolded for future database migrations:

```bash
uv run alembic upgrade head
```

Current persistence coverage:

* dev auto-login user (`/auth/me`)
* conversations and messages
* SQL execution runs (read-only)
* operation logs

Development history endpoint:

```bash
curl http://127.0.0.1:8000/history/summary
```

LLM provider for the chat-driven data assistant:

```bash
NL2IR_PROVIDER=stub
QUERY_PLAN_PROVIDER=gemini
GEMINI_API_KEY=...
GEMINI_MODEL=gemini-2.0-flash
```

The current runtime is chat-driven. The user selects a BIRD/Spider SQLite
database, asks a question, reviews the proposed read-only SQL, validates it,
and approves execution. Gemini is the first implemented LLM SQL provider, but
the configuration is intentionally provider-shaped so another provider can be
added later without changing the frontend/backend API. KDDCup remains in the
repository as an optional legacy NL2IR provider, but it is not called by the
default runtime.

Optional legacy KDDCup data-agent provider:

```bash
NL2IR_PROVIDER=kddcup
KDDCUP_AGENT_MODEL=gpt-4.1-mini
KDDCUP_AGENT_API_BASE=https://api.openai.com/v1
KDDCUP_LLM_API_KEY=...
KDDCUP_AGENT_MAX_STEPS=8
```

`KDDCUP_LLM_API_KEY` is an **LLM (OpenAI-compatible) API key**, not a key
issued by the KDDCup website. The vendored baseline is a ReAct agent: it uses an
LLM to reason step by step before producing SQL, so it needs a key to call
`KDDCUP_AGENT_MODEL`. `KDDCUP_AGENT_API_BASE` can target any OpenAI-compatible
endpoint. The legacy name `KDDCUP_AGENT_API_KEY` still works as a
backward-compatible alias.

If KDDCup is explicitly enabled without a key, the backend returns an
inspectable `agent_trace_error` IR and marks the plan as `needs_replan` instead
of inventing fake SQL.

Evaluation endpoint:

```bash
curl -X POST http://127.0.0.1:8000/evaluation/run \
  -H "Content-Type: application/json" \
  -d '{"benchmark":"bird","dbId":"card_games","limit":10}'
```

The MVP evaluation computes first-pass execution accuracy, placeholder repair
metrics (DRR/IRR/EI until controlled edits are supplied), timing, and error type
distribution for BIRD/Spider subsets.

## Next Steps

1. Improve Gemini answer quality and result summarization for BIRD/Spider.
2. Feed controlled edit scenarios into DRR/IRR/EI evaluation.
3. Add streaming execution progress and cancellation.

