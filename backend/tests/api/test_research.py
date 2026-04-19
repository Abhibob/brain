from __future__ import annotations

import asyncio
import math
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi.testclient import TestClient

from app.db import AsyncSessionLocal
from app.models import PersonalizedLesson, QuizAttempt, TrackingSession
from app.settings import get_settings
from tests.conftest import (
    auth_headers,
    enroll_student,
    make_class,
    make_material,
    register_user,
)


async def _seed_labeled_sessions(student_id: int, material_id: int, *, samples: int, score_base: float, hover_offset: int) -> None:
    now = datetime.now(UTC)
    async with AsyncSessionLocal() as db:
        for i in range(samples):
            features = {
                "total_time_s": 42 + i * 2 + hover_offset,
                "hover_count": hover_offset + (i % 6),
                "avg_hover_duration_ms": 480 + hover_offset * 30 + i,
                "scroll_depth_pct": 70 + (i % 20),
                "back_scroll_count": (i + hover_offset) % 7,
                "scroll_velocity_avg": 0.3 + hover_offset / 100,
                "mouse_velocity_avg": 0.2 + i / 100,
                "mouse_velocity_variance": 0.03 + hover_offset / 50,
                "idle_total_s": i % 4,
                "idle_count": i % 3,
                "text_selection_count": (i + hover_offset) % 5,
                "reading_speed_wpm": 130 + hover_offset * 8 + (i % 45),
                "section_completion_rate": min(0.72 + score_base / 3 + (i % 5) / 100, 1.0),
                "re_read_sections": ["1"] if i % 3 == 0 else [],
            }
            session = TrackingSession(
                student_id=student_id,
                material_id=material_id,
                started_at=now - timedelta(minutes=i + 5),
                ended_at=now - timedelta(minutes=i + 4),
                features=features,
                focus_score=0.55 + score_base / 3,
                focus_breakdown={"pace": 0.7, "completion": 0.8, "attention": 0.7, "engagement": 0.6},
                focus_label="focused" if score_base > 0.7 else "engaged",
            )
            db.add(session)
            await db.flush()
            normalized = min(max(score_base + (i % 4) / 20, 0.0), 1.0)
            db.add(
                QuizAttempt(
                    student_id=student_id,
                    material_id=material_id,
                    session_id=session.id,
                    answers={"1": "Base case"},
                    score=normalized,
                    max_score=1.0,
                )
            )
        await db.commit()


def _setup_class_with_two_students(client: TestClient) -> dict[str, Any]:
    educator = register_user(client, "research-ed@example.com", "educator")
    researcher = register_user(client, "researcher-api@example.com", "researcher")
    student_a = register_user(client, "research-a@example.com", "student")
    student_b = register_user(client, "research-b@example.com", "student")
    cls = make_class(client, educator["access_token"], "Research Methods")
    enroll_student(client, student_a["access_token"], cls["id"], cls["enrollment_code"])
    enroll_student(client, student_b["access_token"], cls["id"], cls["enrollment_code"])
    material = make_material(client, educator["access_token"], cls["id"], title="Gradient descent")
    return {
        "educator": educator,
        "researcher": researcher,
        "student_a": student_a,
        "student_b": student_b,
        "class": cls,
        "material": material,
    }


def test_research_workbench_is_researcher_only(client: TestClient) -> None:
    ctx = _setup_class_with_two_students(client)
    class_id = ctx["class"]["id"]

    denied = client.get(f"/research/classes/{class_id}/workbench", headers=auth_headers(ctx["educator"]["access_token"]))
    assert denied.status_code == 403

    allowed = client.get(f"/research/classes/{class_id}/workbench", headers=auth_headers(ctx["researcher"]["access_token"]))
    assert allowed.status_code == 200, allowed.text
    body = allowed.json()
    assert body["class"]["id"] == class_id
    assert len(body["students"]) == 2
    assert body["materials"][0]["id"] == ctx["material"]["id"]


def test_personalized_surrogates_have_finite_distinct_explanations(client: TestClient) -> None:
    ctx = _setup_class_with_two_students(client)
    class_id = ctx["class"]["id"]
    material_id = ctx["material"]["id"]
    student_a_id = ctx["student_a"]["user"]["id"]
    student_b_id = ctx["student_b"]["user"]["id"]
    asyncio.run(_seed_labeled_sessions(student_a_id, material_id, samples=8, score_base=0.82, hover_offset=7))
    asyncio.run(_seed_labeled_sessions(student_b_id, material_id, samples=8, score_base=0.44, hover_offset=1))
    headers = auth_headers(ctx["researcher"]["access_token"])

    train_a = client.post(f"/research/students/{student_a_id}/neural-surrogate/train?class_id={class_id}", headers=headers)
    train_b = client.post(f"/research/students/{student_b_id}/neural-surrogate/train?class_id={class_id}", headers=headers)
    assert train_a.status_code == 200, train_a.text
    assert train_b.status_code == 200, train_b.text
    assert train_a.json()["student_sample_count"] == 8
    assert train_b.json()["student_sample_count"] == 8

    view_a = client.get(f"/research/students/{student_a_id}/mechanistic?class_id={class_id}", headers=headers)
    view_b = client.get(f"/research/students/{student_b_id}/mechanistic?class_id={class_id}", headers=headers)
    assert view_a.status_code == 200, view_a.text
    assert view_b.status_code == 200, view_b.text
    body_a = view_a.json()
    body_b = view_b.json()
    assert body_a["model"]["personalized"] is True
    assert len(body_a["layers"]) == 4
    assert body_a["edges"]
    assert len(body_a["heatmaps"]) == 3
    assert body_a["heatmaps"][0]["id"] == "input-hidden1"
    assert len(body_a["heatmaps"][0]["gradients"]) > 1
    assert len(body_a["heatmaps"][0]["influence"]) > 1
    assert math.isfinite(body_a["heatmaps"][0]["stats"]["gradients"]["energy"])
    assert math.isfinite(body_a["heatmaps"][0]["stats"]["influence"]["energy"])
    assert body_a["features"]
    assert math.isfinite(body_a["backprop"]["loss"])
    assert math.isfinite(body_a["features"][0]["saliency"])
    assert body_a["backprop"]["prediction"] != body_b["backprop"]["prediction"]


def test_tribe_not_configured_is_persisted_cleanly(client: TestClient) -> None:
    ctx = _setup_class_with_two_students(client)
    headers = auth_headers(ctx["researcher"]["access_token"])
    student_id = ctx["student_a"]["user"]["id"]
    material_id = ctx["material"]["id"]

    response = client.post(f"/research/materials/{material_id}/students/{student_id}/tribe", headers=headers)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "not_configured"
    assert body["prediction"]["error"]

    lookup = client.get(f"/research/materials/{material_id}/students/{student_id}/tribe", headers=headers)
    assert lookup.status_code == 200
    assert lookup.json()["status"] == "not_configured"


def test_personalization_audit_is_researcher_only(client: TestClient) -> None:
    ctx = _setup_class_with_two_students(client)
    student_id = ctx["student_a"]["user"]["id"]
    material_id = ctx["material"]["id"]

    denied = client.get(
        f"/research/materials/{material_id}/students/{student_id}/personalization-audit",
        headers=auth_headers(ctx["educator"]["access_token"]),
    )
    assert denied.status_code == 403

    allowed = client.get(
        f"/research/materials/{material_id}/students/{student_id}/personalization-audit",
        headers=auth_headers(ctx["researcher"]["access_token"]),
    )
    assert allowed.status_code == 200, allowed.text
    assert allowed.json()["base_lesson"]["title"] == "Gradient descent"


def test_tribe_external_adapter_sends_personalized_content(client: TestClient, monkeypatch: Any) -> None:
    ctx = _setup_class_with_two_students(client)
    student_id = ctx["student_a"]["user"]["id"]
    material_id = ctx["material"]["id"]
    personalized_text = "# Personalized Gradient Descent\n\nUse shorter checkpoints."

    async def seed_personalized_lesson() -> None:
        async with AsyncSessionLocal() as db:
            db.add(
                PersonalizedLesson(
                    educator_id=ctx["educator"]["user"]["id"],
                    student_id=student_id,
                    base_material_id=material_id,
                    prompt_used="test prompt",
                    generated_content=personalized_text,
                )
            )
            await db.commit()

    asyncio.run(seed_personalized_lesson())

    captured: dict[str, Any] = {}

    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, Any]:
            return {
                "status": "complete",
                "model_version": "tribe-v2-test",
                "output_space": "fsaverage5",
                "hemodynamic_lag_s": 5,
                "roi_timeseries": {
                    "V1": [0.1, 0.25, 0.4],
                    "IFG": [-0.2, -0.1, 0.05],
                },
                "connectivity": [{"source": "V1", "target": "IFG", "weight": -0.42}],
                "surface": {"space": "fsaverage5", "vertex_count": 20484, "frame_count": 3},
            }

    class FakeClient:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            captured["timeout"] = kwargs.get("timeout")

        async def __aenter__(self) -> "FakeClient":
            return self

        async def __aexit__(self, *args: Any) -> None:
            return None

        async def post(self, url: str, headers: dict[str, str], json: dict[str, Any]) -> FakeResponse:
            captured["url"] = url
            captured["headers"] = headers
            captured["json"] = json
            return FakeResponse()

    monkeypatch.setenv("EDUTRACK_TRIBE_V2_ENABLED", "1")
    monkeypatch.setenv("EDUTRACK_TRIBE_V2_BASE_URL", "https://tribe.example.test")
    monkeypatch.setenv("EDUTRACK_TRIBE_V2_API_KEY", "secret")
    get_settings.cache_clear()
    monkeypatch.setattr("app.services.tribe.httpx.AsyncClient", FakeClient)

    response = client.post(
        f"/research/materials/{material_id}/students/{student_id}/tribe",
        headers=auth_headers(ctx["researcher"]["access_token"]),
    )
    get_settings.cache_clear()

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "complete"
    assert body["prediction"]["model_version"] == "tribe-v2-test"
    assert body["prediction"]["roi_timeseries"]["V1"] == [0.1, 0.25, 0.4]
    assert captured["url"] == "https://tribe.example.test/predict"
    assert captured["headers"]["Authorization"] == "Bearer secret"
    assert captured["json"]["stimulus"]["text"] == personalized_text
