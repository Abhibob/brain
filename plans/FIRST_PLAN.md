# EduTrack: Adaptive Learning Platform — Implementation Plan

## Context

Build a full-stack adaptive education platform where educators manage classes and materials with zero involvement in ML or personalization. Students consume lessons with real-time behavioral tracking; the system automatically trains per-student score predictors, continuously updates LLM-synthesized learning profiles, and — when a lesson is published — automatically generates a personalized version per enrolled student via RAG. Educators just create content; students see content tailored to them.

**Stack:** FastAPI (Python) + Next.js 14 (TypeScript) + PostgreSQL + pgvector + Redis + Celery + OpenRouter (configurable model)

---

## System Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Next.js Frontend                      │
│  Auth | Class Mgmt | Lesson Viewer | Educator Dashboard  │
│            WebSocket client (tracking)                   │
└────────────────────┬────────────────────────────────────┘
                     │ HTTP / WebSocket
┌────────────────────▼────────────────────────────────────┐
│                 FastAPI Backend                          │
│  Auth | Classes | Materials | Quiz | Tracking | Profiles │
│              RAG Lesson Generator                        │
└──────┬─────────────┬──────────────┬──────────────────────┘
       │             │              │
  ┌────▼────┐  ┌─────▼─────┐  ┌────▼────────┐
  │Postgres │  │   Redis   │  │   Celery    │
  │+pgvector│  │(event buf)│  │(ML train,   │
  │         │  │           │  │ profile gen)│
  └─────────┘  └───────────┘  └─────────────┘
```

---

## Database Schema

### Core Tables

```sql
-- Users
users(id, email, hashed_password, role ENUM('student','educator'), created_at)
educator_profiles(id, user_id FK, bio, institution)
-- Profile is append-only: each quiz/session adds a new entry, RAG retrieves across all
student_profile_entries(id, user_id FK, profile_text TEXT, profile_json JSONB,
                        embedding vector(1536), trigger_material_id FK,
                        quiz_score FLOAT, created_at)
-- No single "current profile" — RAG retrieves the most relevant entries at query time

-- Classes & Enrollment
classes(id, educator_id FK, title, description, enrollment_code, created_at)
enrollments(id, class_id FK, student_id FK, enrolled_at)

-- Materials & Sections
materials(id, class_id FK, title, type ENUM('lesson','quiz'), order_index, published_at)
material_sections(id, material_id FK, title, content TEXT, order_index, word_count)

-- Quizzes
quiz_questions(id, material_id FK, question TEXT, options JSONB, correct_answer, points)
quiz_attempts(id, student_id FK, material_id FK, answers JSONB, score FLOAT, 
              max_score FLOAT, started_at, submitted_at)

-- Behavioral Tracking
tracking_sessions(id, student_id FK, material_id FK, started_at, ended_at,
                  features JSONB)  -- computed after session ends
tracking_events(id, session_id FK, event_type VARCHAR, event_data JSONB, 
                client_ts BIGINT, server_ts TIMESTAMPTZ)
-- Partitioned by week; events are high-volume raw data

-- ML Predictions
score_predictions(id, session_id FK, predicted_score FLOAT, confidence FLOAT,
                  model_version VARCHAR, actual_score FLOAT, created_at)
prediction_models(id, class_id FK NULLABLE, version VARCHAR, model_type VARCHAR,
                  feature_importances JSONB, rmse FLOAT, trained_at)

-- Personalized Lessons
personalized_lessons(id, educator_id FK, student_id FK, base_material_id FK,
                     prompt_used TEXT, generated_content TEXT, created_at, assigned_at)
```

---

## Phase 1: Core Platform

### 1.1 Backend (FastAPI)

**Project structure:**
```
backend/
  app/
    api/
      auth.py          # JWT login/register
      classes.py       # CRUD classes + enrollment
      materials.py     # CRUD materials + sections
      quizzes.py       # Quiz engine
      tracking.py      # WebSocket endpoint
      profiles.py      # Student profile read
      lessons.py       # Personalized lesson generation
    models/            # SQLAlchemy ORM models
    schemas/           # Pydantic request/response schemas
    services/
      tracking.py      # Event ingestion + feature extraction
      ml.py            # Heuristic scorer + XGBoost trainer
      profile.py       # LLM profile generation (Claude API)
      rag.py           # RAG pipeline (pgvector + Claude)
    workers/
      tasks.py         # Celery tasks (train, generate profile)
    db.py              # SQLAlchemy async engine
    redis.py           # Redis client
    main.py
```

**Key endpoints:**
```
POST /auth/register           — create user (role in body)
POST /auth/login              — returns JWT access + refresh tokens
GET  /classes                 — list (educator: own; student: enrolled)
POST /classes                 — create (educator only)
POST /classes/{id}/enroll     — student enrolls by code
GET  /classes/{id}/students   — educator views roster (with profile summaries)
POST /classes/{id}/materials  — create material + sections → triggers personalization pipeline
PUT  /materials/{id}/publish  — publish → triggers personalized generation for all enrollees
GET  /materials/{id}          — fetch material (students get their personalized version if ready)
POST /materials/{id}/quiz     — create quiz questions
POST /quiz/{id}/submit        — submit answers, returns score
WS   /track/{session_id}      — behavioral event stream
POST /sessions/start          — create tracking session, return session_id
POST /sessions/{id}/end       — close session, trigger feature extraction + prediction + profile update
GET  /students/{id}/profile   — educator reads auto-generated profile (read-only)
```

### 1.2 Frontend (Next.js 14 App Router)

```
frontend/
  app/
    (auth)/login, register
    dashboard/               — role-aware landing
    classes/[id]/
      page.tsx               — class overview
      materials/[mid]/
        page.tsx             — lesson viewer (tracking enabled, loads personalized content transparently)
        quiz/page.tsx        — quiz taking
    educator/
      classes/new
      materials/[id]/edit    — create/edit lesson content only
      students/[id]/profile  — read-only auto-generated profile view (educator insight)
  components/
    LessonViewer/            — renders sections + injects tracking hooks
    BehaviorTracker/         — WebSocket manager, event listeners
    QuizEngine/
    StudentProfileCard/      — read-only display for educators
  lib/
    api.ts                   — typed fetch wrappers
    tracker.ts               — event capture logic
```

---

## Phase 2: Behavioral Tracking

### Event Types Captured
| Event | Data Captured |
|---|---|
| `section_view` | section_id, timestamp |
| `section_exit` | section_id, time_spent_ms |
| `hover_start/end` | element_id, x, y, duration |
| `mouse_move` | sampled x, y, velocity (every 500ms) |
| `scroll` | direction, position, velocity |
| `text_select` | section_id, char_count |
| `click` | element_type, x, y |
| `idle_start/end` | duration |

### WebSocket Protocol
```
Client → Server:  { type: "event", data: {...}, ts: epoch_ms }
Client → Server:  { type: "heartbeat" }
Server → Client:  { type: "ack" } | { type: "error" }
```

Events buffered in Redis (`tracking:{session_id}`) during session. On `sessions/{id}/end`, a Celery task drains Redis, bulk-inserts to `tracking_events`, then computes features.

### Feature Extraction (`services/tracking.py`)
Computed per session and stored in `tracking_sessions.features JSONB`:
- `total_time_s`, `time_per_section` (dict)
- `hover_count`, `avg_hover_duration_ms`, `hover_per_section`
- `scroll_depth_pct`, `back_scroll_count`, `scroll_velocity_avg`
- `mouse_velocity_avg`, `mouse_velocity_variance`
- `idle_total_s`, `idle_count`
- `text_selection_count`, `re_read_sections` (sections revisited)
- `reading_speed_wpm` (word_count / time_on_section)
- `section_completion_rate`

---

## Phase 3: ML Prediction Pipeline

### Stage 1 — Heuristic Scorer (ships with Phase 1, no training data needed)
```python
def heuristic_score(features: dict) -> float:
    score = 0.5  # baseline
    # Positive signals
    if features['reading_speed_wpm'] in NORMAL_RANGE: score += 0.1
    if features['section_completion_rate'] > 0.8: score += 0.15
    if features['hover_count'] > HOVER_THRESHOLD: score += 0.1  # engagement
    # Negative signals  
    if features['idle_total_s'] / features['total_time_s'] > 0.4: score -= 0.2
    if features['back_scroll_count'] > HIGH_CONFUSION_THRESHOLD: score -= 0.1
    return clamp(score, 0, 1)
```

### Stage 2 — XGBoost Model (activates after 50 labeled sessions per class)
- **Target:** `quiz_attempts.score / max_score`
- **Features:** all fields from `tracking_sessions.features`
- **Training:** Celery task triggered after each quiz submission; retrain when N new samples accumulated
- **Per-class models** with fallback to global model for cold start
- **Storage:** Serialized to `prediction_models` table (pickle + metadata)

### Stage 3 — Prediction Flow
1. Session ends → features extracted → heuristic or XGBoost prediction stored
2. Student submits quiz → `actual_score` backfilled into `score_predictions`
3. Model drift monitoring: if RMSE degrades >15%, flag for retraining

**Educator dashboard surfaces:** predicted vs actual scores, feature importances per student, class-level engagement heatmaps.

---

## Phase 4: LLM Student Profile System

### Profile Design — Append-Only Entries
Each quiz submission generates one new `student_profile_entries` row. There is no single merged profile — RAG retrieves the most relevant past entries at personalization time, naturally weighting recent and topic-relevant observations.

**Each entry captures one learning event:**
```json
{
  "topic": "recursion",
  "observed_score": 0.62,
  "predicted_score": 0.71,
  "strengths_observed": ["understood base cases"],
  "struggles_observed": ["confused by nested calls"],
  "engagement_notes": "re-read call stack section 4x, high hover on diagrams",
  "behavioral_summary": "slow careful reader, benefits from visual aids",
  "recommendation": "use step-through examples instead of abstract definitions"
}
```

### Generation Trigger
After every quiz submission, Celery task `add_student_profile_entry` runs:

```python
async def add_student_profile_entry(student_id, quiz_attempt_id):
    session_features = fetch_session_features(quiz_attempt_id)
    lesson_summary = fetch_material_summary(quiz_attempt_id.material_id)
    quiz_result = fetch_quiz_result(quiz_attempt_id)
    
    prompt = build_entry_prompt(
        features=session_features,
        quiz_score=quiz_result,
        lesson_content=lesson_summary,
    )
    
    response = openrouter_client.chat.completions.create(
        model=settings.LLM_MODEL,  # configurable via env var
        messages=[{"role": "user", "content": prompt}],
    )
    
    entry = parse_profile_entry(response)
    embedding = embed(entry['text'])
    save_profile_entry(student_id, entry, embedding, quiz_attempt_id)
```

### OpenRouter Configuration
```python
# settings.py
LLM_MODEL: str = "anthropic/claude-opus-4-7"  # override via EDUTRACK_LLM_MODEL env var
OPENROUTER_API_KEY: str  # required

# OpenRouter uses OpenAI-compatible SDK
from openai import AsyncOpenAI
openrouter_client = AsyncOpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=settings.OPENROUTER_API_KEY,
)
```
Same client used for both profile entry generation and RAG lesson personalization.

### Prompt Design (new entry per event, no merging)
```
You are analyzing a student's learning session. Generate a focused profile entry.

LESSON: {lesson_title}
CONTENT SUMMARY: {lesson_summary}
BEHAVIORAL SESSION: {feature_summary}
QUIZ SCORE: {score}/{max_score}
SCORE PREDICTION WAS: {predicted}

Generate a JSON profile entry documenting what this session reveals about the student.
Focus on: observed strengths/struggles for this topic, engagement patterns, concrete recommendations.
Be specific and evidence-based. Return only valid JSON.
```

---

## Phase 5: Automatic RAG Personalized Lesson Generation

The entire pipeline is **invisible to educators** — they publish a lesson and students receive their personalized version. No educator action required beyond content creation.

### Trigger: Material Published
When educator calls `PUT /materials/{id}/publish`, Celery spawns one `personalize_lesson_for_student` task per enrolled student. Each task runs independently and in parallel.

### Embedding Pipeline
- `student_profile_entries.embedding` — each new entry is embedded immediately on creation
- Lesson sections embedded at publish time into `material_sections.embedding`
- All stored in `pgvector` with IVFFlat index
- Embedding model: `text-embedding-3-small` via OpenRouter or direct OpenAI

### Per-Student Personalization Flow
```
Event: material published to class
         ↓
For each enrolled student (parallel Celery tasks):
  1. Embed the new lesson's topic/content as a query vector
  2. Retrieve top-8 student profile entries (cosine similarity) — most topic-relevant observations
  3. Build generation prompt with retrieved entries + full lesson content
  4. Call OpenRouter (configurable model) → generate personalized lesson
  5. Save to personalized_lessons table
  6. Student's lesson viewer transparently serves their version
```

### Cold Start Handling
- New students with no profile entries receive the base lesson unmodified
- After their first quiz submission, a profile entry is created and embedded
- Background task `retroactively_personalize` runs when first entry is created: personalizes all already-published lessons for that student

### Generation Prompt
```
You are a skilled educator. Rewrite this lesson for a specific student.

STUDENT LEARNING PROFILE:
{top_profile_chunks}

ORIGINAL LESSON:
{lesson_sections}

Rewrite the lesson maintaining all factual content but:
- Adapt examples to the student's demonstrated interests and strengths
- Add extra scaffolding in areas matching the student's known weaknesses
- Adjust pacing and section length to match their reading and engagement patterns
- Keep the same quiz questions and learning objectives

Return the full rewritten lesson in structured markdown.
```

### Student Experience
- Students navigate to the lesson as normal
- Backend transparently serves their `personalized_lessons.generated_content` if available
- Falls back to base material if personalization isn't ready yet
- No UI difference — personalization is invisible infrastructure

---

## Implementation Phases & Order

| Phase | Deliverable | Depends On |
|---|---|---|
| 1a | Auth + DB schema + migrations | — |
| 1b | Class + Material + Quiz CRUD | 1a |
| 1c | Next.js base layout + auth | 1a |
| 1d | Lesson viewer + quiz UI | 1b, 1c |
| 2a | WebSocket tracking backend | 1b |
| 2b | Browser tracker + feature extraction | 2a |
| 3a | Heuristic scorer + prediction API | 2b |
| 3b | Celery + XGBoost training pipeline | 3a |
| 4a | Claude profile generation (Celery task) | 3a |
| 4b | Profile versioning + educator profile UI | 4a |
| 5a | pgvector embeddings + lesson embedding on publish | 4a |
| 5b | Auto-personalization Celery pipeline (triggered on publish) | 5a |
| 5c | Transparent personalized content serving in lesson viewer | 5b |

---

## Critical Files to Create

```
backend/
  app/services/tracking.py      — event ingestion, feature extraction
  app/services/ml.py            — heuristic scorer + XGBoost pipeline
  app/services/profile.py       — OpenRouter profile entry generation (append-only)
  app/services/rag.py           — pgvector retrieval of profile entries + OpenRouter lesson generation
  app/workers/tasks.py          — Celery task definitions
  app/api/tracking.py           — WebSocket endpoint
  alembic/versions/             — DB migrations

frontend/
  components/LessonViewer/      — section renderer + tracking hooks
  lib/tracker.ts                — WebSocket manager + event capture
  app/educator/students/[id]/profile/page.tsx  — read-only auto profile view
```

---

## Key Dependencies

```
# Backend
fastapi, uvicorn, sqlalchemy[asyncio], asyncpg, alembic
pydantic-settings, python-jose[cryptography], passlib[bcrypt]
redis[asyncio], celery, flower
openai     # OpenAI-compatible SDK (used for OpenRouter)
xgboost, scikit-learn, numpy, pandas
pgvector   # SQLAlchemy extension
tiktoken   # token counting

# Frontend
next@14, typescript, tailwindcss
@tanstack/react-query  # data fetching
zustand                # local state
recharts               # score/engagement charts
```

---

## Verification & Testing

1. **Auth flow:** Register student + educator, login, JWT refresh
2. **Class workflow:** Educator creates class → student enrolls with code → material assigned → visible to student
3. **Tracking:** Open lesson, move mouse/hover → WebSocket events arrive in Redis → session end triggers feature extraction → `tracking_sessions.features` populated
4. **Quiz + prediction:** Submit quiz → `score_predictions` row created → heuristic score within ±20% of actual (manual check)
5. **Profile generation:** Verify Celery task fires after quiz submit → `student_profile_versions` row added → profile JSON matches schema
6. **Auto-personalization:** Educator publishes lesson → verify Celery tasks spawned per enrolled student → `personalized_lessons` rows created → student navigates to lesson and receives personalized version without any special action
7. **Cold start fallback:** New student with no profile views lesson → receives base content → after first quiz, profile created → background task generates their personalized version
8. **Model upgrade:** Seed 50+ sessions → trigger XGBoost train → verify model artifact saved, predictions switch to ML model
