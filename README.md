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
such as `/data/debugsql/benchmarks`. Do not commit raw benchmark downloads to
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
BENCHMARK_DATA_DIR=/data/debugsql/benchmarks python scripts/clean_spider.py
python scripts/clean_spider.py --benchmark_dir /data/debugsql/benchmarks
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
BENCHMARK_DATA_DIR=/data/debugsql/benchmarks python scripts/clean_bird.py
python scripts/clean_bird.py --benchmark_dir /data/debugsql/benchmarks
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

Start all services:

```bash
docker compose up -d --build
```

Apply database migrations:

```bash
docker compose exec backend alembic upgrade head
```

Check backend:

```bash
curl http://localhost:8000/health
curl http://localhost:8000/db-health
curl http://localhost:8000/auth/me
curl http://localhost:8000/hello
```

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
DEBUGSQL_AUTO_LOGIN=1
BENCHMARK_HOST_DATA_DIR=/data/debugsql/benchmarks
BENCHMARK_DATA_DIR=/app/data/benchmarks
```

`DEBUGSQL_AUTO_LOGIN=1` is suitable for the current private demo server. Change
it to `0` after GitHub/Google OAuth is configured for real user testing.

Create the durable server data directories before starting Compose:

```bash
mkdir -p /data/debugsql/benchmarks/{bird,spider}/{raw,processed,sqlite}
mkdir -p /data/debugsql/data/postgres
```

The recommended long-term benchmark layout is:

```text
/data/debugsql/benchmarks/
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
python3 scripts/clean_spider.py --benchmark_dir /data/debugsql/benchmarks
python3 scripts/clean_bird.py --benchmark_dir /data/debugsql/benchmarks
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
GET /auth/github/login
GET /auth/github/callback
GET /auth/google/login
GET /auth/google/callback
GET /benchmarks
GET /benchmarks/spider/databases
POST /query
GET /query-plan/{plan_id}
PATCH /query-plan/{plan_id}/nodes/{node_id}
POST /execute
GET /execute/{run_id}/result
GET /history/summary
GET /history/conversations/{conversation_id}
POST /planning/generate
```

OAuth login uses cookie-backed sessions stored in the system database. Configure
these variables before disabling dev auto-login:

```env
SESSION_SECRET=replace_with_a_long_random_value
AUTH_COOKIE_NAME=debugsql_session
GITHUB_CLIENT_ID=
GITHUB_CLIENT_SECRET=
GOOGLE_CLIENT_ID=
GOOGLE_CLIENT_SECRET=
```

## IR-to-Plan Provider

The IR-to-query-plan layer is intentionally replaceable. The backend exposes a stable internal contract:

```text
generate_plan(intent_ir, schema_context, options) -> QueryPlan
```

Provider selection is controlled by environment variables:

```env
IR_TO_PLAN_PROVIDER=stub
IR_TO_PLAN_API_URL=
IR_TO_PLAN_API_KEY=
IR_TO_PLAN_TIMEOUT_SECONDS=30
```

Supported provider slots:

```text
stub      local deterministic baseline for frontend/backend development
http      future external API owned by another team
internal  future in-process Python package or algorithm module
```

The first implementation uses `StubIRToPlanProvider`. It generates a simple relational plan chain:

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
* generated query plans
* Inspector plan edits
* SQL and step-by-step execution runs
* operation logs

Development history endpoint:

```bash
curl http://127.0.0.1:8000/history/summary
```

## Next Steps

1. Replace the deterministic demo NL2SQL path with a real NL-to-IR provider.
2. Expand Spider/BIRD benchmark execution beyond exact sample-question matching.
3. Add evaluation scripts for Execution Accuracy, DRR, IRR, and edit counts.
4. Add richer Inspector JSON editing for complex IR payloads.
5. Add streaming execution progress and cancellation.

