from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_current_user, require_role
from app.db import get_db
from app.models import Class, Enrollment, Material, MaterialSection, PersonalizedLesson, QuizQuestion, User
from app.schemas import MaterialCreate, MaterialOut, MaterialUpdate, PublishOut, QuizQuestionCreate, QuizQuestionPublic, SectionOut
from app.workers import tasks

router = APIRouter(tags=["materials"])


def _word_count(text: str) -> int:
    return len([word for word in text.replace("\n", " ").split(" ") if word.strip()])


def _section_out(section: MaterialSection) -> SectionOut:
    return SectionOut(id=section.id, title=section.title, content=section.content, order_index=section.order_index, word_count=section.word_count)


async def _replace_sections(db: AsyncSession, material: Material, sections: list) -> None:
    await db.execute(delete(MaterialSection).where(MaterialSection.material_id == material.id))
    await db.flush()
    for idx, section in enumerate(sections):
        db.add(
            MaterialSection(
                material_id=material.id,
                title=section.title,
                content=section.content,
                order_index=section.order_index if section.order_index is not None else idx,
                word_count=_word_count(section.content),
            )
        )


async def _run_publish_personalization(db: AsyncSession, material: Material) -> int:
    tasks.embed_material_sections.delay(material.id)
    student_ids = (await db.scalars(select(Enrollment.student_id).where(Enrollment.class_id == material.class_id))).all()
    for student_id in student_ids:
        tasks.personalize_lesson_for_student.delay(student_id, material.id)
    return len(student_ids)


async def _load_material(db: AsyncSession, material_id: int) -> Material:
    material = await db.scalar(
        select(Material)
        .where(Material.id == material_id)
        .options(selectinload(Material.sections), selectinload(Material.questions), selectinload(Material.class_))
    )
    if material is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Material not found")
    return material


async def _can_access_material(db: AsyncSession, user: User, material: Material) -> bool:
    if user.role == "researcher":
        return True
    if user.role == "educator":
        return material.class_.educator_id == user.id
    return bool(await db.scalar(select(Enrollment.id).where(Enrollment.class_id == material.class_id, Enrollment.student_id == user.id)))


@router.post("/classes/{class_id}/materials", response_model=MaterialOut)
async def create_material(
    class_id: int,
    payload: MaterialCreate,
    current_user: User = Depends(require_role("educator")),
    db: AsyncSession = Depends(get_db),
) -> MaterialOut:
    class_ = await db.scalar(select(Class).where(Class.id == class_id, Class.educator_id == current_user.id))
    if class_ is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Class not found")
    material = Material(class_id=class_id, title=payload.title, type=payload.type, order_index=payload.order_index)
    db.add(material)
    await db.flush()
    await _replace_sections(db, material, payload.sections)
    await db.commit()
    material = await _load_material(db, material.id)
    return MaterialOut(
        id=material.id,
        class_id=material.class_id,
        title=material.title,
        type=material.type,
        order_index=material.order_index,
        published_at=material.published_at,
        sections=[_section_out(section) for section in material.sections],
    )


@router.put("/materials/{material_id}/publish", response_model=PublishOut)
async def publish_material(
    material_id: int,
    current_user: User = Depends(require_role("educator")),
    db: AsyncSession = Depends(get_db),
) -> PublishOut:
    material = await _load_material(db, material_id)
    if material.class_.educator_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Material access denied")
    material.published_at = datetime.now(UTC)
    await db.commit()
    task_count = await _run_publish_personalization(db, material)
    await db.refresh(material)
    return PublishOut(material_id=material.id, published_at=material.published_at, personalization_tasks=task_count)


@router.put("/materials/{material_id}", response_model=MaterialOut)
async def update_material(
    material_id: int,
    payload: MaterialUpdate,
    current_user: User = Depends(require_role("educator")),
    db: AsyncSession = Depends(get_db),
) -> MaterialOut:
    material = await _load_material(db, material_id)
    if material.class_.educator_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Material access denied")
    if payload.title is not None:
        material.title = payload.title
    if payload.type is not None:
        material.type = payload.type
    if payload.order_index is not None:
        material.order_index = payload.order_index
    if payload.sections is not None:
        await _replace_sections(db, material, payload.sections)
        await db.execute(delete(PersonalizedLesson).where(PersonalizedLesson.base_material_id == material.id))
    await db.commit()
    if material.published_at is not None:
        await _run_publish_personalization(db, material)
    material = await _load_material(db, material.id)
    return MaterialOut(
        id=material.id,
        class_id=material.class_id,
        title=material.title,
        type=material.type,
        order_index=material.order_index,
        published_at=material.published_at,
        sections=[_section_out(section) for section in material.sections],
    )


@router.delete("/materials/{material_id}", response_model=dict)
async def delete_material(
    material_id: int,
    current_user: User = Depends(require_role("educator")),
    db: AsyncSession = Depends(get_db),
) -> dict:
    material = await _load_material(db, material_id)
    if material.class_.educator_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Material access denied")
    await db.delete(material)
    await db.commit()
    return {"status": "deleted", "material_id": material_id}


@router.get("/materials/{material_id}", response_model=MaterialOut)
async def get_material(
    material_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MaterialOut:
    material = await _load_material(db, material_id)
    if not await _can_access_material(db, current_user, material):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Material access denied")

    personalized: PersonalizedLesson | None = None
    if current_user.role == "student":
        personalized = await db.scalar(
            select(PersonalizedLesson).where(
                PersonalizedLesson.student_id == current_user.id,
                PersonalizedLesson.base_material_id == material.id,
            )
        )

    return MaterialOut(
        id=material.id,
        class_id=material.class_id,
        title=material.title,
        type=material.type,
        order_index=material.order_index,
        published_at=material.published_at,
        personalized=personalized is not None,
        generated_content=personalized.generated_content if personalized else None,
        sections=[_section_out(section) for section in material.sections],
    )


@router.post("/materials/{material_id}/quiz", response_model=list[QuizQuestionPublic])
async def create_quiz(
    material_id: int,
    questions: list[QuizQuestionCreate],
    current_user: User = Depends(require_role("educator")),
    db: AsyncSession = Depends(get_db),
) -> list[QuizQuestionPublic]:
    material = await _load_material(db, material_id)
    if material.class_.educator_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Material access denied")
    created: list[QuizQuestion] = []
    for question in questions:
        created_question = QuizQuestion(
            material_id=material.id,
            question=question.question,
            options=question.options,
            correct_answer=question.correct_answer,
            points=question.points,
        )
        db.add(created_question)
        created.append(created_question)
    await db.flush()
    response = [QuizQuestionPublic(id=q.id, question=q.question, options=q.options, points=q.points) for q in created]
    await db.commit()
    return response


@router.get("/materials/{material_id}/quiz", response_model=list[QuizQuestionPublic])
async def get_quiz(
    material_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[QuizQuestionPublic]:
    material = await _load_material(db, material_id)
    if not await _can_access_material(db, current_user, material):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Material access denied")
    return [QuizQuestionPublic(id=q.id, question=q.question, options=q.options, points=q.points) for q in material.questions]
