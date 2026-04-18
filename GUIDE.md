# EduTrack Environment Guide

This project has two runtime surfaces:

- `backend/`: FastAPI, Celery, PostgreSQL/pgvector, Redis, OpenRouter.
- `frontend/`: Next.js 14 browser app.

Backend settings are read with the `EDUTRACK_` prefix from environment variables or a `.env` file in the backend process working directory. Frontend settings are read by Next.js from `NEXT_PUBLIC_*` variables.

## Required For Local Demo

For the current local deterministic demo:

```bash
export EDUTRACK_DATABASE_URL="sqlite+aiosqlite:///$(pwd)/backend/.verify/edutrack.db"
export EDUTRACK_REDIS_URL="redis://localhost:6389/0"
export EDUTRACK_CELERY_TASK_ALWAYS_EAGER=1
export EDUTRACK_LLM_PROVIDER=deterministic
export NEXT_PUBLIC_API_URL="http://127.0.0.1:8000"
```

When starting the backend directly from the repo root, also set:

```bash
export PYTHONPATH="$(pwd)/backend"
```

If you start the backend from `backend/`, use:

```bash
export PYTHONPATH="$(pwd)"
```

## Backend Variables

### `EDUTRACK_DATABASE_URL`

SQLAlchemy async database URL.

Default:

```bash
postgresql+asyncpg://edutrack:edutrack@localhost:54328/edutrack
```

Local Docker/Postgres:

```bash
export EDUTRACK_DATABASE_URL="postgresql+asyncpg://edutrack:edutrack@localhost:54328/edutrack"
```

Local SQLite verification fallback:

```bash
export EDUTRACK_DATABASE_URL="sqlite+aiosqlite:///$(pwd)/backend/.verify/edutrack.db"
```

Production should use PostgreSQL with pgvector:

```bash
export EDUTRACK_DATABASE_URL="postgresql+asyncpg://USER:PASSWORD@HOST:5432/DBNAME"
```

### `EDUTRACK_REDIS_URL`

Redis URL used for WebSocket event buffering and Celery broker/result backend.

Default:

```bash
redis://localhost:6389/0
```

Example:

```bash
export EDUTRACK_REDIS_URL="redis://localhost:6389/0"
```

Production example:

```bash
export EDUTRACK_REDIS_URL="redis://:PASSWORD@HOST:6379/0"
```

### `EDUTRACK_API_CORS_ORIGINS`

Allowed browser origins for the FastAPI CORS middleware.

Default:

```json
["http://localhost:3000", "http://127.0.0.1:3000"]
```

Because this is a list setting, set it as JSON:

```bash
export EDUTRACK_API_CORS_ORIGINS='["http://localhost:3000","http://127.0.0.1:3000"]'
```

Production example:

```bash
export EDUTRACK_API_CORS_ORIGINS='["https://edutrack.example.com"]'
```

### `EDUTRACK_JWT_SECRET`

Secret key used to sign access and refresh JWTs.

Default:

```bash
dev-edutrack-change-me
```

Set this in every non-local environment:

```bash
export EDUTRACK_JWT_SECRET="replace-with-a-long-random-secret"
```

Generate one:

```bash
python3 - <<'PY'
import secrets
print(secrets.token_urlsafe(64))
PY
```

### `EDUTRACK_JWT_ALGORITHM`

JWT signing algorithm.

Default:

```bash
HS256
```

Normally leave unchanged:

```bash
export EDUTRACK_JWT_ALGORITHM="HS256"
```

### `EDUTRACK_ACCESS_TOKEN_MINUTES`

Access-token lifetime in minutes.

Default:

```bash
60
```

Example:

```bash
export EDUTRACK_ACCESS_TOKEN_MINUTES=60
```

### `EDUTRACK_REFRESH_TOKEN_DAYS`

Refresh-token lifetime in days.

Default:

```bash
14
```

Example:

```bash
export EDUTRACK_REFRESH_TOKEN_DAYS=14
```

### `EDUTRACK_CELERY_TASK_ALWAYS_EAGER`

Controls whether Celery tasks run synchronously in the API process.

Default:

```bash
False
```

Use eager mode for local deterministic verification:

```bash
export EDUTRACK_CELERY_TASK_ALWAYS_EAGER=1
```

Use normal Celery workers in production:

```bash
export EDUTRACK_CELERY_TASK_ALWAYS_EAGER=0
```

When this is `0`, run a worker separately:

```bash
cd backend
uv run celery -A app.celery_app.celery_app worker --loglevel=INFO
```

### `EDUTRACK_LLM_PROVIDER`

Selects profile/RAG generation provider.

Allowed values:

```bash
auto
openrouter
deterministic
```

Default:

```bash
auto
```

Behavior:

- `auto`: uses OpenRouter if `EDUTRACK_OPENROUTER_API_KEY` is set, otherwise deterministic fallback.
- `openrouter`: always uses OpenRouter and requires `EDUTRACK_OPENROUTER_API_KEY`.
- `deterministic`: local repeatable fallback, no external LLM calls.

Local verification:

```bash
export EDUTRACK_LLM_PROVIDER=deterministic
```

Production:

```bash
export EDUTRACK_LLM_PROVIDER=openrouter
```

### `EDUTRACK_OPENROUTER_API_KEY`

OpenRouter API key.

Default:

```bash
unset
```

Required when `EDUTRACK_LLM_PROVIDER=openrouter`.

Example:

```bash
export EDUTRACK_OPENROUTER_API_KEY="sk-or-..."
```

### `EDUTRACK_OPENROUTER_BASE_URL`

OpenRouter OpenAI-compatible base URL.

Default:

```bash
https://openrouter.ai/api/v1
```

Example:

```bash
export EDUTRACK_OPENROUTER_BASE_URL="https://openrouter.ai/api/v1"
```

### `EDUTRACK_LLM_MODEL`

OpenRouter chat model used for profile generation and lesson personalization.

Default:

```bash
anthropic/claude-opus-4-7
```

Example:

```bash
export EDUTRACK_LLM_MODEL="anthropic/claude-opus-4-7"
```

You can use any OpenRouter model ID supported by your account:

```bash
export EDUTRACK_LLM_MODEL="anthropic/claude-sonnet-4.5"
```

### `EDUTRACK_EMBEDDING_MODEL`

Embedding model used when `EDUTRACK_LLM_PROVIDER=openrouter`.

Default:

```bash
openai/text-embedding-3-small
```

Example:

```bash
export EDUTRACK_EMBEDDING_MODEL="openai/text-embedding-3-small"
```

The database schema expects 1536-dimensional vectors by default. If you use a different embedding model, make sure its dimensions match `EDUTRACK_EMBEDDING_DIM` and the pgvector column dimensions.

### `EDUTRACK_EMBEDDING_DIM`

Embedding vector dimension used by deterministic embeddings and typed OpenRouter pgvector literals.

Default:

```bash
1536
```

Example:

```bash
export EDUTRACK_EMBEDDING_DIM=1536
```

Do not change this without also changing the `Vector(1536)` columns in the model and Alembic migration.

### `EDUTRACK_XGBOOST_MIN_SAMPLES`

Minimum labeled sessions required before training XGBoost models.

Default:

```bash
50
```

Example:

```bash
export EDUTRACK_XGBOOST_MIN_SAMPLES=50
```

For fast local experimentation:

```bash
export EDUTRACK_XGBOOST_MIN_SAMPLES=10
```

## Frontend Variables

### `NEXT_PUBLIC_API_URL`

Base URL for browser requests to the FastAPI backend.

Default in code:

```bash
http://localhost:8000
```

Recommended local setting when opening the app at `127.0.0.1`:

```bash
export NEXT_PUBLIC_API_URL="http://127.0.0.1:8000"
```

Production example:

```bash
export NEXT_PUBLIC_API_URL="https://api.edutrack.example.com"
```

This variable is exposed to the browser because it starts with `NEXT_PUBLIC_`.

## Verification Harness Variables

`scripts/verify.sh` sets these automatically:

```bash
export EDUTRACK_REDIS_URL="${EDUTRACK_REDIS_URL:-redis://localhost:6389/0}"
export EDUTRACK_CELERY_TASK_ALWAYS_EAGER=1
export EDUTRACK_LLM_PROVIDER=deterministic
export EDUTRACK_XGBOOST_MIN_SAMPLES=50
export PYTHONPATH="$ROOT_DIR/backend"
```

If Docker is running, it uses:

```bash
export EDUTRACK_DATABASE_URL="postgresql+asyncpg://edutrack:edutrack@localhost:54328/edutrack"
```

If Docker is unavailable, it uses:

```bash
export EDUTRACK_DATABASE_URL="sqlite+aiosqlite:///$ROOT_DIR/backend/.verify/edutrack.db"
```

The harness also generates PostgreSQL migration SQL and checks that pgvector and tracking-event partitioning are present.

## Docker Compose Variables

`docker-compose.yml` hardcodes the local Postgres container credentials:

```yaml
POSTGRES_DB: edutrack
POSTGRES_USER: edutrack
POSTGRES_PASSWORD: edutrack
```

These match the default local `EDUTRACK_DATABASE_URL`.

## Copyable Local Development Setup

Deterministic local setup:

```bash
export EDUTRACK_DATABASE_URL="postgresql+asyncpg://edutrack:edutrack@localhost:54328/edutrack"
export EDUTRACK_REDIS_URL="redis://localhost:6389/0"
export EDUTRACK_API_CORS_ORIGINS='["http://localhost:3000","http://127.0.0.1:3000"]'
export EDUTRACK_JWT_SECRET="dev-edutrack-change-me"
export EDUTRACK_CELERY_TASK_ALWAYS_EAGER=1
export EDUTRACK_LLM_PROVIDER=deterministic
export EDUTRACK_XGBOOST_MIN_SAMPLES=50
export NEXT_PUBLIC_API_URL="http://127.0.0.1:8000"
```

Start services:

```bash
docker compose up -d postgres redis

cd backend
uv sync --group dev
uv run alembic upgrade head
PYTHONPATH="$(pwd)" uv run uvicorn app.main:app --host 127.0.0.1 --port 8000
```

In another shell:

```bash
cd frontend
npm install
NEXT_PUBLIC_API_URL="http://127.0.0.1:8000" npm run dev -- --hostname 127.0.0.1 --port 3000
```

## Copyable OpenRouter Setup

```bash
export EDUTRACK_DATABASE_URL="postgresql+asyncpg://edutrack:edutrack@localhost:54328/edutrack"
export EDUTRACK_REDIS_URL="redis://localhost:6389/0"
export EDUTRACK_API_CORS_ORIGINS='["http://localhost:3000","http://127.0.0.1:3000"]'
export EDUTRACK_JWT_SECRET="replace-with-a-long-random-secret"
export EDUTRACK_CELERY_TASK_ALWAYS_EAGER=0
export EDUTRACK_LLM_PROVIDER=openrouter
export EDUTRACK_OPENROUTER_API_KEY="sk-or-..."
export EDUTRACK_OPENROUTER_BASE_URL="https://openrouter.ai/api/v1"
export EDUTRACK_LLM_MODEL="anthropic/claude-opus-4-7"
export EDUTRACK_EMBEDDING_MODEL="openai/text-embedding-3-small"
export EDUTRACK_EMBEDDING_DIM=1536
export EDUTRACK_XGBOOST_MIN_SAMPLES=50
export NEXT_PUBLIC_API_URL="http://127.0.0.1:8000"
```

With `EDUTRACK_CELERY_TASK_ALWAYS_EAGER=0`, run both the API and Celery worker.

## Production Checklist

Set these explicitly in production:

```bash
EDUTRACK_DATABASE_URL
EDUTRACK_REDIS_URL
EDUTRACK_API_CORS_ORIGINS
EDUTRACK_JWT_SECRET
EDUTRACK_CELERY_TASK_ALWAYS_EAGER=0
EDUTRACK_LLM_PROVIDER=openrouter
EDUTRACK_OPENROUTER_API_KEY
EDUTRACK_LLM_MODEL
EDUTRACK_EMBEDDING_MODEL
EDUTRACK_EMBEDDING_DIM=1536
EDUTRACK_XGBOOST_MIN_SAMPLES=50
NEXT_PUBLIC_API_URL
```

Usually leave these at defaults unless you have a reason to change them:

```bash
EDUTRACK_JWT_ALGORITHM=HS256
EDUTRACK_ACCESS_TOKEN_MINUTES=60
EDUTRACK_REFRESH_TOKEN_DAYS=14
EDUTRACK_OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
```

