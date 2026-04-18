"""Integration tests for app.services.profile.generate_profile_entry."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy import select

from app.db import AsyncSessionLocal
from app.models import (
    Class,
    Enrollment,
    Material,
    MaterialSection,
    QuizAttempt,
    ScorePrediction,
    StudentProfileEntry,
    TrackingSession,
    User,
)
from app.services.profile import generate_profile_entry


async def _seed_attempt() -> dict[str, int]:
    async with AsyncSessionLocal() as db:
        student = User(email="prof-s@example.com", hashed_password="x", role="student")
        educator = User(email="prof-e@example.com", hashed_password="x", role="educator")
        db.add_all([student, educator])
        await db.flush()
        cls = Class(educator_id=educator.id, title="Prof", enrollment_code="PROF1234")
        db.add(cls)
        await db.flush()
        db.add(Enrollment(class_id=cls.id, student_id=student.id))
        material = Material(class_id=cls.id, title="Recursion", type="lesson")
        db.add(material)
        await db.flush()
        db.add(
            MaterialSection(
                material_id=material.id,
                title="Base",
                content="stopping condition",
                order_index=0,
                word_count=2,
            )
        )
        session = TrackingSession(
            student_id=student.id,
            material_id=material.id,
            started_at=datetime.now(UTC),
            ended_at=datetime.now(UTC),
            features={"section_completion_rate": 1.0, "hover_count": 2, "reading_speed_wpm": 180},
        )
        db.add(session)
        await db.flush()
        db.add(ScorePrediction(session_id=session.id, predicted_score=0.7, confidence=0.45, model_version="heuristic-v1"))
        attempt = QuizAttempt(
            student_id=student.id,
            material_id=material.id,
            session_id=session.id,
            answers={"1": "A"},
            score=4,
            max_score=5,
        )
        db.add(attempt)
        await db.commit()
        return {"student_id": student.id, "attempt_id": attempt.id, "material_id": material.id}


@pytest.mark.asyncio
class TestGenerateProfileEntry:
    async def test_creates_entry_with_embedding(self) -> None:
        ctx = await _seed_attempt()
        async with AsyncSessionLocal() as db:
            entry = await generate_profile_entry(ctx["student_id"], ctx["attempt_id"], db)
            assert entry.id
            assert entry.embedding is not None
            assert len(entry.embedding) == 1536
            assert entry.profile_json["topic"] == "Recursion"
            assert entry.quiz_score == 0.8

    async def test_mismatched_student_rejected(self) -> None:
        ctx = await _seed_attempt()
        async with AsyncSessionLocal() as db:
            with pytest.raises(ValueError):
                await generate_profile_entry(99999, ctx["attempt_id"], db)

    async def test_unknown_attempt_rejected(self) -> None:
        async with AsyncSessionLocal() as db:
            with pytest.raises(ValueError):
                await generate_profile_entry(1, 99999, db)
