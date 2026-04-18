# EduTrack Test Suite

Three layers:

- **Backend unit + integration (`backend/tests/`)** — pytest + pytest-asyncio. Hits the real DB (SQLite fallback OK) and Redis.
- **Frontend component + API client (`frontend/tests/`)** — Vitest + React Testing Library + jsdom. No live backend.
- **End-to-end (`frontend/e2e/`)** — Playwright against a running backend + frontend.

## Backend

Layout:

```
backend/tests/
  conftest.py               # resets DB + Redis between tests; shared fixtures
  test_full_workflow.py     # existing integration scenario
  unit/                     # pure-function coverage
    test_security.py            # bcrypt + JWT
    test_settings.py            # llm_provider resolution
    test_schemas.py             # Pydantic validation
    test_materials_helpers.py
    test_ml_pure.py             # clamp, flatten_features, heuristic_score
    test_tracking_features.py   # compute_features
    test_profile_pure.py        # parse/normalize/deterministic profile
    test_rag_pure.py            # deterministic embedding + section rewrites
  api/                      # FastAPI route contracts
    test_main.py, test_auth.py, test_classes.py, test_materials.py,
    test_quizzes.py, test_tracking.py, test_profiles.py, test_lessons.py
  integration/              # service layer against real DB
    test_tracking_service.py, test_rag_service.py,
    test_ml_service.py, test_profile_service.py,
    test_full_pipeline.py
  workers/
    test_tasks.py           # all 6 Celery tasks (eager mode)
```

Running (same env as `scripts/verify.sh`):

```bash
cd backend
export EDUTRACK_DATABASE_URL="sqlite+aiosqlite:///$(pwd)/.verify/edutrack.db"
export EDUTRACK_REDIS_URL="redis://localhost:6389/0"
export EDUTRACK_CELERY_TASK_ALWAYS_EAGER=1
export EDUTRACK_LLM_PROVIDER=deterministic
export PYTHONPATH="$(pwd)"
uv run python scripts/create_schema.py  # or: uv run alembic upgrade head
uv run pytest -q
```

Target a single layer: `uv run pytest tests/unit -q`.

## Frontend

Install new dev deps once: `npm install` under `frontend/`.

```bash
cd frontend
npm test                    # Vitest (one-shot)
npm run test:watch
```

Uses `jsdom`, mocks `fetch` and `WebSocket`. No backend required.

## E2E (Playwright)

Requires the app running locally (`./scripts/run.sh`). Install browsers once:

```bash
cd frontend
npx playwright install
npm run test:e2e
```

Override with `E2E_BACKEND_URL` / `E2E_FRONTEND_URL` env vars if the servers live elsewhere.

Scenarios:

- `auth.spec.ts` — register redirects to dashboard; wrong password shows error.
- `educator_flow.spec.ts` — educator class + lesson appears on dashboard.
- `student_quiz_flow.spec.ts` — enroll → lesson page → submit quiz → score.
- `researcher_analytics.spec.ts` — researcher can read class.
