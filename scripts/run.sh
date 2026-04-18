#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

export EDUTRACK_REDIS_URL="${EDUTRACK_REDIS_URL:-redis://localhost:6389/0}"
export EDUTRACK_API_CORS_ORIGINS="${EDUTRACK_API_CORS_ORIGINS:-[\"http://localhost:3000\",\"http://127.0.0.1:3000\"]}"
export EDUTRACK_JWT_SECRET="${EDUTRACK_JWT_SECRET:-dev-edutrack-change-me}"
export EDUTRACK_CELERY_TASK_ALWAYS_EAGER="${EDUTRACK_CELERY_TASK_ALWAYS_EAGER:-1}"
export EDUTRACK_LLM_PROVIDER="${EDUTRACK_LLM_PROVIDER:-deterministic}"
export EDUTRACK_XGBOOST_MIN_SAMPLES="${EDUTRACK_XGBOOST_MIN_SAMPLES:-50}"
export NEXT_PUBLIC_API_URL="${NEXT_PUBLIC_API_URL:-http://127.0.0.1:8000}"
export PYTHONPATH="$ROOT_DIR/backend"

BACKEND_PID=""
FRONTEND_PID=""
STARTED_REDIS=0

cleanup() {
  trap - INT TERM EXIT
  if [ -n "$FRONTEND_PID" ] && kill -0 "$FRONTEND_PID" 2>/dev/null; then
    kill "$FRONTEND_PID" 2>/dev/null || true
    wait "$FRONTEND_PID" 2>/dev/null || true
  fi
  if [ -n "$BACKEND_PID" ] && kill -0 "$BACKEND_PID" 2>/dev/null; then
    kill "$BACKEND_PID" 2>/dev/null || true
    wait "$BACKEND_PID" 2>/dev/null || true
  fi
  if [ "$STARTED_REDIS" = "1" ]; then
    redis-cli -p 6389 shutdown nosave >/dev/null 2>&1 || true
  fi
}
trap cleanup INT TERM EXIT

cd "$ROOT_DIR"
if docker info >/dev/null 2>&1; then
  export EDUTRACK_DATABASE_URL="${EDUTRACK_DATABASE_URL:-postgresql+asyncpg://edutrack:edutrack@localhost:54328/edutrack}"
  echo "==> Starting postgres + redis via docker compose"
  docker compose up -d postgres redis

  for _ in $(seq 1 60); do
    docker compose exec -T postgres pg_isready -U edutrack -d edutrack >/dev/null 2>&1 && break
    sleep 1
  done
  for _ in $(seq 1 60); do
    docker compose exec -T redis redis-cli ping >/dev/null 2>&1 && break
    sleep 1
  done
  DB_MODE=postgres
else
  echo "==> Docker unavailable; using SQLite + local redis"
  mkdir -p "$ROOT_DIR/backend/.verify"
  export EDUTRACK_DATABASE_URL="${EDUTRACK_DATABASE_URL:-sqlite+aiosqlite:///$ROOT_DIR/backend/.verify/edutrack.db}"
  if command -v redis-cli >/dev/null 2>&1 && redis-cli -p 6389 ping >/dev/null 2>&1; then
    :
  elif command -v redis-server >/dev/null 2>&1; then
    redis-server --port 6389 --daemonize yes --dir "$ROOT_DIR/backend/.verify" --save "" --appendonly no
    STARTED_REDIS=1
  else
    echo "redis-server is required when Docker is unavailable." >&2
    exit 1
  fi
  DB_MODE=sqlite
fi

echo "==> Installing backend deps"
cd "$ROOT_DIR/backend"
uv sync --group dev

echo "==> Applying migrations"
if [ "$DB_MODE" = "postgres" ]; then
  uv run alembic upgrade head
else
  uv run python scripts/create_schema.py
fi

echo "==> Starting backend on http://127.0.0.1:8000"
uv run uvicorn app.main:app --host 127.0.0.1 --port 8000 &
BACKEND_PID=$!

echo "==> Installing frontend deps"
cd "$ROOT_DIR/frontend"
if [ ! -d node_modules ]; then
  npm install
fi

echo "==> Starting frontend on http://127.0.0.1:3000"
npm run dev -- --hostname 127.0.0.1 --port 3000 &
FRONTEND_PID=$!

echo ""
echo "Backend:  http://127.0.0.1:8000   (pid $BACKEND_PID)"
echo "Frontend: http://127.0.0.1:3000   (pid $FRONTEND_PID)"
echo "Press Ctrl+C to stop."

wait -n "$BACKEND_PID" "$FRONTEND_PID"
