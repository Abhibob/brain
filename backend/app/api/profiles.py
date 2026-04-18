from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db import get_db
from app.models import (
    Enrollment,
    StudentProfileEntry,
    TopicMasteryEdge,
    TopicMasteryNode,
    User,
    UserLearningProfile,
)
from app.schemas import (
    LearningContextOut,
    LessonPlanOut,
    LessonPlanRequest,
    MasteryOut,
    ProfileEntryOut,
    TopicEdgeOut,
    TopicNodeOut,
    UserLearningProfileOut,
)
from app.services import learning_profile as lp_service
from app.services import rag

router = APIRouter(tags=["profiles"])


def _authorize_profile_access(current_user: User, student_id: int) -> None:
    if current_user.role == "researcher":
        return
    if current_user.role == "student" and current_user.id == student_id:
        return
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Not allowed to read this profile",
    )


@router.get("/students/{student_id}/profile", response_model=dict)
async def get_student_profile(
    student_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    _authorize_profile_access(current_user, student_id)
    if current_user.role == "researcher":
        allowed = await db.scalar(select(Enrollment.id).where(Enrollment.student_id == student_id))
        if not allowed:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student not found")
    entries = (
        await db.scalars(
            select(StudentProfileEntry)
            .where(StudentProfileEntry.user_id == student_id)
            .order_by(StudentProfileEntry.created_at.desc(), StudentProfileEntry.id.desc())
        )
    ).all()
    return {
        "student_id": student_id,
        "entry_count": len(entries),
        "entries": [
            ProfileEntryOut(
                id=entry.id,
                profile_text=entry.profile_text,
                profile_json=entry.profile_json,
                quiz_score=entry.quiz_score,
                trigger_material_id=entry.trigger_material_id,
                created_at=entry.created_at,
            ).model_dump()
            for entry in entries
        ],
    }


@router.get("/students/{student_id}/learning-profile", response_model=UserLearningProfileOut)
async def get_learning_profile(
    student_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UserLearningProfileOut:
    _authorize_profile_access(current_user, student_id)
    profile = await db.scalar(
        select(UserLearningProfile).where(UserLearningProfile.user_id == student_id)
    )
    if profile is None:
        profile = await lp_service.get_or_create_profile(student_id, db)
        await db.commit()
    return UserLearningProfileOut(
        user_id=profile.user_id,
        style_vector={key: float(value) for key, value in (profile.style_vector or {}).items()},
        rolling_focus_score=profile.rolling_focus_score,
        rolling_reading_speed_wpm=profile.rolling_reading_speed_wpm,
        rolling_completion_rate=profile.rolling_completion_rate,
        preferred_session_length_s=profile.preferred_session_length_s,
        engagement_fingerprint=profile.engagement_fingerprint or {},
        behavioral_signals=profile.behavioral_signals or {},
        peak_focus_time_of_day=profile.peak_focus_time_of_day or {},
        session_count=profile.session_count,
        lesson_count=profile.lesson_count,
        quiz_count=profile.quiz_count,
        last_focus_label=profile.last_focus_label,
        last_updated_at=profile.last_updated_at,
    )


@router.get("/students/{student_id}/mastery", response_model=MasteryOut)
async def get_mastery(
    student_id: int,
    topic: str | None = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MasteryOut:
    _authorize_profile_access(current_user, student_id)
    query = select(TopicMasteryNode).where(TopicMasteryNode.user_id == student_id)
    if topic:
        query = query.where(TopicMasteryNode.topic == topic.strip().lower())
    nodes = (await db.scalars(query.order_by(TopicMasteryNode.encounter_count.desc()).limit(50))).all()
    edges: list[TopicMasteryEdge] = []
    if topic:
        edges = list(
            (
                await db.scalars(
                    select(TopicMasteryEdge).where(
                        TopicMasteryEdge.user_id == student_id,
                        TopicMasteryEdge.from_topic == topic.strip().lower(),
                    )
                )
            ).all()
        )
    return MasteryOut(
        seed_topic=topic,
        nodes=[
            TopicNodeOut(
                topic=n.topic,
                mastery_score=n.mastery_score,
                exposure_score=n.exposure_score,
                encounter_count=n.encounter_count,
                quiz_sample_count=n.quiz_sample_count,
                struggle_signal=n.struggle_signal,
                strength_signal=n.strength_signal,
                last_seen_at=n.last_seen_at,
            )
            for n in nodes
        ],
        edges=[
            TopicEdgeOut(
                from_topic=e.from_topic,
                to_topic=e.to_topic,
                relation=e.relation,
                weight=e.weight,
            )
            for e in edges
        ],
    )


@router.get("/students/{student_id}/learning-context", response_model=LearningContextOut)
async def get_learning_context(
    student_id: int,
    topic: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> LearningContextOut:
    _authorize_profile_access(current_user, student_id)
    context = await rag.build_learning_context(student_id, topic, db)
    return LearningContextOut(
        style_summary_lines=context["style_summary_lines"],
        mastery_lines=context["mastery_lines"],
        mastery_nodes=context["mastery_nodes"],
        topic_edges=context["topic_edges"],
        profile_entries=context["profile_entries"],
        recent_focus=context["recent_focus"],
        recent_hints=context["recent_hints"],
        seed_text=context["seed_text"],
    )


@router.post("/students/{student_id}/lesson-plan", response_model=LessonPlanOut)
async def post_lesson_plan(
    student_id: int,
    payload: LessonPlanRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> LessonPlanOut:
    _authorize_profile_access(current_user, student_id)
    plan = await rag.generate_lesson_plan(student_id, payload.topic, db, material_id=payload.material_id)
    return LessonPlanOut(**plan)
