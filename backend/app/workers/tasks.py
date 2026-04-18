from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Awaitable

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.celery_app import celery_app
from app.db import AsyncSessionLocal
from app.models import LessonPlanDraft, Material, SectionFocusScore, StudentProfileEntry, TrackingSession
from app.services import (
    learning_profile,
    lesson_studio,
    ml,
    profile,
    profile_reasoning,
    rag,
    topics,
    tracking,
)
from app.services.rag import embed_text


def run_async(coro: Awaitable[Any]) -> Any:
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)
    with ThreadPoolExecutor(max_workers=1) as executor:
        return executor.submit(lambda: asyncio.run(coro)).result()


def _lesson_focus_profile_text(material: Material, focus: dict[str, Any], reasoning: dict[str, Any]) -> str:
    return (
        f"Session focus for '{material.title}': score {focus.get('focus_score')} "
        f"({focus.get('label')}). {reasoning.get('style_narrative', '')}"
    )


async def _run_session_end_pipeline(session_id: int) -> dict[str, Any]:
    async with AsyncSessionLocal() as db:
        features = await tracking.persist_and_compute_features(session_id, db)
        prediction = await ml.predict_for_session(session_id, db)

        session = await db.scalar(
            select(TrackingSession)
            .where(TrackingSession.id == session_id)
            .options(selectinload(TrackingSession.material).selectinload(Material.sections))
        )
        focus = {
            "focus_score": session.focus_score if session else None,
            "breakdown": session.focus_breakdown if session else None,
            "label": session.focus_label if session else None,
        }
        section_rows = (
            await db.scalars(
                select(SectionFocusScore).where(SectionFocusScore.session_id == session_id)
            )
        ).all()
        section_focus = [
            {
                "section_id": row.section_id,
                "focus_score": row.focus_score,
                "breakdown": row.breakdown,
                "label": row.label,
            }
            for row in section_rows
        ]
        if session is None or session.material is None:
            return {
                "features": features,
                "focus": focus,
                "prediction": {
                    "predicted_score": prediction.predicted_score,
                    "confidence": prediction.confidence,
                    "model_version": prediction.model_version,
                },
            }
        material = session.material

        material_topics = await topics.extract_topics_for_material(material.id, db)
        await learning_profile.upsert_from_session(db, session, features, focus, material_topics)
        snapshot = await learning_profile.get_profile_snapshot(session.student_id, db)

        lesson_info = {
            "material_id": material.id,
            "title": material.title,
            "type": material.type,
            "topics": material_topics,
            "sections": [
                {"id": s.id, "title": s.title, "word_count": s.word_count, "order_index": s.order_index}
                for s in sorted(material.sections, key=lambda item: item.order_index)
            ],
        }
        reasoning = await profile_reasoning.reason_about_session(lesson_info, focus, section_focus, snapshot)
        await learning_profile.apply_style_delta(db, session.student_id, reasoning)

        entry_json: dict[str, Any] = {
            "kind": "lesson_session",
            "topic": material.title,
            "topics": material_topics,
            "focus": focus,
            "section_focus": section_focus,
            "style_narrative": reasoning.get("style_narrative"),
            "content_preferences": reasoning.get("content_preferences"),
            "lesson_plan_hints": reasoning.get("lesson_plan_hints"),
            "per_topic_insights": reasoning.get("per_topic_insights"),
        }
        entry_text = _lesson_focus_profile_text(material, focus, reasoning)
        entry = StudentProfileEntry(
            user_id=session.student_id,
            profile_text=entry_text,
            profile_json=entry_json,
            embedding=await embed_text(entry_text),
            trigger_material_id=material.id,
            quiz_attempt_id=None,
            quiz_score=None,
        )
        db.add(entry)
        await db.commit()

        return {
            "features": features,
            "focus": focus,
            "section_focus": section_focus,
            "prediction": {
                "predicted_score": prediction.predicted_score,
                "confidence": prediction.confidence,
                "model_version": prediction.model_version,
            },
            "learning_profile_updated": True,
            "session_entry_id": entry.id,
        }


@celery_app.task(name="tracking.extract_features_and_predict")
def extract_features_and_predict(session_id: int) -> dict[str, Any]:
    return run_async(_run_session_end_pipeline(session_id))


async def _run_profile_entry_pipeline(student_id: int, quiz_attempt_id: int) -> dict[str, Any]:
    async with AsyncSessionLocal() as db:
        entry = await profile.generate_profile_entry(student_id, quiz_attempt_id, db)
        if entry.trigger_material_id is not None:
            material_topics = await topics.extract_topics_for_material(entry.trigger_material_id, db)
        else:
            material_topics = []
        await learning_profile.upsert_from_quiz_entry(db, entry, material_topics)
        await db.commit()
        personalized_count = await rag.retroactively_personalize(student_id, db)
        return {
            "entry_id": entry.id,
            "retroactive_personalized_lessons": personalized_count,
            "topics": material_topics,
        }


@celery_app.task(name="profile.add_student_profile_entry")
def add_student_profile_entry(student_id: int, quiz_attempt_id: int) -> dict[str, Any]:
    return run_async(_run_profile_entry_pipeline(student_id, quiz_attempt_id))


@celery_app.task(name="rag.embed_material_sections")
def embed_material_sections(material_id: int) -> dict[str, int]:
    async def _run() -> dict[str, int]:
        async with AsyncSessionLocal() as db:
            count = await rag.embed_material_sections(material_id, db)
            await topics.extract_topics_for_material(material_id, db)
            return {"embedded_sections": count}

    return run_async(_run())


@celery_app.task(name="rag.personalize_lesson_for_student")
def personalize_lesson_for_student(student_id: int, material_id: int) -> dict[str, Any]:
    async def _run() -> dict[str, Any]:
        async with AsyncSessionLocal() as db:
            lesson = await rag.personalize_lesson(student_id, material_id, db)
            return {"personalized_lesson_id": lesson.id if lesson else None}

    return run_async(_run())


@celery_app.task(name="ml.train_model_for_class")
def train_model_for_class(class_id: int) -> dict[str, Any]:
    async def _run() -> dict[str, Any]:
        async with AsyncSessionLocal() as db:
            model = await ml.train_model_for_class(class_id, db)
            return {
                "model_id": model.id if model else None,
                "model_type": model.model_type if model else None,
                "sample_count": model.sample_count if model else 0,
            }

    return run_async(_run())


@celery_app.task(name="lesson_studio.generate_candidates")
def studio_generate_candidates(draft_id: int) -> dict[str, Any]:
    async def _run() -> dict[str, Any]:
        async with AsyncSessionLocal() as db:
            draft = await db.scalar(select(LessonPlanDraft).where(LessonPlanDraft.id == draft_id))
            if draft is None:
                return {"draft_id": draft_id, "candidate_count": 0}
            candidates = await lesson_studio.generate_candidates(db, draft)
            await lesson_studio.propose_sequence(db, draft, candidates)
            return {"draft_id": draft_id, "candidate_count": len(candidates), "status": draft.status}

    return run_async(_run())


@celery_app.task(name="ml.train_global_model")
def train_global_model() -> dict[str, Any]:
    async def _run() -> dict[str, Any]:
        async with AsyncSessionLocal() as db:
            model = await ml.train_model_for_class(None, db)
            return {
                "model_id": model.id if model else None,
                "model_type": model.model_type if model else None,
                "sample_count": model.sample_count if model else 0,
            }

    return run_async(_run())
