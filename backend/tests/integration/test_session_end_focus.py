from __future__ import annotations

import asyncio
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.db import AsyncSessionLocal
from app.models import (
    SectionFocusScore,
    TopicMasteryEdge,
    TopicMasteryNode,
    TrackingSession,
    UserLearningProfile,
)
from tests.conftest import (
    auth_headers,
    publish_material,
    run_tracked_session,
)


def test_session_end_computes_focus_and_updates_profile(
    client: TestClient,
    published_class: dict[str, Any],
    student: dict[str, Any],
) -> None:
    material = published_class["material"]
    section_ids = published_class["section_ids"]
    student_token = student["access_token"]

    body = run_tracked_session(client, student_token, material["id"], section_ids)

    assert body["focus"] is not None
    assert 0 <= body["focus"]["focus_score"] <= 1
    assert body["focus"]["label"] in {
        "focused", "engaged", "distracted", "skimming", "abandoned",
    }
    assert set(body["focus"]["breakdown"].keys()) == {"pace", "completion", "attention", "engagement"}
    assert body["section_focus"], "expected at least one section focus row"
    for row in body["section_focus"]:
        assert 0 <= row["focus_score"] <= 1
        assert row["label"] in {"focused", "skimmed", "distracted"}
        assert "time_s" in row["breakdown"]

    async def check_db() -> None:
        async with AsyncSessionLocal() as db:
            session = await db.scalar(select(TrackingSession).where(TrackingSession.student_id == student["user"]["id"]))
            assert session is not None
            assert session.focus_score is not None
            assert session.focus_label is not None
            rows = (
                await db.scalars(
                    select(SectionFocusScore).where(SectionFocusScore.session_id == session.id)
                )
            ).all()
            assert rows, "section_focus_scores should be persisted"
            profile = await db.scalar(
                select(UserLearningProfile).where(UserLearningProfile.user_id == student["user"]["id"])
            )
            assert profile is not None
            assert profile.session_count >= 1
            assert profile.rolling_focus_score is not None
            assert set(profile.style_vector.keys()) == {
                "pace",
                "depth",
                "attention_stability",
                "engagement_mode",
                "revisit_tendency",
                "visual_orientation",
                "motor_style",
            }
            nodes = (
                await db.scalars(
                    select(TopicMasteryNode).where(TopicMasteryNode.user_id == student["user"]["id"])
                )
            ).all()
            assert nodes, "topic_mastery_nodes should be created from session end"

    asyncio.run(check_db())


def test_two_sessions_build_topic_edges(
    client: TestClient,
    published_class: dict[str, Any],
    student: dict[str, Any],
    educator: dict[str, Any],
) -> None:
    material = published_class["material"]
    section_ids = published_class["section_ids"]
    student_token = student["access_token"]
    educator_token = educator["access_token"]

    cls_id = published_class["class"]["id"]
    response = client.post(
        f"/classes/{cls_id}/materials",
        json={
            "title": "Pythagorean Theorem",
            "type": "lesson",
            "sections": [
                {"title": "right triangles", "content": "foundations", "order_index": 0},
                {"title": "hypotenuse rule", "content": "ab squared", "order_index": 1},
            ],
        },
        headers=auth_headers(educator_token),
    )
    assert response.status_code == 200, response.text
    second_material = response.json()
    publish_material(client, educator_token, second_material["id"])

    run_tracked_session(client, student_token, material["id"], section_ids)
    run_tracked_session(
        client,
        student_token,
        second_material["id"],
        [section["id"] for section in second_material["sections"]],
    )

    async def check() -> None:
        async with AsyncSessionLocal() as db:
            nodes = (
                await db.scalars(
                    select(TopicMasteryNode).where(TopicMasteryNode.user_id == student["user"]["id"])
                )
            ).all()
            assert len({node.topic for node in nodes}) >= 2
            edges = (
                await db.scalars(
                    select(TopicMasteryEdge).where(TopicMasteryEdge.user_id == student["user"]["id"])
                )
            ).all()
            assert all(edge.relation == "co_occurred" for edge in edges)

    asyncio.run(check())
