#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${1:-/data/debugsql}"

echo "[deploy] App directory: ${APP_DIR}"
cd "${APP_DIR}"

if [[ ! -f docker-compose.yml ]]; then
  echo "[deploy] docker-compose.yml not found in ${APP_DIR}" >&2
  exit 1
fi

if [[ ! -f .env ]]; then
  echo "[deploy] .env not found in ${APP_DIR}; copy .env.server.example first" >&2
  exit 1
fi

echo "[deploy] Pulling latest code"
git pull --ff-only

echo "[deploy] Building and starting containers"
docker compose up -d --build

echo "[deploy] Applying database migrations"
docker compose exec backend alembic upgrade head

echo "[deploy] Done"
