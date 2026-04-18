"""End-to-end pipeline tests driven through HTTP endpoints.

Lighter than `test_full_workflow.py` — focuses on the end-to-end happy path once
the prerequisite fixtures are in place, then verifies artifacts on disk.
"""

from __future__ import annotations

import asyncio
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.db import AsyncSessionLocal
from app.models import (
    MaterialSection,
    PersonalizedLesson,
    ScorePrediction,
    StudentProfileEntry,
    TrackingEvent,
)
from tests.conftest import (
    DEFAULT_QUIZ,
    auth_headers,
    run_tracked_session,
    submit_quiz_answers,
)


async def _fetch_counts(student_id: int, material_id: int, session_id: int) -> dict[str, int]:
    async with AsyncSessionLocal() as db:
        events = await db.scalar(select(func.count(TrackingEvent.id)).where(TrackingEvent.session_id == session_id))
        prediction = await db.scalar(
            select(func.count(ScorePrediction.id)).where(ScorePrediction.session_id == session_id)
        )
        profile = await db.scalar(
            select(func.count(StudentProfileEntry.id)).where(StudentProfileEntry.user_id == student_id)
        )
        personalized = await db.scalar(
            select(func.count(PersonalizedLesson.id)).where(
                PersonalizedLesson.student_id == student_id,
                PersonalizedLesson.base_material_id == material_id,
            )
        )
        section_embeddings = await db.scalar(
            select(func.count(MaterialSection.id)).where(MaterialSection.material_id == material_id)
        )
        return {
            "events": events or 0,
            "prediction": prediction or 0,
            "profile": profile or 0,
            "personalized": personalized or 0,
            "sections": section_embeddings or 0,
        }


class TestQuizToPersonalizationPipeline:
    def test_full_flow_writes_all_artifacts(
        self,
        client: TestClient,
        published_class: dict[str, Any],
        student: dict[str, Any],
    ) -> None:
        material_id = published_class["material"]["id"]
        section_ids = published_class["section_ids"]
        ended = run_tracked_session(client, student["access_token"], material_id, section_ids)

        answers = {str(q["id"]): DEFAULT_QUIZ[i]["correct_answer"] for i, q in enumerate(published_class["questions"])}
        submit = submit_quiz_answers(
            client,
            student["access_token"],
            material_id,
            published_class["questions"],
            answers,
            session_id=ended["session_id"],
        )
        assert submit["normalized_score"] == 1.0

        counts = asyncio.run(
            _fetch_counts(student["user"]["id"], material_id, ended["session_id"])
        )
        assert counts["events"] >= len([e for e in range(14)])
        assert counts["prediction"] == 1
        assert counts["profile"] >= 1
        assert counts["personalized"] == 1

    def test_cold_start_then_personalized(
        self,
        client: TestClient,
        published_class: dict[str, Any],
        student: dict[str, Any],
    ) -> None:
        material_id = published_class["material"]["id"]
        cold = client.get(f"/materials/{material_id}", headers=auth_headers(student["access_token"]))
        assert cold.json()["personalized"] is False
        assert cold.json()["generated_content"] is None

        ended = run_tracked_session(client, student["access_token"], material_id, published_class["section_ids"])
        answers = {str(q["id"]): DEFAULT_QUIZ[i]["correct_answer"] for i, q in enumerate(published_class["questions"])}
        submit_quiz_answers(
            client,
            student["access_token"],
            material_id,
            published_class["questions"],
            answers,
            session_id=ended["session_id"],
        )

        warm = client.get(f"/materials/{material_id}", headers=auth_headers(student["access_token"]))
        assert warm.json()["personalized"] is True
        assert warm.json()["generated_content"]
