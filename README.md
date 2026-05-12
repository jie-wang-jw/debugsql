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

## Quick Start

Create local environment variables:

```bash
cp .env.example .env
```

Start all services:

```bash
docker compose up -d --build
```

Check backend:

```bash
curl http://localhost:8000/health
curl http://localhost:8000/db-health
curl http://localhost:8000/hello
```

Open frontend:

```text
http://localhost:5173
```

## Remote Linux Server

If deploying to a remote Linux server, update `.env` before building:

```env
FRONTEND_PORT=80
VITE_API_BASE_URL=/api
CORS_ORIGINS=http://SERVER_IP,http://SERVER_IP:80,http://localhost:5173,http://127.0.0.1:5173
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
uv run alembic revision --autogenerate -m "init schema"
uv run alembic upgrade head
```

## Next Steps

1. Add dev-mode auto-login.
2. Add user/session database tables.
3. Add conversation API.
4. Add chat UI.
5. Add dataset listing.
6. Add `NL2IR_PROVIDER=stub`.
7. Add query-plan tree UI.
8. Add Inspector node editing.
9. Add SQLite benchmark execution.
10. Add real NL-to-IR provider integration.
