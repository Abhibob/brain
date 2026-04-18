"""Integration tests for app.services.tracking against the live DB + Redis."""

from __future__ import annotations

import asyncio
import json

import pytest
from redis.asyncio import Redis
from sqlalchemy import select

from app.db import AsyncSessionLocal
from app.models import TrackingEvent, TrackingSession, User, Material, Class, Enrollment
from app.services.tracking import drain_buffered_events, ingest_event, persist_and_compute_features
from app.settings import get_settings


async def _redis() -> Redis:
    return Redis.from_url(get_settings().redis_url, decode_responses=True)


@pytest.mark.asyncio
class TestIngestAndDrain:
    async def test_ingest_round_trip(self) -> None:
        redis = await _redis()
        try:
            await ingest_event(redis, 4242, "mouse_move", {"velocity": 0.4}, 1_700_000_000_000)
            events = await drain_buffered_events(redis, 4242)
            assert len(events) == 1
            assert events[0]["event_type"] == "mouse_move"
            assert events[0]["event_data"] == {"velocity": 0.4}
        finally:
            await redis.aclose()

    async def test_drain_clears_key(self) -> None:
        redis = await _redis()
        try:
            await ingest_event(redis, 99, "scroll", {"position": 10}, 1)
            await drain_buffered_events(redis, 99)
            assert await redis.llen("tracking:99") == 0
        finally:
            await redis.aclose()


async def _seed_session(dialect_hint: str = "") -> tuple[int, list[int]]:
    from datetime import UTC, datetime

    async with AsyncSessionLocal() as db:
        user = User(email="int-student@example.com", hashed_password="x", role="student")
        educator = User(email="int-ed@example.com", hashed_password="x", role="educator")
        db.add_all([user, educator])
        await db.flush()
        cls = Class(educator_id=educator.id, title="Integ", enrollment_code="INTEG123")
        db.add(cls)
        await db.flush()
        enrollment = Enrollment(class_id=cls.id, student_id=user.id)
        db.add(enrollment)
        material = Material(class_id=cls.id, title="Integ lesson", type="lesson")
        db.add(material)
        await db.flush()
        from app.models import MaterialSection
        sections = [
            MaterialSection(material_id=material.id, title="A", content="hello world", order_index=0, word_count=2),
            MaterialSection(material_id=material.id, title="B", content="another section", order_index=1, word_count=2),
        ]
        db.add_all(sections)
        # Explicit aware started_at avoids tz mismatch on SQLite where func.now() returns naive.
        session = TrackingSession(
            student_id=user.id,
            material_id=material.id,
            started_at=datetime.now(UTC),
        )
        db.add(session)
        await db.commit()
        await db.refresh(session)
        return session.id, [s.id for s in sections]


@pytest.mark.asyncio
class TestPersistAndCompute:
    async def test_persists_events_and_features(self) -> None:
        session_id, section_ids = await _seed_session()
        redis = await _redis()
        try:
            for i in range(3):
                await ingest_event(
                    redis,
                    session_id,
                    "section_view",
                    {"section_id": str(section_ids[0])},
                    1_700_000_000_000 + i,
                )
            await ingest_event(redis, session_id, "hover_end", {"duration_ms": 500}, 1_700_000_000_100)
        finally:
            await redis.aclose()

        async with AsyncSessionLocal() as db:
            features = await persist_and_compute_features(session_id, db)
            assert features["hover_count"] == 1
            stored = (await db.scalars(select(TrackingEvent).where(TrackingEvent.session_id == session_id))).all()
            assert len(stored) == 4

    async def test_unknown_session_raises(self) -> None:
        async with AsyncSessionLocal() as db:
            with pytest.raises(ValueError):
                await persist_and_compute_features(99999, db)
