"""Integration tests for app.services.learning_profile (DB-backed)."""

from __future__ import annotations

import asyncio

from sqlalchemy import select

from app.db import AsyncSessionLocal
from app.models import (
    StudentProfileEntry,
    TopicMasteryEdge,
    TopicMasteryNode,
    TrackingSession,
    User,
    UserLearningProfile,
)
from app.services.learning_profile import (
    STYLE_AXES,
    apply_style_delta,
    get_or_create_profile,
    get_profile_snapshot,
    upsert_from_quiz_entry,
    upsert_from_session,
)


async def _make_student() -> int:
    async with AsyncSessionLocal() as db:
        user = User(email="lp-student@ex.com", hashed_password="x", role="student")
        db.add(user)
        await db.commit()
        return user.id


def _focus(label: str = "focused", score: float = 0.85) -> dict:
    return {
        "focus_score": score,
        "confidence": 0.7,
        "breakdown": {"pace": 0.8, "completion": 0.9, "attention": 0.8, "engagement": 0.7},
        "label": label,
    }


class TestGetOrCreateProfile:
    def test_creates_with_defaults(self) -> None:
        user_id = asyncio.run(_make_student())

        async def run() -> None:
            async with AsyncSessionLocal() as db:
                profile = await get_or_create_profile(user_id, db)
                await db.commit()
                assert profile.user_id == user_id
                assert set(profile.style_vector.keys()) == set(STYLE_AXES)
                assert profile.session_count == 0

        asyncio.run(run())

    def test_returns_existing_on_second_call(self) -> None:
        user_id = asyncio.run(_make_student())

        async def run() -> None:
            async with AsyncSessionLocal() as db:
                first = await get_or_create_profile(user_id, db)
                await db.commit()
                second = await get_or_create_profile(user_id, db)
                assert first.id == second.id
                count = len((await db.scalars(select(UserLearningProfile).where(UserLearningProfile.user_id == user_id))).all())
                assert count == 1

        asyncio.run(run())


class TestUpsertFromSession:
    def test_applies_ema_and_topic_nodes(self) -> None:
        user_id = asyncio.run(_make_student())

        async def run() -> None:
            async with AsyncSessionLocal() as db:
                session = TrackingSession(student_id=user_id, material_id=None) if False else None
                # Build a fake session without material FK - use DB-backed to keep relationships valid.
                fake_session = TrackingSession(student_id=user_id, material_id=0)
                db.add(fake_session)
                await db.flush()
                features = {
                    "reading_speed_wpm": 200,
                    "section_completion_rate": 0.9,
                    "total_time_s": 180,
                    "hover_count": 5,
                    "idle_total_s": 10,
                    "text_selection_count": 1,
                    "re_read_sections": ["1"],
                    "back_scroll_count": 2,
                    "mouse_velocity_variance": 10,
                }
                profile = await upsert_from_session(db, fake_session, features, _focus(), ["pythag", "triangles"])
                await db.commit()
                assert profile.session_count == 1
                assert profile.rolling_focus_score > 0
                assert profile.last_focus_label == "focused"
                nodes = (await db.scalars(select(TopicMasteryNode).where(TopicMasteryNode.user_id == user_id))).all()
                assert {n.topic for n in nodes} == {"pythag", "triangles"}
                edges = (await db.scalars(select(TopicMasteryEdge).where(TopicMasteryEdge.user_id == user_id))).all()
                assert any(e.from_topic == "pythag" and e.to_topic == "triangles" for e in edges)

        asyncio.run(run())

    def test_second_session_increments_counts_and_weight(self) -> None:
        user_id = asyncio.run(_make_student())

        async def run() -> None:
            async with AsyncSessionLocal() as db:
                fake_session = TrackingSession(student_id=user_id, material_id=0)
                db.add(fake_session)
                await db.flush()
                features = {"reading_speed_wpm": 180, "section_completion_rate": 0.8, "total_time_s": 120}
                await upsert_from_session(db, fake_session, features, _focus(), ["pythag", "triangles"])
                await upsert_from_session(db, fake_session, features, _focus(score=0.5), ["pythag", "triangles"])
                await db.commit()
                profile = await db.scalar(select(UserLearningProfile).where(UserLearningProfile.user_id == user_id))
                assert profile.session_count == 2
                edge = await db.scalar(
                    select(TopicMasteryEdge).where(
                        TopicMasteryEdge.user_id == user_id,
                        TopicMasteryEdge.from_topic == "pythag",
                    )
                )
                assert edge.weight >= 2.0

        asyncio.run(run())


class TestUpsertFromQuizEntry:
    def test_updates_mastery_and_struggle(self) -> None:
        user_id = asyncio.run(_make_student())

        async def run() -> None:
            async with AsyncSessionLocal() as db:
                entry = StudentProfileEntry(
                    user_id=user_id,
                    profile_text="",
                    profile_json={},
                    embedding=None,
                    trigger_material_id=None,
                    quiz_attempt_id=None,
                    quiz_score=0.4,
                )
                db.add(entry)
                await db.flush()
                profile = await upsert_from_quiz_entry(db, entry, ["arrays"])
                await db.commit()
                assert profile.quiz_count == 1
                node = await db.scalar(select(TopicMasteryNode).where(TopicMasteryNode.user_id == user_id, TopicMasteryNode.topic == "arrays"))
                assert node is not None
                assert node.quiz_sample_count == 1
                assert node.struggle_signal > 0


        asyncio.run(run())


class TestApplyStyleDelta:
    def test_merges_delta_and_hints(self) -> None:
        user_id = asyncio.run(_make_student())

        async def run() -> None:
            async with AsyncSessionLocal() as db:
                delta = {
                    "style_vector_delta": {"pace": 0.1, "attention_stability": -0.05},
                    "style_narrative": "Good focus on examples.",
                    "content_preferences": {"prefers_examples": True},
                    "lesson_plan_hints": ["use short passages"],
                }
                profile = await apply_style_delta(db, user_id, delta)
                await db.commit()
                assert profile.style_vector["pace"] > 0.5
                assert profile.behavioral_signals["narrative_notes"]
                assert profile.behavioral_signals["content_preferences"]["prefers_examples"] >= 0.5
                assert "use short passages" in profile.behavioral_signals["recent_hints"]

        asyncio.run(run())


class TestGetProfileSnapshot:
    def test_returns_defaults_for_unknown_student(self) -> None:
        async def run() -> None:
            async with AsyncSessionLocal() as db:
                snap = await get_profile_snapshot(999999, db)
                assert snap["rolling_focus_score"] == 0.5
                assert snap["top_mastery"] == []

        asyncio.run(run())

    def test_returns_top_mastery_after_sessions(self) -> None:
        user_id = asyncio.run(_make_student())

        async def run() -> None:
            async with AsyncSessionLocal() as db:
                fake_session = TrackingSession(student_id=user_id, material_id=0)
                db.add(fake_session)
                await db.flush()
                features = {"reading_speed_wpm": 180, "section_completion_rate": 0.9, "total_time_s": 120}
                await upsert_from_session(db, fake_session, features, _focus(), ["topic_a"])
                await db.commit()
                snap = await get_profile_snapshot(user_id, db)
                assert snap["top_mastery"]
                assert snap["session_count"] == 1

        asyncio.run(run())
