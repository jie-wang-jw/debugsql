#!/usr/bin/env bash
set -e

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND="$ROOT/backend"
PYTHON="$BACKEND/.venv/bin/python"

cd "$BACKEND"
export PYTHONPATH="$BACKEND"
export DATABASE_URL="${DATABASE_URL:-postgresql+psycopg://debugsql:debugsql_dev_password@127.0.0.1:5432/debugsql}"
export DEBUGSQL_AUTO_LOGIN="${DEBUGSQL_AUTO_LOGIN:-1}"

if [ ! -x "$PYTHON" ]; then
  echo "Backend virtual environment was not found at $PYTHON"
  echo "Create it with: python3 -m venv .venv"
  exit 1
fi

"$PYTHON" -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
