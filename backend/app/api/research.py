from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import require_role
from app.db import get_db
from app.models import (
    Class,
    Enrollment,
    Material,
    PersonalizedLesson,
    ResearchNeuralModel,
    StudentProfileEntry,
    TribePrediction,
    User,
)
from app.services import research_nn, tribe
from app.services.rag import retrieve_profile_entries

router = APIRouter(prefix="/research", tags=["research"])


async def _require_student_in_class(db: AsyncSession, student_id: int, class_id: int | None = None) -> None:
    query = select(Enrollment.id).where(Enrollment.student_id == student_id)
    if class_id is not None:
        query = query.where(Enrollment.class_id == class_id)
    enrolled = await db.scalar(query.limit(1))
    if not enrolled:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student enrollment not found")


@router.get("/classes/{class_id}/workbench", response_model=dict)
async def get_research_workbench(
    class_id: int,
    _researcher: User = Depends(require_role("researcher")),
    db: AsyncSession = Depends(get_db),
) -> dict:
    class_ = await db.scalar(select(Class).where(Class.id == class_id))
    if class_ is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Class not found")

    student_rows = (
        await db.execute(
            select(User, func.count(StudentProfileEntry.id))
            .join(Enrollment, Enrollment.student_id == User.id)
            .outerjoin(StudentProfileEntry, StudentProfileEntry.user_id == User.id)
            .where(Enrollment.class_id == class_id)
            .group_by(User.id)
            .order_by(User.email)
        )
    ).all()
    materials = (
        await db.scalars(
            select(Material)
            .where(Material.class_id == class_id)
            .options(selectinload(Material.sections))
            .order_by(Material.order_index.asc(), Material.id.asc())
        )
    ).all()
    research_models = (
        await db.scalars(
            select(ResearchNeuralModel)
            .where(ResearchNeuralModel.class_id == class_id)
            .order_by(ResearchNeuralModel.trained_at.desc(), ResearchNeuralModel.id.desc())
        )
    ).all()
    latest_model_by_student: dict[int, ResearchNeuralModel] = {}
    for model in research_models:
        latest_model_by_student.setdefault(model.student_id, model)
    tribe_rows = (
        await db.scalars(
            select(TribePrediction)
            .join(Material, Material.id == TribePrediction.material_id)
            .where(Material.class_id == class_id)
            .order_by(TribePrediction.created_at.desc(), TribePrediction.id.desc())
        )
    ).all()
    latest_tribe_by_pair: dict[str, TribePrediction] = {}
    for row in tribe_rows:
        latest_tribe_by_pair.setdefault(f"{row.student_id}:{row.material_id}", row)

    return {
        "class": {
            "id": class_.id,
            "title": class_.title,
            "description": class_.description,
            "created_at": class_.created_at,
        },
        "students": [
            {
                "id": student.id,
                "email": student.email,
                "profile_entry_count": entry_count,
                "neural_model": (
                    {
                        "id": latest_model_by_student[student.id].id,
                        "status": latest_model_by_student[student.id].status,
                        "version": latest_model_by_student[student.id].version,
                        "sample_count": latest_model_by_student[student.id].sample_count,
                        "student_sample_count": latest_model_by_student[student.id].student_sample_count,
                        "confidence": latest_model_by_student[student.id].metrics.get("confidence"),
                    }
                    if student.id in latest_model_by_student
                    else None
                ),
            }
            for student, entry_count in student_rows
        ],
        "materials": [
            {
                "id": material.id,
                "title": material.title,
                "type": material.type,
                "published_at": material.published_at,
                "section_count": len(material.sections),
                "word_count": sum(section.word_count for section in material.sections),
            }
            for material in materials
        ],
        "tribe_predictions": [
            {
                "student_id": prediction.student_id,
                "material_id": prediction.material_id,
                "status": prediction.status,
                "model_version": prediction.model_version,
                "created_at": prediction.created_at,
                "completed_at": prediction.completed_at,
                "error": prediction.error,
            }
            for prediction in latest_tribe_by_pair.values()
        ],
    }


@router.post("/students/{student_id}/neural-surrogate/train", response_model=dict)
async def train_student_surrogate(
    student_id: int,
    class_id: int | None = None,
    _researcher: User = Depends(require_role("researcher")),
    db: AsyncSession = Depends(get_db),
) -> dict:
    await _require_student_in_class(db, student_id, class_id)
    try:
        model = await research_nn.train_personalized_surrogate(db, student_id=student_id, class_id=class_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return {
        "id": model.id,
        "version": model.version,
        "status": model.status,
        "sample_count": model.sample_count,
        "student_sample_count": model.student_sample_count,
        "metrics": model.metrics,
    }


@router.get("/students/{student_id}/mechanistic", response_model=dict)
async def get_student_mechanistic_view(
    student_id: int,
    class_id: int | None = None,
    _researcher: User = Depends(require_role("researcher")),
    db: AsyncSession = Depends(get_db),
) -> dict:
    await _require_student_in_class(db, student_id, class_id)
    try:
        return await research_nn.explain_surrogate(db, student_id=student_id, class_id=class_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.get("/materials/{material_id}/students/{student_id}/personalization-audit", response_model=dict)
async def get_personalization_audit(
    material_id: int,
    student_id: int,
    _researcher: User = Depends(require_role("researcher")),
    db: AsyncSession = Depends(get_db),
) -> dict:
    material = await db.scalar(
        select(Material)
        .where(Material.id == material_id)
        .options(selectinload(Material.sections), selectinload(Material.class_))
    )
    if material is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Material not found")
    await _require_student_in_class(db, student_id, material.class_id)
    personalized = await db.scalar(
        select(PersonalizedLesson).where(
            PersonalizedLesson.student_id == student_id,
            PersonalizedLesson.base_material_id == material_id,
        )
    )
    query_text = f"{material.title}\n" + "\n".join(section.content for section in material.sections)
    entries = await retrieve_profile_entries(student_id, query_text, db, top_k=8)
    return {
        "student_id": student_id,
        "material_id": material_id,
        "base_lesson": {
            "title": material.title,
            "sections": [
                {
                    "id": section.id,
                    "title": section.title,
                    "content": section.content,
                    "order_index": section.order_index,
                    "word_count": section.word_count,
                }
                for section in sorted(material.sections, key=lambda item: item.order_index)
            ],
        },
        "personalized": personalized is not None,
        "personalized_lesson": (
            {
                "id": personalized.id,
                "generated_content": personalized.generated_content,
                "prompt_used": personalized.prompt_used,
                "assigned_at": personalized.assigned_at,
            }
            if personalized
            else None
        ),
        "retrieved_profile_entries": [
            {
                "id": entry.id,
                "profile_text": entry.profile_text,
                "profile_json": entry.profile_json,
                "quiz_score": entry.quiz_score,
                "trigger_material_id": entry.trigger_material_id,
                "created_at": entry.created_at,
            }
            for entry in entries
        ],
    }

@router.get("/materials/{material_id}/students/{student_id}/tribe", response_model=dict)
async def get_tribe_prediction(
    material_id: int,
    student_id: int,
    _researcher: User = Depends(require_role("researcher")),
    db: AsyncSession = Depends(get_db),
) -> dict:
    material = await db.scalar(select(Material).where(Material.id == material_id))
    if material is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Material not found")
    await _require_student_in_class(db, student_id, material.class_id)
    prediction = await tribe.get_latest_prediction(db, student_id=student_id, material_id=material_id)
    return tribe.prediction_payload(prediction)


@router.post("/materials/{material_id}/students/{student_id}/tribe", response_model=dict)
async def run_tribe_prediction(
    material_id: int,
    student_id: int,
    _researcher: User = Depends(require_role("researcher")),
    db: AsyncSession = Depends(get_db),
) -> dict:
    try:
        prediction = await tribe.run_prediction(db, student_id=student_id, material_id=material_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return tribe.prediction_payload(prediction)
