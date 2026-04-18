#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

export EDUTRACK_REDIS_URL="${EDUTRACK_REDIS_URL:-redis://localhost:6389/0}"
export EDUTRACK_CELERY_TASK_ALWAYS_EAGER=1
export EDUTRACK_LLM_PROVIDER=deterministic
export EDUTRACK_XGBOOST_MIN_SAMPLES=50
export PYTHONPATH="$ROOT_DIR/backend"

cd "$ROOT_DIR"
if docker info >/dev/null 2>&1; then
  export EDUTRACK_DATABASE_URL="${EDUTRACK_DATABASE_URL:-postgresql+asyncpg://edutrack:edutrack@localhost:54328/edutrack}"
  docker compose up -d postgres redis

  for _ in $(seq 1 60); do
    if docker compose exec -T postgres pg_isready -U edutrack -d edutrack >/dev/null 2>&1; then
      break
    fi
    sleep 1
  done

  for _ in $(seq 1 60); do
    if docker compose exec -T redis redis-cli ping >/dev/null 2>&1; then
      break
    fi
    sleep 1
  done
  DB_MODE=postgres
else
  echo "Docker daemon unavailable; using SQLite verification database and local Redis."
  mkdir -p "$ROOT_DIR/backend/.verify"
  rm -f "$ROOT_DIR/backend/.verify/edutrack.db"
  export EDUTRACK_DATABASE_URL="sqlite+aiosqlite:///$ROOT_DIR/backend/.verify/edutrack.db"
  if command -v redis-cli >/dev/null 2>&1 && redis-cli -p 6389 ping >/dev/null 2>&1; then
    true
  elif command -v redis-server >/dev/null 2>&1; then
    redis-server --port 6389 --daemonize yes --dir "$ROOT_DIR/backend/.verify" --save "" --appendonly no
  else
    echo "redis-server is required when Docker is unavailable." >&2
    exit 1
  fi
  DB_MODE=sqlite
fi

cd "$ROOT_DIR/backend"
uv sync --group dev
mkdir -p .verify
if [ "$DB_MODE" = "postgres" ]; then
  uv run alembic upgrade head
else
  uv run python scripts/create_schema.py
fi
uv run pytest -q
EDUTRACK_DATABASE_URL=postgresql+asyncpg://edutrack:edutrack@localhost:54328/edutrack uv run alembic upgrade head --sql > .verify/postgres_migration.sql
grep -q "PARTITION BY RANGE (server_ts)" .verify/postgres_migration.sql
grep -q "vector_cosine_ops" .verify/postgres_migration.sql
grep -q "CREATE EXTENSION IF NOT EXISTS vector" .verify/postgres_migration.sql

cd "$ROOT_DIR/frontend"
npm install
npm run typecheck
npm run build

echo "EduTrack verification completed."
