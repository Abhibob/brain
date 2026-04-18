"""Integration tests for app.services.topics (idempotency + persistence)."""

from __future__ import annotations

import asyncio

from sqlalchemy import select

from app.db import AsyncSessionLocal
from app.models import Class, Material, MaterialSection, MaterialTopic, User
from app.services.topics import extract_topics_for_material, topics_for_materials


async def _seed_material(title: str = "Pythagorean Theorem Basics") -> int:
    async with AsyncSessionLocal() as db:
        educator = User(email=f"topics-ed-{title.replace(' ', '-')}@ex.com", hashed_password="x", role="educator")
        db.add(educator)
        await db.flush()
        cls = Class(educator_id=educator.id, title="C", enrollment_code=f"TO-{title[:4]}")
        db.add(cls)
        await db.flush()
        material = Material(class_id=cls.id, title=title, type="lesson")
        db.add(material)
        await db.flush()
        db.add_all([
            MaterialSection(material_id=material.id, title="Right triangles", content="x" * 40, order_index=0, word_count=3),
            MaterialSection(material_id=material.id, title="The hypotenuse rule", content="y" * 40, order_index=1, word_count=3),
        ])
        await db.commit()
        return material.id


class TestExtractTopicsForMaterial:
    def test_creates_rows_on_first_call(self) -> None:
        mid = asyncio.run(_seed_material())

        async def run() -> None:
            async with AsyncSessionLocal() as db:
                topics = await extract_topics_for_material(mid, db)
                assert topics, "expected at least one topic"
                rows = (await db.scalars(select(MaterialTopic).where(MaterialTopic.material_id == mid))).all()
                assert len(rows) == len(topics)

        asyncio.run(run())

    def test_idempotent_on_repeated_call(self) -> None:
        mid = asyncio.run(_seed_material("Introduction to Graphs"))

        async def run() -> None:
            async with AsyncSessionLocal() as db:
                first = await extract_topics_for_material(mid, db)
                second = await extract_topics_for_material(mid, db)
                assert first == second
                rows = (await db.scalars(select(MaterialTopic).where(MaterialTopic.material_id == mid))).all()
                assert len(rows) == len(first)

        asyncio.run(run())

    def test_unknown_material_returns_empty(self) -> None:
        async def run() -> None:
            async with AsyncSessionLocal() as db:
                assert await extract_topics_for_material(99999, db) == []

        asyncio.run(run())


class TestTopicsForMaterials:
    def test_returns_mapping_for_multiple(self) -> None:
        mid = asyncio.run(_seed_material("Trees and Graphs"))

        async def run() -> None:
            async with AsyncSessionLocal() as db:
                await extract_topics_for_material(mid, db)
                result = await topics_for_materials([mid, mid + 999], db)
                assert mid in result
                assert result[mid]
                assert result[mid + 999] == []

        asyncio.run(run())

    def test_empty_input_returns_empty(self) -> None:
        async def run() -> None:
            async with AsyncSessionLocal() as db:
                assert await topics_for_materials([], db) == {}

        asyncio.run(run())
