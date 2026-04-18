# EduTrack

Full-stack adaptive learning platform built from `PLAN.md`.

## Run Verification

The harness uses Docker PostgreSQL with pgvector, Redis, FastAPI's in-process test client, real WebSocket traffic, eager Celery task execution, deterministic LLM/RAG generation, and an XGBoost training upgrade after 50 labeled sessions. If the Docker daemon is unavailable, it falls back to a SQLite verification database while still using Redis, Celery eager tasks, WebSockets, deterministic RAG/profile generation, and XGBoost.

```bash
chmod +x scripts/verify.sh
./scripts/verify.sh
```

The deterministic LLM provider is used only for repeatable local verification. Set `EDUTRACK_OPENROUTER_API_KEY` and `EDUTRACK_LLM_PROVIDER=openrouter` to use OpenRouter in runtime environments.

## Security Note

The implementation stays on Next.js 14 as requested. As of the current npm advisory set, `npm audit` reports high-severity advisories in the Next 14 line that require a major Next upgrade to remediate.
