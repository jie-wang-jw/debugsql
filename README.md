# DebugSQL

DebugSQL is a human-in-the-loop NL2SQL debugging system. This repository currently contains the first runnable engineering skeleton: a React frontend, a FastAPI backend, and a PostgreSQL database managed by Docker Compose.

The first milestone is intentionally simple. It proves that the deployment chain works:

```text
Browser -> Frontend -> Backend -> PostgreSQL
```

## Services

- `frontend`: React + Vite hello-world status page
- `backend`: FastAPI service with health checks
- `postgres`: PostgreSQL 16 system database

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
CORS_ORIGINS=http://SERVER_IP:5173,http://localhost:5173,http://127.0.0.1:5173
```

Then open:

```text
http://SERVER_IP:5173
```

If `FRONTEND_PORT=80`, open:

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
  README.md
```

## Current MVP Endpoints

```text
GET /health
GET /db-health
GET /hello
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
