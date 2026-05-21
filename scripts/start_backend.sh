#!/usr/bin/env bash
set -e

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND="$ROOT/backend"
PYTHON="$BACKEND/.venv/bin/python"

cd "$BACKEND"
export PYTHONPATH="$BACKEND"
mkdir -p "$ROOT/data/dev"
export DATABASE_URL="${DATABASE_URL:-sqlite:///$ROOT/data/dev/debugsql.sqlite}"
export DEBUGSQL_AUTO_LOGIN="${DEBUGSQL_AUTO_LOGIN:-1}"

if [ ! -x "$PYTHON" ]; then
  echo "Backend virtual environment was not found at $PYTHON"
  echo "Create it with: python3 -m venv .venv"
  exit 1
fi

"$PYTHON" -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
