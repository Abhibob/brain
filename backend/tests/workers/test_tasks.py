"""Direct tests for Celery task entry points in app.workers.tasks.

These exercise the thin task wrappers. Heavier end-to-end coverage lives in the
integration tests — these just ensure each task can be invoked eagerly and
returns the documented payload shape.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from typing import Any

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
from app.settings import get_settings
from app.workers import tasks


async def _basic_setup() -> dict[str, int]:
    async with AsyncSessionLocal() as db:
        student = User(email="w-s@example.com", hashed_password="x", role="student")
        educator = User(email="w-e@example.com", hashed_password="x", role="educator")
        db.add_all([student, educator])
        await db.flush()
        cls = Class(educator_id=educator.id, title="W", enrollment_code="WCLS1234")
        db.add(cls)
        await db.flush()
        db.add(Enrollment(class_id=cls.id, student_id=student.id))
        material = Material(class_id=cls.id, title="W Lesson", type="lesson", published_at=datetime.now(UTC))
        db.add(material)
        await db.flush()
        db.add_all([
            MaterialSection(material_id=material.id, title="A", content="hello world", order_index=0, word_count=2),
            MaterialSection(material_id=material.id, title="B", content="goodbye world", order_index=1, word_count=2),
        ])
        session = TrackingSession(
            student_id=student.id,
            material_id=material.id,
            started_at=datetime.now(UTC) - timedelta(seconds=30),
            ended_at=datetime.now(UTC),
            features={"section_completion_rate": 1.0, "reading_speed_wpm": 200, "hover_count": 2, "total_time_s": 30},
        )
        db.add(session)
        await db.flush()
        attempt = QuizAttempt(
            student_id=student.id,
            material_id=material.id,
            session_id=session.id,
            answers={"1": "A"},
            score=3,
            max_score=5,
        )
        db.add(attempt)
        await db.commit()
        return {
            "student_id": student.id,
            "educator_id": educator.id,
            "class_id": cls.id,
            "material_id": material.id,
            "session_id": session.id,
            "attempt_id": attempt.id,
        }


class TestRunAsync:
    def test_run_async_outside_loop(self) -> None:
        async def coro() -> int:
            return 42

        assert tasks.run_async(coro()) == 42


class TestExtractFeaturesAndPredict:
    def test_returns_features_and_prediction(self) -> None:
        ctx = asyncio.run(_basic_setup())
        result = tasks.extract_features_and_predict.delay(ctx["session_id"]).result
        assert "features" in result
        assert "prediction" in result
        assert result["prediction"]["model_version"]

    def test_unknown_session_propagates(self) -> None:
        with pytest.raises(Exception):
            tasks.extract_features_and_predict.delay(99999).result


class TestAddStudentProfileEntry:
    def test_creates_entry_and_personalizes(self) -> None:
        ctx = asyncio.run(_basic_setup())
        # ensure section embeddings exist for personalization
        tasks.embed_material_sections.delay(ctx["material_id"]).result
        result = tasks.add_student_profile_entry.delay(ctx["student_id"], ctx["attempt_id"]).result
        assert result["entry_id"]
        assert result["retroactive_personalized_lessons"] >= 1

        async def _count() -> int:
            async with AsyncSessionLocal() as db:
                return (
                    await db.scalar(
                        select(StudentProfileEntry).where(StudentProfileEntry.user_id == ctx["student_id"])
                    )
                ).id

        assert asyncio.run(_count())


class TestEmbedMaterialSections:
    def test_embeds_each_section(self) -> None:
        ctx = asyncio.run(_basic_setup())
        result = tasks.embed_material_sections.delay(ctx["material_id"]).result
        assert result["embedded_sections"] == 2


class TestPersonalizeLessonForStudent:
    def test_returns_none_without_profile(self) -> None:
        ctx = asyncio.run(_basic_setup())
        result = tasks.personalize_lesson_for_student.delay(ctx["student_id"], ctx["material_id"]).result
        assert result["personalized_lesson_id"] is None


class TestTrainModelForClass:
    def test_returns_zero_samples_when_below_threshold(self) -> None:
        ctx = asyncio.run(_basic_setup())
        result = tasks.train_model_for_class.delay(ctx["class_id"]).result
        assert result["sample_count"] == 0
        assert result["model_id"] is None

    def test_trains_when_threshold_met(self) -> None:
        from tests.conftest import _XGBOOST_AVAILABLE
        if not _XGBOOST_AVAILABLE:
            pytest.skip("xgboost library failed to load (likely missing libomp).")
        ctx = asyncio.run(_basic_setup())
        # seed enough samples
        async def _seed() -> None:
            async with AsyncSessionLocal() as db:
                for i in range(get_settings().xgboost_min_samples):
                    session = TrackingSession(
                        student_id=ctx["student_id"],
                        material_id=ctx["material_id"],
                        started_at=datetime.now(UTC) - timedelta(minutes=i + 2),
                        ended_at=datetime.now(UTC) - timedelta(minutes=i + 1),
                        features={
                            "total_time_s": 30 + i,
                            "hover_count": 2,
                            "section_completion_rate": 0.9,
                            "reading_speed_wpm": 180,
                        },
                    )
                    db.add(session)
                    await db.flush()
                    db.add(
                        QuizAttempt(
                            student_id=ctx["student_id"],
                            material_id=ctx["material_id"],
                            session_id=session.id,
                            answers={"x": "y"},
                            score=0.75,
                            max_score=1.0,
                        )
                    )
                await db.commit()

        asyncio.run(_seed())
        result = tasks.train_model_for_class.delay(ctx["class_id"]).result
        assert result["model_type"] == "xgboost"
        assert result["sample_count"] >= get_settings().xgboost_min_samples


class TestTrainGlobalModel:
    def test_returns_zero_when_empty(self) -> None:
        result = tasks.train_global_model.delay().result
        assert result["sample_count"] == 0
