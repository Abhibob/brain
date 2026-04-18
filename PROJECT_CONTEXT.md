# EduTrack Project Context

Generated from the current repository on 2026-04-18.

This document is meant to give a frontend UI editor enough project context to safely redesign or extend the UI without breaking the backend contracts. It describes what the app does, how the backend works, what data exists, what each screen uses, and where the important code lives.

## 1. Product Summary

EduTrack is a full-stack adaptive learning platform.

The core product idea is:

1. Educators create classes, lessons, and quizzes.
2. Students enroll in classes, read lessons, and take quizzes.
3. While students read lessons, the browser captures behavior signals such as section views, scrolls, hovers, mouse movement, idle time, text selection, and clicks.
4. The backend turns those behavioral events into session-level learning features.
5. The system predicts quiz performance from those features.
6. After quiz submission, the backend generates append-only student learning profile entries.
7. Published lessons can be personalized per student using the student's profile entries and lesson content.
8. Researchers can inspect profiles, prediction quality, model status, drift, and engagement analytics.

The app is currently named `EduTrack`.

## 2. Tech Stack

### Frontend

- Next.js 14 App Router
- React 18
- TypeScript
- CSS in `frontend/app/globals.css`
- Recharts for research charts
- React Markdown for personalized lesson markdown rendering
- Browser `localStorage` for auth token persistence

### Backend

- FastAPI
- SQLAlchemy async ORM
- Alembic migrations
- PostgreSQL with pgvector for production/local Docker
- SQLite fallback for verification
- Redis for WebSocket event buffering and Celery broker/result backend
- Celery for background work
- OpenRouter through the OpenAI-compatible SDK for LLM and embedding calls
- Deterministic local fallback for LLM/profile/personalization/embedding behavior
- XGBoost for trained score prediction after enough labeled data exists

### Local Infrastructure

- `docker-compose.yml` starts:
  - PostgreSQL/pgvector on host port `54328`
  - Redis on host port `6389`

## 3. User Roles

The actual code supports three roles:

- `student`
- `educator`
- `researcher`

### Student

Students can:

- Register and log in.
- View classes they are enrolled in.
- Enroll in a class using a class ID plus enrollment code.
- Open lesson materials.
- Generate tracked reading sessions while viewing lessons.
- Finish reading, which ends a tracking session and triggers feature extraction/prediction.
- Take quizzes.
- Receive personalized lessons if a personalized version exists.

### Educator

Educators can:

- Register and log in.
- Create classes.
- View their own classes.
- See class enrollment codes.
- Create lessons and basic quizzes.
- Edit and delete materials.
- Publish materials, which triggers background personalization for enrolled students.
- View class rosters.

Educators currently cannot access generated student profile details or researcher analytics in the implemented backend.

### Researcher

Researchers can:

- Register and log in.
- View all classes.
- View rosters with profile entry counts.
- View student profile entries.
- View class analytics, prediction summaries, model details, drift status, material engagement, and section heatmaps.
- Manually queue personalization for a material/student.
- Fetch session predictions.

The researcher role is important in the actual implementation and should be preserved in UI work unless the backend is intentionally changed.

## 4. End-to-End Product Flows

### 4.1 Auth Flow

1. User registers at `/register`.
2. Frontend calls `POST /auth/register`.
3. Backend creates a `users` row.
4. If the role is `educator`, backend also creates an `educator_profiles` row.
5. Backend returns an access token, refresh token, and user object.
6. Frontend stores the auth response in `localStorage` key `edutrack.auth`.
7. Authenticated API calls send `Authorization: Bearer <access_token>`.

Login uses `POST /auth/login`.

Refresh uses `POST /auth/refresh`.

### 4.2 Class and Enrollment Flow

1. Educator creates a class.
2. Backend generates an 8-character enrollment code.
3. Student enrolls by submitting both:
   - class ID
   - enrollment code
4. Backend creates an `enrollments` row if the pair is valid.

Current UI note: students need to know the numeric class ID and enrollment code. There is no class-code-only join flow yet.

### 4.3 Lesson Creation and Publishing Flow

1. Educator creates a lesson material inside a class.
2. Lesson content is stored as one or more `material_sections`.
3. Educator creates quiz questions for the material.
4. Educator publishes the material.
5. Backend sets `materials.published_at`.
6. Backend queues:
   - one task to embed material sections
   - one personalization task per enrolled student
7. If a student has no profile entries yet, personalization returns `None` and the base lesson is served.
8. After that student generates a profile entry later, the backend retroactively personalizes all already-published lessons for that student.

### 4.4 Student Reading and Tracking Flow

1. Student opens a lesson page.
2. `BehaviorTrackerMount` calls `POST /sessions/start`.
3. Backend creates a `tracking_sessions` row and returns `session_id`.
4. Frontend opens a WebSocket at `/track/{session_id}?token=<access_token>`.
5. Browser behavior events are sent over the WebSocket.
6. Backend buffers events into Redis list key `tracking:{session_id}`.
7. Student clicks "Finish reading" or leaves the page.
8. Frontend calls `POST /sessions/{session_id}/end`.
9. Backend marks `ended_at` and queues `tracking.extract_features_and_predict`.
10. Celery drains Redis, writes `tracking_events`, computes features, stores them on `tracking_sessions.features`, and creates/updates a `score_predictions` row.

### 4.5 Quiz and Profile Flow

1. Student opens quiz page.
2. Frontend calls `GET /materials/{material_id}/quiz`.
3. Student submits answers to `POST /quiz/{material_id}/submit`.
4. Backend scores the quiz.
5. Backend creates a `quiz_attempts` row.
6. If `session_id` is provided, backend backfills `score_predictions.actual_score`.
7. Backend queues:
   - `profile.add_student_profile_entry`
   - `ml.train_model_for_class`
   - `ml.train_global_model`
8. Profile task builds a profile entry from lesson content, behavioral features, quiz score, and predicted score.
9. The profile entry is embedded and saved to `student_profile_entries`.
10. The same task retroactively personalizes published lessons for that student.

Current UI note: the backend supports `session_id` on quiz submit, and tests use it. The current browser quiz UI does not pass the reading `session_id` into `QuizEngine`, so predicted-vs-actual linking may be missing in normal UI usage unless the UI is updated to carry the session ID from lesson to quiz.

### 4.6 Personalized Lesson Serving Flow

1. Student requests `GET /materials/{material_id}`.
2. Backend checks whether the user is enrolled in the material's class.
3. If the requester is a student, backend looks for a matching `personalized_lessons` row.
4. If found:
   - `personalized` is `true`
   - `generated_content` contains personalized markdown
   - frontend renders that markdown as a single lesson section
5. If not found:
   - `personalized` is `false`
   - `generated_content` is `null`
   - frontend renders the base material sections

### 4.7 Research Analytics Flow

1. Researcher opens a class page.
2. Frontend calls `GET /classes/{class_id}/analytics`.
3. Backend computes:
   - latest class model metadata
   - drift status
   - per-student prediction/actual averages
   - material engagement averages
   - section heatmap values
4. Frontend renders predicted vs actual chart, model details, drift status, top feature importances, and heatmap cards.

## 5. Backend Architecture

Backend root: `backend/`

### Important Backend Files

```text
backend/app/main.py                 FastAPI app, CORS, router registration, health endpoint
backend/app/settings.py             EDUTRACK_* settings and provider selection
backend/app/db.py                   Async SQLAlchemy engine/session
backend/app/security.py             Password hashing and JWT creation/validation
backend/app/redis.py                Redis connection helper
backend/app/celery_app.py           Celery app configuration
backend/app/models/__init__.py      SQLAlchemy models
backend/app/schemas/__init__.py     Pydantic request/response schemas
backend/app/api/auth.py             Register/login/refresh
backend/app/api/classes.py          Class CRUD, enrollment, rosters, analytics
backend/app/api/materials.py        Material CRUD, publishing, quiz question CRUD, personalized serving
backend/app/api/quizzes.py          Quiz submission and scoring
backend/app/api/tracking.py         Tracking sessions and WebSocket event ingestion
backend/app/api/profiles.py         Researcher profile read endpoint
backend/app/api/lessons.py          Researcher manual personalization endpoint
backend/app/services/tracking.py    Redis draining, event persistence, feature extraction
backend/app/services/ml.py          Heuristic scoring, XGBoost training, drift status
backend/app/services/profile.py     Student profile entry generation
backend/app/services/rag.py         Embeddings, profile retrieval, lesson personalization
backend/app/workers/tasks.py        Celery task wrappers
backend/alembic/versions/0001_initial.py PostgreSQL schema migration
backend/tests/test_full_workflow.py Full backend workflow verification
```

### FastAPI Routers

`backend/app/main.py` registers these routers:

- `auth.router`
- `classes.router`
- `materials.router`
- `quizzes.router`
- `tracking.router`
- `profiles.router`
- `lessons.router`

The app also exposes:

- `GET /health` -> `{ "status": "ok" }`

### API Endpoint Summary

| Endpoint | Method | Main role(s) | Purpose |
|---|---:|---|---|
| `/auth/register` | POST | public | Create user, return tokens |
| `/auth/login` | POST | public | Authenticate, return tokens |
| `/auth/refresh` | POST | public with refresh token | Return new token pair |
| `/classes` | GET | student, educator, researcher | List visible classes |
| `/classes` | POST | educator | Create class |
| `/classes/{class_id}` | GET | enrolled student, owning educator, researcher | Get class plus materials |
| `/classes/{class_id}/enroll` | POST | student | Enroll using class ID and code |
| `/classes/{class_id}/students` | GET | educator, researcher | Class roster; researcher gets profile counts |
| `/classes/{class_id}/analytics` | GET | researcher | Prediction/model/engagement analytics |
| `/classes/{class_id}/materials` | POST | educator | Create material and sections |
| `/materials/{material_id}` | GET | enrolled student, owning educator, researcher | Get material; student may receive personalized content |
| `/materials/{material_id}` | PUT | educator | Update material; clears/regenerates personalization when sections change |
| `/materials/{material_id}` | DELETE | educator | Delete material |
| `/materials/{material_id}/publish` | PUT | educator | Publish material and queue personalization |
| `/materials/{material_id}/quiz` | POST | educator | Add quiz questions |
| `/materials/{material_id}/quiz` | GET | enrolled student, owning educator, researcher | Get public quiz questions |
| `/quiz/{material_id}/submit` | POST | student | Submit answers, score quiz, queue profile/training |
| `/sessions/start` | POST | student | Create reading tracking session |
| `/sessions/{session_id}/end` | POST | student | End session and queue feature extraction/prediction |
| `/sessions/{session_id}/prediction` | GET | researcher | Read prediction for session |
| `/track/{session_id}` | WebSocket | student with access token | Stream behavior events |
| `/students/{student_id}/profile` | GET | researcher | Read generated profile entries |
| `/lessons/{material_id}/personalize/{student_id}` | POST | researcher | Queue manual personalization |

### Auth and Authorization Details

- Passwords are hashed with passlib/bcrypt.
- JWTs are signed with `EDUTRACK_JWT_SECRET`.
- Access and refresh tokens include:
  - `sub`: user ID string
  - `type`: `access` or `refresh`
  - `exp`: expiration
- Most endpoints use `get_current_user`.
- Role-only endpoints use `require_role(role)`.
- WebSockets pass the access token as a query parameter because browser WebSocket connections cannot set arbitrary Authorization headers consistently.

### Database Models

All models are in `backend/app/models/__init__.py`.

#### `users`

Stores auth identity.

Important columns:

- `id`
- `email`
- `hashed_password`
- `role`: `student`, `educator`, or `researcher`
- `created_at`

#### `educator_profiles`

Optional educator metadata.

Important columns:

- `user_id`
- `bio`
- `institution`

#### `classes`

Class/course containers owned by educators.

Important columns:

- `educator_id`
- `title`
- `description`
- `enrollment_code`
- `created_at`

#### `enrollments`

Joins students to classes.

Important columns:

- `class_id`
- `student_id`
- unique constraint on `(class_id, student_id)`

#### `materials`

Lesson or quiz containers inside a class.

Important columns:

- `class_id`
- `title`
- `type`: `lesson` or `quiz`
- `order_index`
- `published_at`

#### `material_sections`

Ordered lesson sections.

Important columns:

- `material_id`
- `title`
- `content`
- `order_index`
- `word_count`
- `embedding`: pgvector `Vector(1536)` in PostgreSQL, JSON fallback in SQLite

#### `quiz_questions`

Quiz questions attached to a material.

Important columns:

- `material_id`
- `question`
- `options`
- `correct_answer`
- `points`

The public quiz endpoint does not return `correct_answer`.

#### `tracking_sessions`

One reading session for one student and one material.

Important columns:

- `student_id`
- `material_id`
- `started_at`
- `ended_at`
- `features`: computed JSON feature payload

#### `tracking_events`

Raw high-volume event table.

Important columns:

- `session_id`
- `event_type`
- `event_data`
- `client_ts`
- `server_ts`

PostgreSQL migration creates this table partitioned by `server_ts`, with a default partition and weekly partition creation at runtime.

#### `quiz_attempts`

Student quiz attempts.

Important columns:

- `student_id`
- `material_id`
- `session_id`
- `answers`
- `score`
- `max_score`
- `submitted_at`

#### `score_predictions`

Predicted quiz score for a reading session.

Important columns:

- `session_id`
- `predicted_score`
- `confidence`
- `model_version`
- `actual_score`
- `created_at`

#### `prediction_models`

Stores XGBoost model artifacts and metadata.

Important columns:

- `class_id`: nullable; null means global model
- `version`
- `model_type`
- `feature_importances`
- `rmse`
- `sample_count`
- `artifact`: pickled model
- `trained_at`

#### `student_profile_entries`

Append-only generated learning profile observations.

Important columns:

- `user_id`
- `profile_text`
- `profile_json`
- `embedding`: pgvector `Vector(1536)` in PostgreSQL, JSON fallback in SQLite
- `trigger_material_id`
- `quiz_attempt_id`
- `quiz_score`
- `created_at`

There is no single merged student profile. RAG retrieves relevant past entries when personalizing a lesson.

#### `personalized_lessons`

Per-student generated lesson variants.

Important columns:

- `educator_id`
- `student_id`
- `base_material_id`
- `prompt_used`
- `generated_content`
- `created_at`
- `assigned_at`

Unique constraint:

- `(student_id, base_material_id)`

### Tracking Service

File: `backend/app/services/tracking.py`

The tracking service:

- Receives WebSocket events through `ingest_event`.
- Pushes raw JSON payloads into Redis list `tracking:{session_id}`.
- On session end, drains the Redis list.
- Persists drained events into `tracking_events`.
- Reads all persisted events for the session.
- Computes a session feature JSON.
- Saves features to `tracking_sessions.features`.

Computed features include:

- `total_time_s`
- `time_per_section`
- `hover_count`
- `avg_hover_duration_ms`
- `hover_per_section`
- `scroll_depth_pct`
- `back_scroll_count`
- `scroll_velocity_avg`
- `mouse_velocity_avg`
- `mouse_velocity_variance`
- `idle_total_s`
- `idle_count`
- `text_selection_count`
- `re_read_sections`
- `reading_speed_wpm`
- `section_completion_rate`

### ML Service

File: `backend/app/services/ml.py`

There are two prediction modes:

1. Heuristic prediction
2. XGBoost prediction

#### Heuristic prediction

Used when no trained model artifact exists.

Starts at baseline `0.5` and adjusts based on:

- Normal reading speed
- Section completion rate
- Hover count
- Idle ratio
- Back-scroll count

Outputs:

- `predicted_score`
- `confidence` fixed around `0.45`
- `model_version = "heuristic-v1"`

#### XGBoost prediction

Training starts only when there are at least `EDUTRACK_XGBOOST_MIN_SAMPLES` labeled sessions. Default is `50`.

Training data comes from sessions that have:

- computed `tracking_sessions.features`
- joined `quiz_attempts`
- nonzero `max_score`

Targets are normalized quiz scores:

```text
quiz_attempt.score / quiz_attempt.max_score
```

Trained models are saved in `prediction_models` as pickled artifacts with feature importances and RMSE.

Prediction uses the latest class-specific model first, then falls back to the latest global model, then falls back to the heuristic scorer.

### Profile Service

File: `backend/app/services/profile.py`

After each quiz submission, a background task generates a profile entry.

Input context:

- Material title and section summaries
- Tracking session features
- Quiz score
- Previous predicted score, if there was a linked tracking session

Output JSON fields:

- `topic`
- `observed_score`
- `predicted_score`
- `strengths_observed`
- `struggles_observed`
- `engagement_notes`
- `behavioral_summary`
- `recommendation`

Provider behavior:

- If `EDUTRACK_LLM_PROVIDER=openrouter`, the backend calls OpenRouter using `EDUTRACK_LLM_MODEL`.
- If `deterministic`, or `auto` without an API key, it generates a deterministic local profile entry.

The profile text is embedded immediately using `embed_text` from the RAG service.

### RAG and Personalization Service

File: `backend/app/services/rag.py`

Responsibilities:

- Create deterministic or OpenRouter embeddings.
- Embed material sections.
- Retrieve relevant student profile entries for a lesson query.
- Build a personalization prompt.
- Generate personalized lesson markdown.
- Upsert `personalized_lessons`.
- Retroactively personalize published lessons after a student's first or later profile entries.

Retrieval behavior:

- PostgreSQL uses pgvector cosine distance through `<=>`.
- SQLite fallback computes cosine distance in Python.
- Default retrieval count is top 8 profile entries.

Cold start behavior:

- If a student has no profile entries, no personalized lesson is created.
- The student receives the base lesson.
- Once a profile entry exists, retroactive personalization can create generated lessons for already-published materials.

### Celery Tasks

File: `backend/app/workers/tasks.py`

Tasks:

- `tracking.extract_features_and_predict(session_id)`
  - drains Redis events
  - persists tracking events
  - computes features
  - creates/updates score prediction
- `profile.add_student_profile_entry(student_id, quiz_attempt_id)`
  - generates profile entry
  - retroactively personalizes lessons
- `rag.embed_material_sections(material_id)`
  - embeds all sections for a material
- `rag.personalize_lesson_for_student(student_id, material_id)`
  - creates or updates one personalized lesson
- `ml.train_model_for_class(class_id)`
  - trains class-specific XGBoost model if sample count is high enough
- `ml.train_global_model()`
  - trains global XGBoost model if sample count is high enough

Celery can run eagerly in the API process by setting:

```bash
EDUTRACK_CELERY_TASK_ALWAYS_EAGER=1
```

## 6. Frontend Architecture

Frontend root: `frontend/`

### Important Frontend Files

```text
frontend/app/layout.tsx                                  Root layout and metadata
frontend/app/globals.css                                 Global styling and design tokens
frontend/app/page.tsx                                    Redirects to dashboard or login
frontend/app/(auth)/login/page.tsx                       Login screen
frontend/app/(auth)/register/page.tsx                    Registration screen
frontend/app/dashboard/page.tsx                          Role-aware dashboard
frontend/app/classes/[id]/page.tsx                       Class page, materials, roster, analytics
frontend/app/classes/[id]/materials/[mid]/page.tsx       Lesson page
frontend/app/classes/[id]/materials/[mid]/quiz/page.tsx  Quiz page
frontend/app/educator/classes/new/page.tsx               Create class screen
frontend/app/educator/materials/[id]/edit/page.tsx       Lesson editor
frontend/app/researcher/students/[id]/profile/page.tsx   Researcher profile entry screen
frontend/components/LessonViewer/LessonViewer.tsx        Lesson rendering and session controls
frontend/components/BehaviorTracker/BehaviorTrackerMount.tsx Starts/stops tracking
frontend/components/QuizEngine/QuizEngine.tsx            Quiz renderer and submitter
frontend/components/StudentProfileCard/StudentProfileCard.tsx Profile entry display
frontend/lib/api.ts                                      Typed API wrapper and auth storage
frontend/lib/tracker.ts                                  Browser behavior tracker and WebSocket client
```

### Current Frontend Routing

| Route | Purpose | Main API calls |
|---|---|---|
| `/` | Redirects based on auth state | localStorage only |
| `/login` | Sign in | `POST /auth/login` |
| `/register` | Create account | `POST /auth/register` |
| `/dashboard` | Role-aware class dashboard | `GET /classes`, student `POST /classes/{id}/enroll` |
| `/educator/classes/new` | Educator creates class | `POST /classes` |
| `/classes/[id]` | Class overview | `GET /classes/{id}`, roster, analytics for researcher |
| `/classes/[id]/materials/[mid]` | Lesson viewer | `GET /materials/{mid}`, tracking session APIs |
| `/classes/[id]/materials/[mid]/quiz` | Quiz UI | `GET /materials/{mid}/quiz`, `POST /quiz/{mid}/submit` |
| `/educator/materials/[id]/edit` | Lesson editor | `GET /materials/{id}`, `PUT /materials/{id}` |
| `/researcher/students/[id]/profile` | Researcher profile entries | `GET /students/{id}/profile` |

### Frontend Auth Model

`frontend/lib/api.ts` defines:

- `API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"`
- `AUTH_KEY = "edutrack.auth"`
- `getStoredAuth()`
- `storeAuth(auth)`
- `clearAuth()`

Auth is read directly from browser localStorage. There is no React auth provider currently.

Every API request:

- sets `Content-Type: application/json`
- includes `Authorization: Bearer <access_token>` when present
- throws an `Error` with backend `detail` when the response is not OK

### Frontend Data Types

Core frontend types are in `frontend/lib/api.ts`:

- `User`
- `AuthState`
- `ClassOut`
- `MaterialSummary`
- `MaterialOut`
- `SectionOut`
- `ClassAnalytics`
- `QuizQuestion`
- `ProfileEntry`

These are the main types a UI editor should preserve or update if API contracts change.

### Lesson Viewer

File: `frontend/components/LessonViewer/LessonViewer.tsx`

Responsibilities:

- Mount the behavior tracker.
- Render session status.
- Render "Finish reading".
- Link to quiz.
- Render personalized markdown when `material.generated_content` exists.
- Otherwise render base material sections.

For base sections, each section has:

```tsx
data-section-id={section.id}
```

For personalized generated markdown, the single rendered section has:

```tsx
data-section-id={`personalized-${material.id}`}
```

The tracker relies on `[data-section-id]` elements for section view and exit events.

### Behavior Tracker

Files:

- `frontend/components/BehaviorTracker/BehaviorTrackerMount.tsx`
- `frontend/lib/tracker.ts`

The tracker starts only for authenticated students.

Captured events:

- `section_view`
- `section_exit`
- `hover_start`
- `hover_end`
- `mouse_move`
- `scroll`
- `text_select`
- `click`
- `idle_start`
- `idle_end`

Tracking implementation details:

- WebSocket URL is derived by replacing `http` with `ws` in `NEXT_PUBLIC_API_URL`.
- Mouse movement is sampled every 500 ms.
- Idle starts after 30 seconds.
- Section visibility is measured with `IntersectionObserver` at threshold `0.45`.
- Section and hover exits are flushed when tracking stops.

### Quiz Engine

File: `frontend/components/QuizEngine/QuizEngine.tsx`

Responsibilities:

- Fetch public quiz questions.
- Render radio options.
- Submit answer map.
- Display score.

Current limitation:

- It accepts only `materialId`.
- It does not accept or submit a `session_id`.
- To fully link browser tracking predictions with actual quiz scores, update this component or route flow to preserve the session ID from the lesson page and include it in `api.submitQuiz(materialId, answers, session_id)`.

### Research UI

Researcher features are rendered mostly in:

- `frontend/app/classes/[id]/page.tsx`
- `frontend/app/researcher/students/[id]/profile/page.tsx`

Research UI includes:

- predicted vs actual bar chart
- active model metadata
- drift status
- top feature importances
- section heatmap cards
- profile entry cards

## 7. Existing UI Style Context

Global CSS is in `frontend/app/globals.css`.

Current visual system:

- White background
- Soft green accent
- Gray-green borders
- Simple cards
- Sticky topbar
- Constrained content width
- Responsive grid layout
- Plain Arial/Helvetica stack

CSS variables:

```css
--background: #ffffff;
--foreground: #151515;
--muted: #f4f6f5;
--line: #d8dfdc;
--accent: #0f7b66;
--accent-strong: #095947;
--danger: #b3261e;
--ink-soft: #4b5560;
```

Reusable classes:

- `.shell`
- `.topbar`
- `.brand`
- `.nav`
- `.main`
- `.band`
- `.banner-image`
- `.stack`
- `.grid`
- `.card`
- `.field`
- `.input`
- `.textarea`
- `.select`
- `.button`
- `.button.secondary`
- `.button.danger`
- `.muted`
- `.error`
- `.lesson`
- `.lesson-section`
- `.markdown`
- `.toolbar`
- `.chart-card`

If a UI editor changes markup, it should preserve:

- authenticated role flows
- `data-section-id` on readable lesson sections
- ability to call the same API endpoints
- ability to show personalized markdown
- ability to carry a tracking session into quiz submission if improving prediction/actual linking

## 8. Current Project Structure

```text
.
|-- README.md
|-- GUIDE.md
|-- PROJECT_CONTEXT.md
|-- docker-compose.yml
|-- scripts/
|   `-- verify.sh
|-- plans/
|   `-- FIRST_PLAN.md
|-- backend/
|   |-- pyproject.toml
|   |-- uv.lock
|   |-- alembic.ini
|   |-- alembic/
|   |   |-- env.py
|   |   `-- versions/
|   |       `-- 0001_initial.py
|   |-- scripts/
|   |   `-- create_schema.py
|   |-- tests/
|   |   `-- test_full_workflow.py
|   `-- app/
|       |-- main.py
|       |-- settings.py
|       |-- db.py
|       |-- redis.py
|       |-- security.py
|       |-- celery_app.py
|       |-- api/
|       |-- models/
|       |-- schemas/
|       |-- services/
|       `-- workers/
`-- frontend/
    |-- package.json
    |-- package-lock.json
    |-- next.config.mjs
    |-- tsconfig.json
    |-- tailwind.config.ts
    |-- postcss.config.js
    |-- next-env.d.ts
    |-- app/
    |-- components/
    `-- lib/
```

## 9. Runtime Configuration

Backend settings use `EDUTRACK_` prefix and are defined in `backend/app/settings.py`.

Important backend variables:

- `EDUTRACK_DATABASE_URL`
- `EDUTRACK_REDIS_URL`
- `EDUTRACK_API_CORS_ORIGINS`
- `EDUTRACK_JWT_SECRET`
- `EDUTRACK_JWT_ALGORITHM`
- `EDUTRACK_ACCESS_TOKEN_MINUTES`
- `EDUTRACK_REFRESH_TOKEN_DAYS`
- `EDUTRACK_CELERY_TASK_ALWAYS_EAGER`
- `EDUTRACK_LLM_PROVIDER`
- `EDUTRACK_OPENROUTER_API_KEY`
- `EDUTRACK_OPENROUTER_BASE_URL`
- `EDUTRACK_LLM_MODEL`
- `EDUTRACK_EMBEDDING_MODEL`
- `EDUTRACK_EMBEDDING_DIM`
- `EDUTRACK_XGBOOST_MIN_SAMPLES`

Frontend settings use:

- `NEXT_PUBLIC_API_URL`

Default frontend API URL:

```text
http://localhost:8000
```

Default backend database URL:

```text
postgresql+asyncpg://edutrack:edutrack@localhost:54328/edutrack
```

Default Redis URL:

```text
redis://localhost:6389/0
```

## 10. Local Development Commands

Start infrastructure:

```bash
docker compose up -d postgres redis
```

Backend setup and run:

```bash
cd backend
uv sync --group dev
uv run alembic upgrade head
PYTHONPATH="$(pwd)" uv run uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Frontend setup and run:

```bash
cd frontend
npm install
NEXT_PUBLIC_API_URL="http://127.0.0.1:8000" npm run dev -- --hostname 127.0.0.1 --port 3000
```

Run full verification:

```bash
chmod +x scripts/verify.sh
./scripts/verify.sh
```

The verification script:

- starts Docker Postgres/Redis if Docker is available
- falls back to SQLite for the database when Docker is unavailable
- runs backend tests
- checks generated PostgreSQL migration SQL for pgvector and partitioning
- installs frontend packages
- runs TypeScript typecheck
- builds the frontend

## 11. What the Backend Does in Plain English

The backend is the source of truth for:

- user identity and roles
- class ownership and enrollment
- lesson and quiz content
- raw student behavior events
- computed learning features
- predicted quiz scores
- quiz attempt scoring
- profile entries generated from learning events
- per-student personalized lesson versions
- research analytics and model metadata

It also orchestrates background intelligence:

- behavior events become features
- features become score predictions
- quiz outcomes become profile entries
- profile entries become future personalization context
- enough labeled sessions become trained XGBoost models

The backend is not just a storage API. It contains the adaptation and learning-intelligence loop.

## 12. What the Frontend Does in Plain English

The frontend is the user-facing control surface for:

- account creation and login
- class dashboards
- class joining
- educator lesson creation and publishing
- student lesson reading
- behavior tracking during reading
- quiz taking
- researcher analytics and profile inspection

The frontend currently keeps state simple:

- auth lives in localStorage
- page-level components fetch data directly
- no global query client/provider is currently wired, despite React Query being installed
- no global route guards exist outside component-level redirects/checks

## 13. Important Implementation Caveats for UI Work

These are not necessarily desired product behaviors, but they are the current implementation details.

1. Researcher role is real and backend-gated.
   - Analytics and profile entries are researcher-only.
   - Educators get rosters, but not generated profile details.

2. Quiz submission supports `session_id`, but current UI does not pass it.
   - Backend tests submit `session_id`.
   - Browser UI currently calls `api.submitQuiz(materialId, answers)` without session ID.
   - A UI improvement should preserve session ID from lesson to quiz if prediction/actual analytics matter.

3. Students currently enroll using both class ID and enrollment code.
   - A friendlier join flow would require backend changes or a new endpoint.

4. Class material listing does not filter drafts for students in the current backend.
   - `GET /classes/{class_id}` returns all materials attached to the class.
   - If the UI should hide drafts from students, either filter on the frontend or change backend behavior.

5. Personalized generated content is a single markdown blob.
   - Base content is structured sections.
   - Personalized content is rendered as one markdown section.
   - If section-level tracking on personalized content matters, the generation format or rendering strategy may need to split markdown into sections.

6. Auth is localStorage-based.
   - There is no HTTP-only cookie auth.
   - There is no automatic refresh retry in the frontend request helper.

7. Celery eager mode changes timing.
   - In local verification, tasks run synchronously.
   - In real worker mode, personalization/profile/model updates are asynchronous and UI should handle "not ready yet" states.

8. Deterministic mode is designed for local repeatability.
   - OpenRouter is optional unless `EDUTRACK_LLM_PROVIDER=openrouter`.
   - Without OpenRouter, profiles and lessons are generated by deterministic code.

## 14. Suggested UI Editor Context Prompt

Use this project as an adaptive learning app with three roles: student, educator, and researcher. The frontend is a Next.js 14 App Router app. The backend is a FastAPI API that already implements auth, classes, materials, quizzes, tracking, prediction, profile generation, and lesson personalization.

Preserve the API contracts in `frontend/lib/api.ts`. Preserve student behavior tracking by keeping `data-section-id` attributes on lesson content that should be tracked. Preserve role-specific navigation:

- students: dashboard, class enrollment, class pages, lessons, quizzes
- educators: dashboard, class creation, class pages, lesson creation/editing/publishing, roster
- researchers: dashboard, class analytics, profile entries

Important product concepts to surface cleanly:

- A lesson can be base content or personalized markdown.
- Reading a lesson starts a tracking session.
- Finishing reading ends the session and produces features/predictions.
- Quizzes produce scores and profile entries.
- Published lessons queue personalization for enrolled students.
- Research analytics may lag because background tasks are asynchronous.

Do not remove or hide core adaptive-learning concepts unless the backend is also changed.

## 15. Backend Contract Details for Frontend Editors

### `MaterialOut`

The lesson UI should expect:

```ts
{
  id: number;
  class_id: number;
  title: string;
  type: string;
  order_index: number;
  published_at: string | null;
  personalized: boolean;
  generated_content: string | null;
  sections: Array<{
    id: number;
    title: string;
    content: string;
    order_index: number;
    word_count: number;
  }>;
}
```

Rendering rule:

- If `generated_content` is present, render markdown.
- Otherwise render `sections`.

### `ClassOut`

Class pages should expect:

```ts
{
  id: number;
  educator_id: number;
  title: string;
  description: string | null;
  enrollment_code: string;
  created_at: string;
  materials?: Array<{
    id: number;
    title: string;
    type: string;
    order_index: number;
    published_at: string | null;
  }>;
}
```

### `ClassAnalytics`

Research pages should expect:

```ts
{
  class_id: number;
  model: null | {
    id: number;
    version: string;
    model_type: string;
    rmse: number;
    sample_count: number;
    trained_at: string;
    feature_importances: Record<string, number>;
  };
  drift: Record<string, unknown>;
  students: Array<{
    id: number;
    email: string;
    session_count: number;
    prediction_count: number;
    average_predicted: number | null;
    average_actual: number | null;
    latest_prediction: Record<string, unknown> | null;
  }>;
  material_engagement: Array<{
    material_id: number;
    title: string;
    session_count: number;
    average_completion_rate: number;
    average_idle_s: number;
    average_total_time_s: number;
  }>;
  section_heatmap: Array<{
    section_id: string;
    title: string;
    session_count: number;
    average_time_s: number;
    average_hovers: number;
  }>;
}
```

## 16. Mental Model for Future Changes

Think of EduTrack as three connected layers:

1. Learning content layer
   - classes
   - materials
   - sections
   - quizzes

2. Learning telemetry layer
   - sessions
   - WebSocket events
   - computed features
   - predictions
   - quiz outcomes

3. Adaptation layer
   - profile entries
   - embeddings
   - profile retrieval
   - generated personalized lessons
   - researcher analytics

A UI redesign should make these layers easier to use, but should not accidentally sever the data loop:

```text
lesson reading -> behavior events -> features -> prediction -> quiz score -> profile entry -> personalized future lessons
```
