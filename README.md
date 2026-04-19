# EduTrack

> See how every brain learns.

EduTrack is a full-stack adaptive learning platform that turns every reading session into a teaching signal. It watches *how* students actually read — mouse paths, scroll-back, hovers, idle gaps, re-reads, text selections — and uses that behavior to predict comprehension, build a per-student learning profile, personalize lessons via RAG, and visualize the underlying brain activation patterns.

Three roles share one adaptive loop: **students** read, **educators** build with AI, **researchers** inspect.

![Research workbench — class overview, student console, active drivers](docs/screenshots/research-workbench.png)

---

## Table of Contents

- [What it does](#what-it-does)
- [Screenshots](#screenshots)
- [Architecture](#architecture)
- [Tech stack](#tech-stack)
- [Quick start](#quick-start)
- [Configuration](#configuration)
- [Repo layout](#repo-layout)
- [Testing](#testing)
- [Adaptive loop in detail](#adaptive-loop-in-detail)

---

## What it does

- **Behavior tracking.** A WebSocket-backed tracker streams ten event types (`section_view`, `section_exit`, `hover_start/end`, `mouse_move`, `scroll`, `text_select`, `click`, `idle_start/end`) into Redis, then drains them into Postgres on session end.
- **Focus classification.** Sessions are scored along five states (focused / engaged / distracted / skimming / abandoned) plus a per-section focus timeseries.
- **7-axis learning profile.** Pace, depth, attention stability, engagement mode, revisit tendency, visual orientation, motor style — updated via EMA after every session, plus an engagement fingerprint and a topic-mastery graph.
- **Lesson Studio.** Educators type a topic; an LLM (Claude via OpenRouter) generates four reading variants, two quiz sets, practice problems, and pulls matching YouTube videos. Drag, reorder, publish.
- **RAG-driven personalization.** Each student's lesson is rewritten using their top-k most relevant past profile entries (pgvector cosine retrieval, fallback to deterministic embeddings).
- **Per-student Neural Microscope.** A 44-feature → 10 → 6 → 1 NumPy SGD surrogate trained on the student's own data (3× weighted) plus the cohort, exposed with full saliency, weight heatmaps, gradient heatmaps, and loss curves.
- **TRIBE v2 brain visualization.** Predicts ROI activation patterns (dlPFC, IPS, Broca, Wernicke, Hippocampus, V1, etc.) for a given student × lesson and renders them on an interactive Three.js hemisphere.
- **Continual + persistent learning** through a blend of **RAG and RL**: behavior → features → prediction → quiz outcome → profile entry → personalized future lessons.

## Screenshots

### Research Workbench
Per-class neural surrogate status, content audit, and TRIBE v2 readiness. Each student's "active drivers" panel surfaces which behavioral features are pushing the prediction up or down right now.

![Research workbench — Algebra I · Block 3](docs/screenshots/research-workbench.png)

### Neural Microscope
Personalized 44 → 10 → 6 → 1 surrogate per student. Click any node or edge to inspect activations, gradients, and weight contributions; switch the heatmap mode between learned weights, loss gradients, update pressure, and activation-weighted influence.

![Neural Microscope — personalized layers, loss, gradients, and backprop](docs/screenshots/neural-microscope.png)

---

## Architecture

```
┌─────────────────┐    WebSocket    ┌─────────────┐    drain    ┌──────────────┐
│ Student browser │ ──────────────▶ │    Redis    │ ──────────▶ │ Celery worker│
│ (BehaviorTracker)│                │ (events buf)│             │ (eager OK)   │
└─────────────────┘                 └─────────────┘             └──────┬───────┘
                                                                       │
                                          ┌────────────────────────────┼────────────────────────┐
                                          ▼                            ▼                        ▼
                                ┌──────────────────┐         ┌──────────────────┐    ┌────────────────────┐
                                │ tracking service │         │   profile + RAG   │    │  ml service +      │
                                │ (features → DB)  │         │ (embed + retrieve)│    │  research_nn (NN)  │
                                └────────┬─────────┘         └─────────┬─────────┘    └──────────┬─────────┘
                                         │                             │                         │
                                         ▼                             ▼                         ▼
                            ┌────────────────────────────────────────────────────────────────────────┐
                            │           PostgreSQL + pgvector (or SQLite fallback)                    │
                            │  users · classes · materials · sections · quiz_questions · attempts     │
                            │  tracking_sessions · tracking_events (weekly partitioned)               │
                            │  score_predictions · prediction_models · research_neural_models         │
                            │  user_learning_profiles · topic_mastery_nodes · personalized_lessons    │
                            └────────────────────────────────────────────────────────────────────────┘
                                                              ▲
                                                              │
                                                    REST + OpenAPI
                                                              │
                                                              ▼
                                                ┌─────────────────────┐
                                                │ Next.js 14 frontend │
                                                │ (App Router · TS)    │
                                                └─────────────────────┘
```

---

## Tech stack

**Languages** — Python 3.12, TypeScript, SQL, Bash

**Frameworks / libraries**
- Backend: FastAPI, SQLAlchemy 2 async, Alembic, Pydantic, Celery, Passlib + bcrypt, python-jose, NumPy, Pandas, scikit-learn, XGBoost, OpenAI Python SDK, pgvector, httpx, tiktoken
- Frontend: Next.js 14 (App Router), React 18, Three.js, Recharts, React Markdown + remark-gfm, Zustand, TanStack React Query, Tailwind CSS
- Tests: pytest + pytest-asyncio, Vitest + React Testing Library + jsdom, Playwright

**Platforms** — Docker / Docker Compose, uv, npm, Uvicorn

**Databases** — PostgreSQL 16 + pgvector, SQLite (verification fallback), Redis 7

**APIs / external services** — Anthropic Claude (via OpenRouter), OpenRouter, OpenAI text-embedding-3-small, YouTube Data API v3, TRIBE v2 (fMRI brain activation prediction)

**Protocols** — WebSockets, JWT (HS256), OAuth2 Bearer, REST + OpenAPI, CORS

---

## Quick start

### One-shot run

```bash
chmod +x scripts/run.sh
./scripts/run.sh
```

`run.sh` brings up Postgres + Redis via Docker (or falls back to SQLite + a local `redis-server` if Docker is down), applies migrations, starts the FastAPI backend on `:8000`, starts the Next.js frontend on `:3000`, and tears everything down on Ctrl+C.

Open [http://127.0.0.1:3000](http://127.0.0.1:3000).

### Verify the full pipeline

```bash
chmod +x scripts/verify.sh
./scripts/verify.sh
```

The harness boots Postgres + Redis (or SQLite + local Redis), runs the full pytest suite, generates the PostgreSQL migration SQL and asserts pgvector + tracking partition presence, then typechecks and builds the Next.js frontend.

### Manual

```bash
# infra
docker compose up -d postgres redis

# backend  (terminal 1)
cd backend
uv sync --group dev
uv run alembic upgrade head
PYTHONPATH="$(pwd)" uv run uvicorn app.main:app --host 127.0.0.1 --port 8000

# frontend (terminal 2)
cd frontend
npm install
NEXT_PUBLIC_API_URL="http://127.0.0.1:8000" npm run dev -- --hostname 127.0.0.1 --port 3000
```

---

## Configuration

All backend settings use the `EDUTRACK_` prefix. Set these in the shell or a `backend/.env` file. See `GUIDE.md` for the full reference.

| Variable | Default | Notes |
|---|---|---|
| `EDUTRACK_DATABASE_URL` | `postgresql+asyncpg://edutrack:edutrack@localhost:54328/edutrack` | Use `sqlite+aiosqlite:///...` for the offline fallback |
| `EDUTRACK_REDIS_URL` | `redis://localhost:6389/0` | WebSocket buffer + Celery broker/backend |
| `EDUTRACK_JWT_SECRET` | `dev-edutrack-change-me` | **Override in any non-local env** |
| `EDUTRACK_CELERY_TASK_ALWAYS_EAGER` | `False` | Set to `1` for in-process task execution (used by tests + verify) |
| `EDUTRACK_LLM_PROVIDER` | `auto` | `auto` / `openrouter` / `deterministic` |
| `EDUTRACK_OPENROUTER_API_KEY` | unset | Required when provider resolves to `openrouter` |
| `EDUTRACK_LLM_MODEL` | `anthropic/claude-opus-4-7` | Any OpenRouter-compatible model ID |
| `EDUTRACK_EMBEDDING_MODEL` | `openai/text-embedding-3-small` | 1536-dim |
| `EDUTRACK_XGBOOST_MIN_SAMPLES` | `50` | Threshold before training the per-class XGBoost model |
| `NEXT_PUBLIC_API_URL` | `http://localhost:8000` | Frontend → backend base URL |

---

## Repo layout

```
brain/
├── README.md                      ← you are here
├── GUIDE.md                       ← full env-var + ops reference
├── TESTING.md                     ← test suite layout + run commands
├── docker-compose.yml             ← Postgres (pgvector) + Redis
├── docs/
│   └── screenshots/               ← in-app captures used in this README
├── scripts/
│   ├── run.sh                     ← bring everything up locally
│   └── verify.sh                  ← full CI-style verification
├── backend/
│   ├── app/
│   │   ├── api/                   ← auth, classes, materials, quizzes,
│   │   │                            tracking, profiles, lessons,
│   │   │                            lesson_studio, research
│   │   ├── services/              ← tracking, ml, profile, rag,
│   │   │                            asset_generation, asset_scoring,
│   │   │                            focus, learning_profile,
│   │   │                            lesson_studio, llm,
│   │   │                            profile_reasoning, research_nn,
│   │   │                            topics, tribe, youtube
│   │   ├── workers/tasks.py       ← Celery task wrappers
│   │   ├── models/, schemas/      ← SQLAlchemy + Pydantic
│   │   └── settings.py, db.py, redis.py, celery_app.py, security.py
│   ├── alembic/                   ← migrations (incl. pgvector + partitions)
│   └── tests/                     ← unit / api / integration / workers
└── frontend/
    ├── app/                       ← Next.js 14 App Router pages
    │   ├── (auth)/login, register
    │   ├── dashboard
    │   ├── classes/[id]/...
    │   ├── educator/...
    │   ├── researcher/students/[id]/profile
    │   ├── research/classes/[id]/workbench
    │   └── students/[id]
    ├── components/
    │   ├── BehaviorTracker/       ← WebSocket session + IntersectionObserver
    │   ├── BrainModel/            ← Three.js hemisphere with 9 ROIs
    │   ├── LessonStudio/          ← TopicInput, AssetPalette, PlanCanvas, ...
    │   ├── LearningProfileView/   ← StyleRadar, FocusTimeline, TopicGraph
    │   ├── LessonViewer/, QuizEngine/, StudentProfileCard/
    │   └── ResearchWorkbench/     ← CohortOverview, NeuralMicroscope,
    │                                PersonalizationAuditPanel,
    │                                StudentSignalPanel, TribeNeuroView
    ├── lib/api.ts, lib/tracker.ts
    └── e2e/                       ← Playwright scenarios
```

---

## Testing

Backend:

```bash
cd backend
uv run pytest -q                    # everything
uv run pytest tests/unit -q         # pure functions
uv run pytest tests/api -q          # FastAPI routes (TestClient)
uv run pytest tests/integration -q  # services against the live DB
uv run pytest tests/workers -q      # eager-mode Celery tasks
```

Frontend:

```bash
cd frontend
npm test                            # Vitest one-shot
npm run test:watch
npx playwright install              # once
npm run test:e2e                    # Playwright E2E
```

See `TESTING.md` for the full layout and what each file covers.

---

## Adaptive loop in detail

Every reading session walks the same six-stage pipeline, and every stage writes evidence to the database for later inspection:

1. **Read** — Lesson page mounts `BehaviorTrackerMount`, which calls `POST /sessions/start` and opens a WebSocket to `/track/{session_id}`. Browser events stream in real time.
2. **Buffer + drain** — Events sit in `Redis :: tracking:{session_id}` until the student finishes reading. `POST /sessions/{id}/end` queues `tracking.extract_features_and_predict`, which drains Redis, persists raw events into the partitioned `tracking_events` table, and computes the per-session feature payload.
3. **Predict** — `ml.predict_for_session` chooses the latest class XGBoost model (or the global one, or the heuristic baseline) and writes a `score_predictions` row.
4. **Score** — Student takes the quiz; `POST /quiz/{id}/submit` scores it, fills `score_predictions.actual_score`, and queues `profile.add_student_profile_entry`.
5. **Profile** — The profile task generates a JSON profile entry (LLM or deterministic), embeds it into pgvector, then **retroactively personalizes** every published lesson the student is enrolled in.
6. **Personalize** — On the next `GET /materials/{id}`, the student receives a markdown variant generated from their retrieved profile entries plus the base lesson — RAG conditioning the next lesson on everything we've learned about them so far.

In parallel, the **research workbench** trains a per-student NumPy neural surrogate, runs the TRIBE v2 brain-activation predictor, and exposes the entire mechanism — saliency, gradients, weight heatmaps, loss curves, ROI activations, connectivity edges — to researchers.

---

## License & status

Built for hackathon / research demonstration. Demo paths run with deterministic LLM + simulated TRIBE so the full experience is reproducible without external API keys; switch `EDUTRACK_LLM_PROVIDER=openrouter` and provide a TRIBE endpoint to enable the live versions.
