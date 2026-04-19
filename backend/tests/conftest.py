"""Shared fixtures for the EduTrack backend test suite.

Environment assumptions (same as scripts/verify.sh):
    EDUTRACK_DATABASE_URL, EDUTRACK_REDIS_URL, EDUTRACK_CELERY_TASK_ALWAYS_EAGER=1,
    EDUTRACK_LLM_PROVIDER=deterministic, PYTHONPATH=<repo>/backend

Conftest forces deterministic + eager celery defaults if callers forgot, then
imports the app lazily so get_settings() picks up the environment.
"""

from __future__ import annotations

import asyncio
import os
from typing import Any, Iterator

import pytest


def _xgboost_available() -> bool:
    try:
        import xgboost  # noqa: F401
    except Exception:
        return False
    return True


_XGBOOST_AVAILABLE = _xgboost_available()


xgboost_required = pytest.mark.skipif(
    not _XGBOOST_AVAILABLE,
    reason="xgboost library failed to load (likely missing libomp); skipping xgboost-dependent tests.",
)

os.environ.setdefault("EDUTRACK_CELERY_TASK_ALWAYS_EAGER", "1")
os.environ.setdefault("EDUTRACK_LLM_PROVIDER", "deterministic")
os.environ.setdefault("EDUTRACK_XGBOOST_MIN_SAMPLES", "50")

from fastapi.testclient import TestClient  # noqa: E402
from redis.asyncio import Redis  # noqa: E402
from sqlalchemy import text  # noqa: E402

from app.celery_app import celery_app  # noqa: E402
from app.db import AsyncSessionLocal  # noqa: E402
from app.main import app  # noqa: E402
from app.settings import get_settings  # noqa: E402

# Ensure celery really runs eagerly even if the env var was set after import.
celery_app.conf.task_always_eager = True
celery_app.conf.task_eager_propagates = True


TABLES_IN_ORDER = [
    "tribe_predictions",
    "research_neural_models",
    "asset_fit_scores",
    "lesson_plan_edges",
    "lesson_plan_nodes",
    "lesson_plan_drafts",
    "lesson_assets",
    "personalized_lessons",
    "student_profile_entries",
    "prediction_models",
    "score_predictions",
    "section_focus_scores",
    "tracking_events",
    "quiz_attempts",
    "tracking_sessions",
    "quiz_questions",
    "material_topics",
    "material_sections",
    "materials",
    "enrollments",
    "classes",
    "topic_mastery_edges",
    "topic_mastery_nodes",
    "user_learning_profiles",
    "educator_profiles",
    "users",
]


async def _truncate_all() -> None:
    async with AsyncSessionLocal() as db:
        dialect = db.bind.dialect.name if db.bind else "postgresql"
        if dialect == "postgresql":
            await db.execute(
                text("TRUNCATE " + ", ".join(TABLES_IN_ORDER) + " RESTART IDENTITY CASCADE")
            )
        else:
            for table in TABLES_IN_ORDER:
                await db.execute(text(f"DELETE FROM {table}"))
        await db.commit()


async def _flush_redis() -> None:
    redis = Redis.from_url(get_settings().redis_url, decode_responses=True)
    try:
        await redis.flushdb()
    finally:
        await redis.aclose()


@pytest.fixture(autouse=True)
def _clean_state() -> Iterator[None]:
    """Reset Postgres/SQLite tables and Redis before every test."""
    asyncio.run(_truncate_all())
    asyncio.run(_flush_redis())
    yield


@pytest.fixture
def client() -> Iterator[TestClient]:
    with TestClient(app) as test_client:
        yield test_client


# ---------------------------------------------------------------------------
# Auth + factory helpers
# ---------------------------------------------------------------------------


def auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def register_user(
    client: TestClient,
    email: str,
    role: str,
    password: str = "password-123",
    institution: str = "Test Institute",
) -> dict[str, Any]:
    response = client.post(
        "/auth/register",
        json={"email": email, "password": password, "role": role, "institution": institution},
    )
    assert response.status_code == 200, response.text
    return response.json()


@pytest.fixture
def educator(client: TestClient) -> dict[str, Any]:
    return register_user(client, "educator@example.com", "educator")


@pytest.fixture
def researcher(client: TestClient) -> dict[str, Any]:
    return register_user(client, "researcher@example.com", "researcher")


@pytest.fixture
def student(client: TestClient) -> dict[str, Any]:
    return register_user(client, "student@example.com", "student")


@pytest.fixture
def second_student(client: TestClient) -> dict[str, Any]:
    return register_user(client, "second-student@example.com", "student")


def make_class(client: TestClient, educator_token: str, title: str = "Computer Science") -> dict[str, Any]:
    response = client.post(
        "/classes",
        json={"title": title, "description": "desc"},
        headers=auth_headers(educator_token),
    )
    assert response.status_code == 200, response.text
    return response.json()


def enroll_student(
    client: TestClient,
    student_token: str,
    class_id: int,
    enrollment_code: str,
) -> dict[str, Any]:
    response = client.post(
        f"/classes/{class_id}/enroll",
        json={"enrollment_code": enrollment_code},
        headers=auth_headers(student_token),
    )
    assert response.status_code == 200, response.text
    return response.json()


DEFAULT_SECTIONS = [
    {
        "title": "Base cases",
        "content": "A recursive function needs a stopping condition. The base case returns an answer without making another recursive call.",
        "order_index": 0,
    },
    {
        "title": "Recursive steps",
        "content": "The recursive step reduces the problem. Each call should move closer to the base case while preserving the original goal.",
        "order_index": 1,
    },
]


def make_material(
    client: TestClient,
    educator_token: str,
    class_id: int,
    title: str = "Recursion",
    sections: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    response = client.post(
        f"/classes/{class_id}/materials",
        json={
            "title": title,
            "type": "lesson",
            "sections": sections or DEFAULT_SECTIONS,
        },
        headers=auth_headers(educator_token),
    )
    assert response.status_code == 200, response.text
    return response.json()


DEFAULT_QUIZ = [
    {"question": "What stops recursion?", "options": ["Base case", "Timer"], "correct_answer": "Base case", "points": 1},
    {"question": "What should each step do?", "options": ["Grow", "Reduce the problem"], "correct_answer": "Reduce the problem", "points": 1},
]


def make_quiz(
    client: TestClient,
    educator_token: str,
    material_id: int,
    questions: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    response = client.post(
        f"/materials/{material_id}/quiz",
        json=questions or DEFAULT_QUIZ,
        headers=auth_headers(educator_token),
    )
    assert response.status_code == 200, response.text
    return response.json()


def publish_material(client: TestClient, educator_token: str, material_id: int) -> dict[str, Any]:
    response = client.put(
        f"/materials/{material_id}/publish",
        headers=auth_headers(educator_token),
    )
    assert response.status_code == 200, response.text
    return response.json()


@pytest.fixture
def published_class(
    client: TestClient,
    educator: dict[str, Any],
    student: dict[str, Any],
) -> dict[str, Any]:
    """Educator creates a class with a published lesson + quiz, student enrolled."""
    educator_token = educator["access_token"]
    student_token = student["access_token"]

    cls = make_class(client, educator_token)
    enroll_student(client, student_token, cls["id"], cls["enrollment_code"])
    material = make_material(client, educator_token, cls["id"])
    questions = make_quiz(client, educator_token, material["id"])
    publish_material(client, educator_token, material["id"])
    return {
        "class": cls,
        "material": material,
        "questions": questions,
        "section_ids": [section["id"] for section in material["sections"]],
    }


# ---------------------------------------------------------------------------
# Tracked-session helper
# ---------------------------------------------------------------------------


SAMPLE_EVENTS: list[dict[str, Any]] = [
    {"event_type": "section_view", "section_id": "PLACEHOLDER_0"},
    {"event_type": "hover_start", "section_id": "PLACEHOLDER_0", "element_id": "term-base-case"},
    {"event_type": "hover_end", "section_id": "PLACEHOLDER_0", "element_id": "term-base-case", "duration_ms": 800},
    {"event_type": "mouse_move", "x": 10, "y": 20, "velocity": 0.3},
    {"event_type": "scroll", "direction": "down", "position": 55, "velocity": 0.6},
    {"event_type": "text_select", "section_id": "PLACEHOLDER_0", "char_count": 24},
    {"event_type": "section_exit", "section_id": "PLACEHOLDER_0", "time_spent_ms": 15_000},
    {"event_type": "section_view", "section_id": "PLACEHOLDER_1"},
    {"event_type": "section_view", "section_id": "PLACEHOLDER_0"},
    {"event_type": "hover_start", "section_id": "PLACEHOLDER_1", "element_id": "diagram"},
    {"event_type": "hover_end", "section_id": "PLACEHOLDER_1", "element_id": "diagram", "duration_ms": 1200},
    {"event_type": "scroll", "direction": "up", "position": 30, "velocity": 0.4},
    {"event_type": "idle_end", "duration_ms": 2000},
    {"event_type": "section_exit", "section_id": "PLACEHOLDER_1", "time_spent_ms": 15_000},
]


def run_tracked_session(
    client: TestClient,
    student_token: str,
    material_id: int,
    section_ids: list[int],
) -> dict[str, Any]:
    """Start → stream 14 events over WebSocket → end. Returns SessionEndOut body."""
    started = client.post(
        "/sessions/start",
        json={"material_id": material_id},
        headers=auth_headers(student_token),
    )
    assert started.status_code == 200, started.text
    session_id = started.json()["session_id"]

    now = 1_700_000_000_000
    events: list[dict[str, Any]] = []
    for template in SAMPLE_EVENTS:
        event = dict(template)
        sid = event.get("section_id")
        if sid == "PLACEHOLDER_0":
            event["section_id"] = str(section_ids[0])
        elif sid == "PLACEHOLDER_1":
            event["section_id"] = str(section_ids[1 % len(section_ids)])
        events.append(event)

    with client.websocket_connect(f"/track/{session_id}?token={student_token}") as ws:
        ws.send_json({"type": "heartbeat"})
        assert ws.receive_json()["type"] == "ack"
        for offset, event in enumerate(events):
            ws.send_json({"type": "event", "data": event, "ts": now + offset * 500})
            assert ws.receive_json()["type"] == "ack"

    ended = client.post(f"/sessions/{session_id}/end", headers=auth_headers(student_token))
    assert ended.status_code == 200, ended.text
    return ended.json()


def submit_quiz_answers(
    client: TestClient,
    student_token: str,
    material_id: int,
    questions: list[dict[str, Any]],
    correct_map: dict[str, str],
    session_id: int | None = None,
) -> dict[str, Any]:
    """Submit answers; correct_map is question_id_str -> selected option."""
    response = client.post(
        f"/quiz/{material_id}/submit",
        json={"answers": correct_map, "session_id": session_id},
        headers=auth_headers(student_token),
    )
    assert response.status_code == 200, response.text
    return response.json()
