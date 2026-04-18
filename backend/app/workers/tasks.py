from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Awaitable

from app.celery_app import celery_app
from app.db import AsyncSessionLocal
from app.services import ml, profile, rag, tracking


def run_async(coro: Awaitable[Any]) -> Any:
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)
    with ThreadPoolExecutor(max_workers=1) as executor:
        return executor.submit(lambda: asyncio.run(coro)).result()


@celery_app.task(name="tracking.extract_features_and_predict")
def extract_features_and_predict(session_id: int) -> dict[str, Any]:
    async def _run() -> dict[str, Any]:
        async with AsyncSessionLocal() as db:
            features = await tracking.persist_and_compute_features(session_id, db)
            prediction = await ml.predict_for_session(session_id, db)
            return {
                "features": features,
                "prediction": {
                    "predicted_score": prediction.predicted_score,
                    "confidence": prediction.confidence,
                    "model_version": prediction.model_version,
                },
            }

    return run_async(_run())


@celery_app.task(name="profile.add_student_profile_entry")
def add_student_profile_entry(student_id: int, quiz_attempt_id: int) -> dict[str, Any]:
    async def _run() -> dict[str, Any]:
        async with AsyncSessionLocal() as db:
            entry = await profile.generate_profile_entry(student_id, quiz_attempt_id, db)
            personalized_count = await rag.retroactively_personalize(student_id, db)
            return {"entry_id": entry.id, "retroactive_personalized_lessons": personalized_count}

    return run_async(_run())


@celery_app.task(name="rag.embed_material_sections")
def embed_material_sections(material_id: int) -> dict[str, int]:
    async def _run() -> dict[str, int]:
        async with AsyncSessionLocal() as db:
            count = await rag.embed_material_sections(material_id, db)
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
