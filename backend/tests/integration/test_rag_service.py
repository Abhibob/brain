"""Integration tests for app.services.rag against the live DB."""

from __future__ import annotations

import pytest
from sqlalchemy import select

from app.db import AsyncSessionLocal
from app.models import (
    Class,
    Enrollment,
    Material,
    MaterialSection,
    PersonalizedLesson,
    StudentProfileEntry,
    User,
)
from app.services.rag import (
    embed_material_sections,
    embed_text,
    personalize_lesson,
    retrieve_profile_entries,
    retroactively_personalize,
)


async def _seed(published: bool = True) -> dict[str, int]:
    from datetime import UTC, datetime

    async with AsyncSessionLocal() as db:
        student = User(email="rag-s@example.com", hashed_password="x", role="student")
        educator = User(email="rag-e@example.com", hashed_password="x", role="educator")
        db.add_all([student, educator])
        await db.flush()
        cls = Class(educator_id=educator.id, title="RAG", enrollment_code="RAG12345")
        db.add(cls)
        await db.flush()
        db.add(Enrollment(class_id=cls.id, student_id=student.id))
        material = Material(
            class_id=cls.id,
            title="Recursion",
            type="lesson",
            published_at=datetime.now(UTC) if published else None,
        )
        db.add(material)
        await db.flush()
        db.add_all([
            MaterialSection(material_id=material.id, title="Base", content="stopping condition", order_index=0, word_count=2),
            MaterialSection(material_id=material.id, title="Step", content="reduce the problem", order_index=1, word_count=3),
        ])
        await db.commit()
        return {"student_id": student.id, "material_id": material.id, "class_id": cls.id, "educator_id": educator.id}


@pytest.mark.asyncio
class TestEmbedding:
    async def test_embed_text_returns_vector(self) -> None:
        vec = await embed_text("hello")
        assert len(vec) == 1536

    async def test_embed_material_sections_writes_to_db(self) -> None:
        ctx = await _seed()
        async with AsyncSessionLocal() as db:
            count = await embed_material_sections(ctx["material_id"], db)
            assert count == 2
            sections = (
                await db.scalars(select(MaterialSection).where(MaterialSection.material_id == ctx["material_id"]))
            ).all()
            assert all(s.embedding is not None and len(s.embedding) == 1536 for s in sections)


@pytest.mark.asyncio
class TestPersonalizeLesson:
    async def test_returns_none_without_profile(self) -> None:
        ctx = await _seed()
        async with AsyncSessionLocal() as db:
            lesson = await personalize_lesson(ctx["student_id"], ctx["material_id"], db)
            assert lesson is None

    async def test_returns_none_for_unpublished(self) -> None:
        ctx = await _seed(published=False)
        # create a profile so the short-circuit is truly because unpublished
        async with AsyncSessionLocal() as db:
            db.add(
                StudentProfileEntry(
                    user_id=ctx["student_id"],
                    profile_text="p",
                    profile_json={"topic": "x"},
                    embedding=await embed_text("p"),
                )
            )
            await db.commit()
            lesson = await personalize_lesson(ctx["student_id"], ctx["material_id"], db)
            assert lesson is None

    async def test_upsert_then_update(self) -> None:
        ctx = await _seed()
        async with AsyncSessionLocal() as db:
            db.add(
                StudentProfileEntry(
                    user_id=ctx["student_id"],
                    profile_text="needs visuals",
                    profile_json={"topic": "recursion"},
                    embedding=await embed_text("needs visuals"),
                )
            )
            await db.commit()
            first = await personalize_lesson(ctx["student_id"], ctx["material_id"], db)
            assert first is not None
            assert first.educator_id == ctx["educator_id"]

            second = await personalize_lesson(ctx["student_id"], ctx["material_id"], db)
            assert second is not None
            # same row
            assert second.id == first.id

            count = await db.scalar(
                select(PersonalizedLesson)
                .where(PersonalizedLesson.student_id == ctx["student_id"])
            )
            assert count is not None


@pytest.mark.asyncio
class TestRetrieveProfileEntries:
    async def test_returns_entries_sorted_by_relevance(self) -> None:
        ctx = await _seed()
        async with AsyncSessionLocal() as db:
            for text in ["base case stopping", "unrelated chat about music", "recursive steps"]:
                db.add(
                    StudentProfileEntry(
                        user_id=ctx["student_id"],
                        profile_text=text,
                        profile_json={"topic": text},
                        embedding=await embed_text(text),
                    )
                )
            await db.commit()
            results = await retrieve_profile_entries(ctx["student_id"], "recursion base case", db)
            assert len(results) == 3
            # most relevant should be first (either "base case stopping" or "recursive steps")
            assert results[0].profile_text in {"base case stopping", "recursive steps"}


@pytest.mark.asyncio
class TestRetroactivelyPersonalize:
    async def test_personalizes_all_enrolled_published(self) -> None:
        ctx = await _seed()
        async with AsyncSessionLocal() as db:
            db.add(
                StudentProfileEntry(
                    user_id=ctx["student_id"],
                    profile_text="slow reader",
                    profile_json={"topic": "x"},
                    embedding=await embed_text("slow reader"),
                )
            )
            await db.commit()
            count = await retroactively_personalize(ctx["student_id"], db)
            assert count == 1
