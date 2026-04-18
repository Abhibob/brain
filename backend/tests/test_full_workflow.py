from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi.testclient import TestClient
from redis.asyncio import Redis
from sqlalchemy import func, select, text

from app.db import AsyncSessionLocal
from app.main import app
from app.models import MaterialSection, PersonalizedLesson, PredictionModel, QuizAttempt, ScorePrediction, StudentProfileEntry, TrackingEvent, TrackingSession
from app.services.profile import parse_profile_entry_content
from app.settings import get_settings
from app.workers import tasks


def auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def reset_state() -> None:
    async with AsyncSessionLocal() as db:
        dialect = db.bind.dialect.name if db.bind else "postgresql"
        if dialect == "postgresql":
            await db.execute(
                text(
                    """
                    TRUNCATE
                      personalized_lessons,
                      student_profile_entries,
                      prediction_models,
                      score_predictions,
                      tracking_events,
                      quiz_attempts,
                      tracking_sessions,
                      quiz_questions,
                      material_sections,
                      materials,
                      enrollments,
                      classes,
                      educator_profiles,
                      users
                    RESTART IDENTITY CASCADE
                    """
                )
            )
        else:
            for table in [
                "personalized_lessons",
                "student_profile_entries",
                "prediction_models",
                "score_predictions",
                "tracking_events",
                "quiz_attempts",
                "tracking_sessions",
                "quiz_questions",
                "material_sections",
                "materials",
                "enrollments",
                "classes",
                "educator_profiles",
                "users",
            ]:
                await db.execute(text(f"DELETE FROM {table}"))
        await db.commit()
    redis = Redis.from_url(get_settings().redis_url, decode_responses=True)
    await redis.flushdb()
    await redis.aclose()


async def redis_llen(key: str) -> int:
    redis = Redis.from_url(get_settings().redis_url, decode_responses=True)
    try:
        return await redis.llen(key)
    finally:
        await redis.aclose()


def register(client: TestClient, email: str, role: str) -> dict[str, Any]:
    response = client.post(
        "/auth/register",
        json={"email": email, "password": "password-123", "role": role, "institution": "Test Institute"},
    )
    assert response.status_code == 200, response.text
    return response.json()


def create_tracked_session(client: TestClient, token: str, material_id: int, section_ids: list[int]) -> dict[str, Any]:
    started = client.post("/sessions/start", json={"material_id": material_id}, headers=auth(token))
    assert started.status_code == 200, started.text
    session_id = started.json()["session_id"]

    now = 1_700_000_000_000
    events = [
        {"event_type": "section_view", "section_id": str(section_ids[0]), "timestamp": now},
        {"event_type": "hover_start", "section_id": str(section_ids[0]), "element_id": "term-base-case"},
        {"event_type": "hover_end", "section_id": str(section_ids[0]), "element_id": "term-base-case", "duration_ms": 800},
        {"event_type": "mouse_move", "x": 10, "y": 20, "velocity": 0.3},
        {"event_type": "scroll", "direction": "down", "position": 55, "velocity": 0.6},
        {"event_type": "text_select", "section_id": str(section_ids[0]), "char_count": 24},
        {"event_type": "section_exit", "section_id": str(section_ids[0]), "time_spent_ms": 15_000},
        {"event_type": "section_view", "section_id": str(section_ids[1]), "timestamp": now + 16_000},
        {"event_type": "section_view", "section_id": str(section_ids[0]), "timestamp": now + 18_000},
        {"event_type": "hover_start", "section_id": str(section_ids[1]), "element_id": "diagram-call-stack"},
        {"event_type": "hover_end", "section_id": str(section_ids[1]), "element_id": "diagram-call-stack", "duration_ms": 1200},
        {"event_type": "scroll", "direction": "up", "position": 30, "velocity": 0.4},
        {"event_type": "idle_end", "duration_ms": 2_000},
        {"event_type": "section_exit", "section_id": str(section_ids[1]), "time_spent_ms": 15_000},
    ]
    with client.websocket_connect(f"/track/{session_id}?token={token}") as websocket:
        websocket.send_json({"type": "heartbeat"})
        assert websocket.receive_json()["type"] == "ack"
        for offset, event in enumerate(events):
            websocket.send_json({"type": "event", "data": event, "ts": now + offset * 500})
            assert websocket.receive_json()["type"] == "ack"

    assert asyncio.run(redis_llen(f"tracking:{session_id}")) == len(events)
    ended = client.post(f"/sessions/{session_id}/end", headers=auth(token))
    assert ended.status_code == 200, ended.text
    body = ended.json()
    assert body["features"]["section_completion_rate"] == 1
    assert body["features"]["hover_count"] == 2
    assert body["features"]["text_selection_count"] == 1
    assert body["prediction"]["model_version"]
    assert asyncio.run(redis_llen(f"tracking:{session_id}")) == 0
    return body


async def assert_learning_artifacts(student_id: int, material_id: int, session_id: int) -> None:
    async with AsyncSessionLocal() as db:
        event_count = await db.scalar(select(func.count(TrackingEvent.id)).where(TrackingEvent.session_id == session_id))
        assert event_count and event_count >= 14
        prediction = await db.scalar(select(ScorePrediction).where(ScorePrediction.session_id == session_id))
        assert prediction is not None
        profile_entry = await db.scalar(select(StudentProfileEntry).where(StudentProfileEntry.user_id == student_id).order_by(StudentProfileEntry.id.desc()))
        assert profile_entry is not None
        assert profile_entry.embedding is not None and len(profile_entry.embedding) == 1536
        sections = (await db.scalars(select(MaterialSection).where(MaterialSection.material_id == material_id))).all()
        assert sections and all(section.embedding is not None and len(section.embedding) == 1536 for section in sections)
        personalized = await db.scalar(select(PersonalizedLesson).where(PersonalizedLesson.student_id == student_id, PersonalizedLesson.base_material_id == material_id))
        assert personalized is not None
        assert "STUDENT LEARNING PROFILE" in personalized.prompt_used


async def assert_model_artifact(class_id: int) -> None:
    async with AsyncSessionLocal() as db:
        model = await db.scalar(select(PredictionModel).where(PredictionModel.class_id == class_id).order_by(PredictionModel.id.desc()))
        assert model is not None
        assert model.artifact
        assert model.feature_importances
        assert model.sample_count >= get_settings().xgboost_min_samples


async def seed_training_samples(student_id: int, material_id: int, samples: int = 50) -> None:
    now = datetime.now(UTC)
    async with AsyncSessionLocal() as db:
        for index in range(samples):
            features = {
                "total_time_s": 40 + index,
                "hover_count": 2 + (index % 6),
                "avg_hover_duration_ms": 700 + index,
                "scroll_depth_pct": 70 + (index % 25),
                "back_scroll_count": index % 5,
                "scroll_velocity_avg": 0.2 + (index % 4) * 0.1,
                "mouse_velocity_avg": 0.1 + (index % 5) * 0.05,
                "mouse_velocity_variance": 0.02 + (index % 3) * 0.01,
                "idle_total_s": index % 8,
                "idle_count": index % 3,
                "text_selection_count": index % 4,
                "reading_speed_wpm": 130 + (index % 80),
                "section_completion_rate": 0.82 + (index % 15) / 100,
                "re_read_sections": ["1"] if index % 4 == 0 else [],
            }
            session = TrackingSession(
                student_id=student_id,
                material_id=material_id,
                started_at=now - timedelta(minutes=index + 2),
                ended_at=now - timedelta(minutes=index + 1),
                features=features,
            )
            db.add(session)
            await db.flush()
            target = 0.55 + (index % 10) / 25
            db.add(
                QuizAttempt(
                    student_id=student_id,
                    material_id=material_id,
                    session_id=session.id,
                    answers={"seed": "A"},
                    score=min(target, 1.0),
                    max_score=1.0,
                )
            )
        await db.commit()


def test_full_edutrack_workflow() -> None:
    asyncio.run(reset_state())
    parsed = parse_profile_entry_content(
        '```json\n{"topic":"recursion","observed_score":0.8,"predicted_score":0.7,"strengths_observed":["base case"],"struggles_observed":[],"engagement_notes":"steady","behavioral_summary":"visual","recommendation":"use diagrams"}\n```'
    )
    assert parsed["topic"] == "recursion"

    with TestClient(app) as client:
        educator = register(client, "educator@example.com", "educator")
        researcher = register(client, "researcher@example.com", "researcher")
        student = register(client, "student@example.com", "student")

        login = client.post("/auth/login", json={"email": "educator@example.com", "password": "password-123"})
        assert login.status_code == 200
        refreshed = client.post("/auth/refresh", json={"refresh_token": login.json()["refresh_token"]})
        assert refreshed.status_code == 200
        educator_token = refreshed.json()["access_token"]
        researcher_token = researcher["access_token"]
        student_token = student["access_token"]

        created_class = client.post(
            "/classes",
            json={"title": "Computer Science", "description": "Adaptive recursion unit"},
            headers=auth(educator_token),
        )
        assert created_class.status_code == 200, created_class.text
        class_id = created_class.json()["id"]
        enrollment_code = created_class.json()["enrollment_code"]

        enroll = client.post(f"/classes/{class_id}/enroll", json={"enrollment_code": enrollment_code}, headers=auth(student_token))
        assert enroll.status_code == 200, enroll.text
        researcher_classes = client.get("/classes", headers=auth(researcher_token))
        assert researcher_classes.status_code == 200
        assert any(item["id"] == class_id for item in researcher_classes.json())

        lesson = client.post(
            f"/classes/{class_id}/materials",
            json={
                "title": "Recursion",
                "type": "lesson",
                "sections": [
                    {
                        "title": "Base cases",
                        "content": "A recursive function needs a stopping condition. The base case returns an answer without making another recursive call. This keeps the problem finite and makes the result traceable.",
                        "order_index": 0,
                    },
                    {
                        "title": "Recursive steps",
                        "content": "The recursive step reduces the problem. Each call should move closer to the base case while preserving the original goal. Tracing the call stack helps explain how answers return.",
                        "order_index": 1,
                    },
                ],
            },
            headers=auth(educator_token),
        )
        assert lesson.status_code == 200, lesson.text
        material = lesson.json()
        material_id = material["id"]
        section_ids = [section["id"] for section in material["sections"]]

        quiz_payload = [
            {"question": "What stops recursion?", "options": ["Base case", "Timer", "Database"], "correct_answer": "Base case", "points": 1},
            {"question": "What should each recursive step do?", "options": ["Grow", "Reduce the problem", "Ignore input"], "correct_answer": "Reduce the problem", "points": 1},
            {"question": "What helps trace returns?", "options": ["Call stack", "CSS", "Cache"], "correct_answer": "Call stack", "points": 1},
            {"question": "What happens without a base case?", "options": ["May not stop", "Always faster", "No effect"], "correct_answer": "May not stop", "points": 1},
            {"question": "Which preserves correctness?", "options": ["Move toward base case", "Random calls", "Skip tests"], "correct_answer": "Move toward base case", "points": 1},
        ]
        quiz = client.post(
            f"/materials/{material_id}/quiz",
            json=quiz_payload,
            headers=auth(educator_token),
        )
        assert quiz.status_code == 200, quiz.text
        questions = quiz.json()

        publish = client.put(f"/materials/{material_id}/publish", headers=auth(educator_token))
        assert publish.status_code == 200, publish.text
        assert publish.json()["personalization_tasks"] == 1

        cold_start_lesson = client.get(f"/materials/{material_id}", headers=auth(student_token))
        assert cold_start_lesson.status_code == 200
        assert cold_start_lesson.json()["personalized"] is False
        assert cold_start_lesson.json()["generated_content"] is None

        ended = create_tracked_session(client, student_token, material_id, section_ids)
        predicted = float(ended["prediction"]["predicted_score"])
        assert ended["prediction"]["model_version"] == "heuristic-v1"
        student_prediction_lookup = client.get(f"/sessions/{ended['session_id']}/prediction", headers=auth(student_token))
        assert student_prediction_lookup.status_code == 403
        educator_prediction_lookup = client.get(f"/sessions/{ended['session_id']}/prediction", headers=auth(educator_token))
        assert educator_prediction_lookup.status_code == 403
        prediction_lookup = client.get(f"/sessions/{ended['session_id']}/prediction", headers=auth(researcher_token))
        assert prediction_lookup.status_code == 200, prediction_lookup.text
        assert prediction_lookup.json()["predicted_score"] == predicted

        answers = {str(question["id"]): quiz_payload[index]["correct_answer"] for index, question in enumerate(questions)}
        answers[str(questions[-1]["id"])] = "Skip tests"
        submitted = client.post(f"/quiz/{material_id}/submit", json={"answers": answers, "session_id": ended["session_id"]}, headers=auth(student_token))
        assert submitted.status_code == 200, submitted.text
        actual = submitted.json()["normalized_score"]
        assert abs(predicted - actual) <= 0.2
        researcher_prediction_lookup = client.get(f"/sessions/{ended['session_id']}/prediction", headers=auth(researcher_token))
        assert researcher_prediction_lookup.status_code == 200
        assert researcher_prediction_lookup.json()["actual_score"] == actual

        educator_profile = client.get(f"/students/{student['user']['id']}/profile", headers=auth(educator_token))
        assert educator_profile.status_code == 403
        profile = client.get(f"/students/{student['user']['id']}/profile", headers=auth(researcher_token))
        assert profile.status_code == 200, profile.text
        assert profile.json()["entry_count"] == 1
        entry = profile.json()["entries"][0]["profile_json"]
        assert {"topic", "observed_score", "recommendation", "behavioral_summary"}.issubset(entry.keys())

        personalized = client.get(f"/materials/{material_id}", headers=auth(student_token))
        assert personalized.status_code == 200
        assert personalized.json()["personalized"] is True
        assert "## Quick Practice" in personalized.json()["generated_content"]
        assert "Personalized guidance" not in personalized.json()["generated_content"]
        asyncio.run(assert_learning_artifacts(student["user"]["id"], material_id, ended["session_id"]))

        updated = client.put(
            f"/materials/{material_id}",
            json={"title": "Recursion Revised"},
            headers=auth(educator_token),
        )
        assert updated.status_code == 200, updated.text
        assert updated.json()["title"] == "Recursion Revised"

        educator_roster = client.get(f"/classes/{class_id}/students", headers=auth(educator_token))
        assert educator_roster.status_code == 200
        assert "profile_entry_count" not in educator_roster.json()[0]
        researcher_roster = client.get(f"/classes/{class_id}/students", headers=auth(researcher_token))
        assert researcher_roster.status_code == 200
        assert "profile_entry_count" in researcher_roster.json()[0]

        educator_analytics = client.get(f"/classes/{class_id}/analytics", headers=auth(educator_token))
        assert educator_analytics.status_code == 403
        analytics = client.get(f"/classes/{class_id}/analytics", headers=auth(researcher_token))
        assert analytics.status_code == 200, analytics.text
        assert analytics.json()["students"][0]["average_predicted"] is not None
        assert analytics.json()["students"][0]["average_actual"] == actual
        assert analytics.json()["section_heatmap"]

        draft = client.post(
            f"/classes/{class_id}/materials",
            json={"title": "Draft to delete", "type": "lesson", "sections": [{"title": "Draft", "content": "temporary", "order_index": 0}]},
            headers=auth(educator_token),
        )
        assert draft.status_code == 200
        deleted = client.delete(f"/materials/{draft.json()['id']}", headers=auth(educator_token))
        assert deleted.status_code == 200
        missing = client.get(f"/materials/{draft.json()['id']}", headers=auth(educator_token))
        assert missing.status_code == 404

        second_lesson = client.post(
            f"/classes/{class_id}/materials",
            json={
                "title": "Tree Recursion",
                "type": "lesson",
                "sections": [
                    {"title": "Branching calls", "content": "Tree recursion makes more than one recursive call from a single frame.", "order_index": 0},
                    {"title": "Combining answers", "content": "Each branch returns a partial answer that must be combined into the final result.", "order_index": 1},
                ],
            },
            headers=auth(educator_token),
        )
        assert second_lesson.status_code == 200
        second_material_id = second_lesson.json()["id"]
        second_update = client.put(
            f"/materials/{second_material_id}",
            json={
                "title": "Tree Recursion Revised",
                "sections": [
                    {"title": "Branching calls", "content": "Tree recursion makes more than one recursive call from a single frame. Track each branch separately.", "order_index": 0},
                    {"title": "Combining answers", "content": "Each branch returns a partial answer that is combined into the final result.", "order_index": 1},
                ],
            },
            headers=auth(educator_token),
        )
        assert second_update.status_code == 200, second_update.text
        second_section_ids = [section["id"] for section in second_update.json()["sections"]]
        second_quiz = client.post(
            f"/materials/{second_material_id}/quiz",
            json=[
                {"question": "How many calls can a tree-recursive frame make?", "options": ["More than one", "None"], "correct_answer": "More than one", "points": 1}
            ],
            headers=auth(educator_token),
        )
        assert second_quiz.status_code == 200
        second_publish = client.put(f"/materials/{second_material_id}/publish", headers=auth(educator_token))
        assert second_publish.status_code == 200
        assert second_publish.json()["personalization_tasks"] == 1
        second_personalized = client.get(f"/materials/{second_material_id}", headers=auth(student_token))
        assert second_personalized.json()["personalized"] is True

        new_student = register(client, "new-student@example.com", "student")
        new_student_token = new_student["access_token"]
        new_enroll = client.post(f"/classes/{class_id}/enroll", json={"enrollment_code": enrollment_code}, headers=auth(new_student_token))
        assert new_enroll.status_code == 200
        new_cold_start = client.get(f"/materials/{second_material_id}", headers=auth(new_student_token))
        assert new_cold_start.status_code == 200
        assert new_cold_start.json()["personalized"] is False

        new_ended = create_tracked_session(client, new_student_token, second_material_id, second_section_ids)
        new_answers = {str(second_quiz.json()[0]["id"]): "More than one"}
        new_submit = client.post(
            f"/quiz/{second_material_id}/submit",
            json={"answers": new_answers, "session_id": new_ended["session_id"]},
            headers=auth(new_student_token),
        )
        assert new_submit.status_code == 200, new_submit.text
        new_personalized = client.get(f"/materials/{second_material_id}", headers=auth(new_student_token))
        assert new_personalized.status_code == 200
        assert new_personalized.json()["personalized"] is True

        asyncio.run(seed_training_samples(student["user"]["id"], material_id))
        training_result = tasks.train_model_for_class.delay(class_id).result
        assert training_result["model_type"] == "xgboost"
        assert training_result["sample_count"] >= 50
        global_training_result = tasks.train_global_model.delay().result
        assert global_training_result["model_type"] == "xgboost"
        assert global_training_result["sample_count"] >= 50

        ml_session = create_tracked_session(client, student_token, material_id, section_ids)
        assert ml_session["prediction"]["model_version"].startswith("ml-")
        trained_analytics = client.get(f"/classes/{class_id}/analytics", headers=auth(researcher_token))
        assert trained_analytics.status_code == 200
        assert trained_analytics.json()["model"]["model_type"] == "xgboost"
        assert trained_analytics.json()["drift"]["flagged"] in {True, False}
        assert trained_analytics.json()["model"]["feature_importances"]
        asyncio.run(assert_model_artifact(class_id))
