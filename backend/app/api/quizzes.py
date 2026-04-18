from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_current_user, require_role
from app.db import get_db
from app.models import Class, Enrollment, Material, QuizAttempt, QuizQuestion, ScorePrediction, TrackingSession, User
from app.schemas import QuizResult, QuizSubmit
from app.workers import tasks

router = APIRouter(prefix="/quiz", tags=["quiz"])


@router.post("/{material_id}/submit", response_model=QuizResult)
async def submit_quiz(
    material_id: int,
    payload: QuizSubmit,
    current_user: User = Depends(require_role("student")),
    db: AsyncSession = Depends(get_db),
) -> QuizResult:
    material = await db.scalar(select(Material).where(Material.id == material_id).options(selectinload(Material.questions), selectinload(Material.class_)))
    if material is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Material not found")
    enrolled = await db.scalar(select(Enrollment.id).where(Enrollment.class_id == material.class_id, Enrollment.student_id == current_user.id))
    if not enrolled:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Student is not enrolled")

    session_id = payload.session_id
    if session_id is not None:
        session = await db.scalar(
            select(TrackingSession).where(
                TrackingSession.id == session_id,
                TrackingSession.student_id == current_user.id,
                TrackingSession.material_id == material_id,
            )
        )
        if session is None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid tracking session")

    questions = (await db.scalars(select(QuizQuestion).where(QuizQuestion.material_id == material_id))).all()
    if not questions:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Material has no quiz questions")

    score = 0.0
    max_score = 0.0
    normalized_answers = {str(key): value for key, value in payload.answers.items()}
    for question in questions:
        max_score += question.points
        if normalized_answers.get(str(question.id)) == question.correct_answer:
            score += question.points

    attempt = QuizAttempt(
        student_id=current_user.id,
        material_id=material_id,
        session_id=session_id,
        answers=normalized_answers,
        score=score,
        max_score=max_score,
    )
    db.add(attempt)
    if session_id is not None:
        prediction = await db.scalar(select(ScorePrediction).where(ScorePrediction.session_id == session_id))
        if prediction is not None:
            prediction.actual_score = score / max_score if max_score else 0.0
    await db.commit()
    await db.refresh(attempt)

    tasks.add_student_profile_entry.delay(current_user.id, attempt.id)
    class_id = await db.scalar(select(Class.id).where(Class.id == material.class_id))
    if class_id is not None:
        tasks.train_model_for_class.delay(class_id)
    tasks.train_global_model.delay()

    return QuizResult(attempt_id=attempt.id, score=score, max_score=max_score, normalized_score=score / max_score if max_score else 0.0)
