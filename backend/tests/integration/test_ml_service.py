"""Integration tests for app.services.ml."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from app.db import AsyncSessionLocal
from app.models import (
    Class,
    Material,
    PredictionModel,
    QuizAttempt,
    ScorePrediction,
    TrackingSession,
    User,
)
from app.services.ml import drift_status, predict_for_session, train_model_for_class
from app.settings import get_settings
from tests.conftest import xgboost_required


async def _seed_class_with_student() -> dict[str, int]:
    async with AsyncSessionLocal() as db:
        student = User(email="ml-s@example.com", hashed_password="x", role="student")
        educator = User(email="ml-e@example.com", hashed_password="x", role="educator")
        db.add_all([student, educator])
        await db.flush()
        cls = Class(educator_id=educator.id, title="ML Class", enrollment_code="MLCLS000")
        db.add(cls)
        await db.flush()
        material = Material(class_id=cls.id, title="ML Lesson", type="lesson")
        db.add(material)
        await db.commit()
        return {"student_id": student.id, "educator_id": educator.id, "class_id": cls.id, "material_id": material.id}


async def _seed_samples(student_id: int, material_id: int, samples: int) -> None:
    now = datetime.now(UTC)
    async with AsyncSessionLocal() as db:
        for i in range(samples):
            features = {
                "total_time_s": 40 + i,
                "hover_count": 2 + (i % 5),
                "avg_hover_duration_ms": 700 + i,
                "scroll_depth_pct": 70 + (i % 20),
                "back_scroll_count": i % 5,
                "scroll_velocity_avg": 0.2,
                "mouse_velocity_avg": 0.1,
                "mouse_velocity_variance": 0.02,
                "idle_total_s": i % 8,
                "idle_count": i % 3,
                "text_selection_count": i % 4,
                "reading_speed_wpm": 150 + (i % 60),
                "section_completion_rate": 0.85 + (i % 10) / 100,
                "re_read_sections": ["1"] if i % 4 == 0 else [],
            }
            session = TrackingSession(
                student_id=student_id,
                material_id=material_id,
                started_at=now - timedelta(minutes=i + 2),
                ended_at=now - timedelta(minutes=i + 1),
                features=features,
            )
            db.add(session)
            await db.flush()
            db.add(
                QuizAttempt(
                    student_id=student_id,
                    material_id=material_id,
                    session_id=session.id,
                    answers={"x": "y"},
                    score=min(0.55 + (i % 10) / 25, 1.0),
                    max_score=1.0,
                )
            )
        await db.commit()


@pytest.mark.asyncio
class TestTrainModelForClass:
    async def test_returns_none_below_threshold(self) -> None:
        ctx = await _seed_class_with_student()
        await _seed_samples(ctx["student_id"], ctx["material_id"], samples=3)
        async with AsyncSessionLocal() as db:
            model = await train_model_for_class(ctx["class_id"], db)
            assert model is None

    @xgboost_required
    async def test_trains_when_threshold_met(self) -> None:
        ctx = await _seed_class_with_student()
        await _seed_samples(ctx["student_id"], ctx["material_id"], samples=get_settings().xgboost_min_samples)
        async with AsyncSessionLocal() as db:
            model = await train_model_for_class(ctx["class_id"], db)
            assert model is not None
            assert model.model_type == "xgboost"
            assert model.artifact is not None
            assert model.sample_count >= get_settings().xgboost_min_samples
            assert model.feature_importances

    @xgboost_required
    async def test_global_model_covers_null_class(self) -> None:
        ctx = await _seed_class_with_student()
        await _seed_samples(ctx["student_id"], ctx["material_id"], samples=get_settings().xgboost_min_samples)
        async with AsyncSessionLocal() as db:
            model = await train_model_for_class(None, db)
            assert model is not None
            assert model.class_id is None


@pytest.mark.asyncio
class TestPredictForSession:
    async def test_heuristic_when_no_model(self) -> None:
        ctx = await _seed_class_with_student()
        async with AsyncSessionLocal() as db:
            session = TrackingSession(
                student_id=ctx["student_id"],
                material_id=ctx["material_id"],
                features={"total_time_s": 60, "section_completion_rate": 1.0, "hover_count": 3},
            )
            db.add(session)
            await db.commit()
            await db.refresh(session)
            pred = await predict_for_session(session.id, db)
            assert pred.model_version == "heuristic-v1"
            assert 0.0 <= pred.predicted_score <= 1.0

    @xgboost_required
    async def test_uses_class_model_when_trained(self) -> None:
        ctx = await _seed_class_with_student()
        await _seed_samples(ctx["student_id"], ctx["material_id"], samples=get_settings().xgboost_min_samples)
        async with AsyncSessionLocal() as db:
            await train_model_for_class(ctx["class_id"], db)
            session = TrackingSession(
                student_id=ctx["student_id"],
                material_id=ctx["material_id"],
                features={"total_time_s": 40, "hover_count": 2, "section_completion_rate": 1.0},
            )
            db.add(session)
            await db.commit()
            await db.refresh(session)
            pred = await predict_for_session(session.id, db)
            assert pred.model_version.startswith("ml-")

    async def test_second_call_updates_existing_row(self) -> None:
        ctx = await _seed_class_with_student()
        async with AsyncSessionLocal() as db:
            session = TrackingSession(
                student_id=ctx["student_id"],
                material_id=ctx["material_id"],
                features={"total_time_s": 10},
            )
            db.add(session)
            await db.commit()
            await db.refresh(session)
            first = await predict_for_session(session.id, db)
            second = await predict_for_session(session.id, db)
            assert first.id == second.id
            count = len(
                (await db.scalars(select(ScorePrediction).where(ScorePrediction.session_id == session.id))).all()
            )
            assert count == 1


@pytest.mark.asyncio
class TestDriftStatus:
    async def test_no_model_reason(self) -> None:
        ctx = await _seed_class_with_student()
        async with AsyncSessionLocal() as db:
            status = await drift_status(ctx["class_id"], db)
            assert status["checked"] is False
            assert status["reason"] == "no_class_model"

    @xgboost_required
    async def test_insufficient_samples_reason(self) -> None:
        ctx = await _seed_class_with_student()
        await _seed_samples(ctx["student_id"], ctx["material_id"], samples=get_settings().xgboost_min_samples)
        async with AsyncSessionLocal() as db:
            await train_model_for_class(ctx["class_id"], db)
            status = await drift_status(ctx["class_id"], db)
            assert status["reason"] == "insufficient_recent_ml_predictions"
