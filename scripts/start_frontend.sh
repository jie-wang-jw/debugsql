#!/usr/bin/env bash
set -e

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FRONTEND="$ROOT/frontend"

cd "$FRONTEND"
export VITE_DEV_API_TARGET="http://127.0.0.1:8000"

if [ ! -d "node_modules" ]; then
  npm install
fi

npm run dev -- --host 127.0.0.1
