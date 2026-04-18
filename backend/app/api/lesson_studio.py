from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_current_user
from app.db import get_db
from app.models import (
    Class,
    LessonPlanDraft,
    Material,
    TopicMasteryEdge,
    TopicMasteryNode,
    TrackingSession,
    User,
    UserLearningProfile,
)
from app.schemas import (
    LearningViewOut,
    LessonPlanCreate,
    LessonPlanDraftOut,
    LessonPlanPatch,
    MaterialOut,
    SectionOut,
    TopicEdgeOut,
    TopicNodeOut,
    UserLearningProfileOut,
)
from app.services import lesson_studio as studio_service

router = APIRouter(tags=["lesson_studio"])


def _require_educator_or_researcher(user: User) -> None:
    if user.role not in {"educator", "researcher"}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only educators or researchers may use the lesson studio",
        )


async def _load_draft(db: AsyncSession, draft_id: int, user: User) -> LessonPlanDraft:
    draft = await db.scalar(select(LessonPlanDraft).where(LessonPlanDraft.id == draft_id))
    if draft is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Draft not found")
    if user.role == "educator" and draft.educator_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Educator does not own this draft",
        )
    return draft


@router.post("/teacher/lesson-plans", response_model=LessonPlanDraftOut)
async def create_lesson_plan(
    payload: LessonPlanCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> LessonPlanDraftOut:
    _require_educator_or_researcher(current_user)
    class_id = payload.class_id
    material = None
    if payload.material_id is not None:
        material = await db.scalar(
            select(Material)
            .where(Material.id == payload.material_id)
            .options(
                selectinload(Material.sections),
                selectinload(Material.questions),
                selectinload(Material.class_),
            )
        )
        if material is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Material not found")
        class_id = class_id or material.class_id
        if current_user.role == "educator" and material.class_.educator_id != current_user.id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your material")
    if class_id is not None and current_user.role == "educator":
        owner = await db.scalar(select(Class.educator_id).where(Class.id == class_id))
        if owner is None or owner != current_user.id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your class")
    draft = await studio_service.create_draft(
        db,
        educator_id=current_user.id,
        student_id=payload.student_id,
        class_id=class_id,
        topic=payload.topic,
        description=payload.description,
    )
    if material is not None:
        # Seed with the material's real sections + quiz. No LLM calls here.
        await studio_service.seed_draft_from_material(db, draft, material)
    else:
        candidates = await studio_service.generate_candidates(db, draft)
        await studio_service.propose_sequence(db, draft, candidates)
    view = await studio_service.get_draft_view(db, draft.id)
    return _to_draft_out(view)


@router.get("/teacher/lesson-plans/{draft_id}", response_model=LessonPlanDraftOut)
async def get_lesson_plan(
    draft_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> LessonPlanDraftOut:
    _require_educator_or_researcher(current_user)
    draft = await _load_draft(db, draft_id, current_user)
    view = await studio_service.get_draft_view(db, draft.id)
    return _to_draft_out(view)


@router.post("/teacher/lesson-plans/{draft_id}/regenerate", response_model=LessonPlanDraftOut)
async def regenerate_lesson_plan(
    draft_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> LessonPlanDraftOut:
    """Refresh the AI suggestions for this draft. Leaves the teacher's current lesson intact."""
    _require_educator_or_researcher(current_user)
    draft = await _load_draft(db, draft_id, current_user)
    await studio_service.generate_candidates(db, draft)
    view = await studio_service.get_draft_view(db, draft.id)
    return _to_draft_out(view)


@router.patch("/teacher/lesson-plans/{draft_id}", response_model=LessonPlanDraftOut)
async def patch_lesson_plan(
    draft_id: int,
    payload: LessonPlanPatch,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> LessonPlanDraftOut:
    _require_educator_or_researcher(current_user)
    draft = await _load_draft(db, draft_id, current_user)
    if payload.nodes is not None:
        await studio_service.update_draft_nodes(
            db,
            draft,
            [node.model_dump() for node in payload.nodes],
        )
    view = await studio_service.get_draft_view(db, draft.id)
    return _to_draft_out(view)


@router.post("/teacher/lesson-plans/{draft_id}/publish", response_model=MaterialOut)
async def publish_lesson_plan(
    draft_id: int,
    target_material_id: int | None = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MaterialOut:
    _require_educator_or_researcher(current_user)
    draft = await _load_draft(db, draft_id, current_user)
    if target_material_id is not None:
        target = await db.scalar(
            select(Material)
            .where(Material.id == target_material_id)
            .options(selectinload(Material.class_))
        )
        if target is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Target material not found")
        if current_user.role == "educator" and target.class_.educator_id != current_user.id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your material")
    try:
        material = await studio_service.publish_draft(db, draft, target_material_id=target_material_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return MaterialOut(
        id=material.id,
        class_id=material.class_id,
        title=material.title,
        type=material.type,
        order_index=material.order_index,
        published_at=material.published_at,
        personalized=False,
        generated_content=None,
        sections=[
            SectionOut(
                id=section.id,
                title=section.title,
                content=section.content,
                order_index=section.order_index,
                word_count=section.word_count,
            )
            for section in sorted(material.sections, key=lambda s: s.order_index)
        ],
    )


@router.get("/teacher/students/{student_id}/learning-view", response_model=LearningViewOut)
async def get_learning_view(
    student_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> LearningViewOut:
    _require_educator_or_researcher(current_user)
    profile = await db.scalar(
        select(UserLearningProfile).where(UserLearningProfile.user_id == student_id)
    )
    nodes = (
        await db.scalars(
            select(TopicMasteryNode)
            .where(TopicMasteryNode.user_id == student_id)
            .order_by(TopicMasteryNode.encounter_count.desc())
            .limit(30)
        )
    ).all()
    edges = (
        await db.scalars(
            select(TopicMasteryEdge).where(TopicMasteryEdge.user_id == student_id).limit(60)
        )
    ).all()
    recent_sessions = (
        await db.scalars(
            select(TrackingSession)
            .where(TrackingSession.student_id == student_id, TrackingSession.focus_label.is_not(None))
            .order_by(TrackingSession.ended_at.desc())
            .limit(10)
        )
    ).all()
    top_mastery = sorted(nodes, key=lambda n: n.mastery_score, reverse=True)[:6]
    top_struggle = sorted(nodes, key=lambda n: n.struggle_signal, reverse=True)[:6]

    return LearningViewOut(
        student_id=student_id,
        learning_profile=UserLearningProfileOut(
            user_id=profile.user_id,
            style_vector={k: float(v) for k, v in (profile.style_vector or {}).items()},
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
        ) if profile else None,
        top_mastery=[_node_out(n) for n in top_mastery],
        top_struggles=[_node_out(n) for n in top_struggle if n.struggle_signal > 0],
        topic_edges=[
            TopicEdgeOut(
                from_topic=e.from_topic,
                to_topic=e.to_topic,
                relation=e.relation,
                weight=e.weight,
            )
            for e in edges
        ],
        recent_focus=[
            {
                "session_id": s.id,
                "material_id": s.material_id,
                "focus_score": s.focus_score,
                "focus_label": s.focus_label,
                "ended_at": s.ended_at.isoformat() if s.ended_at else None,
            }
            for s in recent_sessions
        ],
        narrative_notes=(profile.behavioral_signals or {}).get("narrative_notes", []) if profile else [],
    )


def _node_out(node: TopicMasteryNode) -> TopicNodeOut:
    return TopicNodeOut(
        topic=node.topic,
        mastery_score=node.mastery_score,
        exposure_score=node.exposure_score,
        encounter_count=node.encounter_count,
        quiz_sample_count=node.quiz_sample_count,
        struggle_signal=node.struggle_signal,
        strength_signal=node.strength_signal,
        last_seen_at=node.last_seen_at,
    )


def _to_draft_out(view: dict) -> LessonPlanDraftOut:
    draft = view["draft"]
    return LessonPlanDraftOut(
        id=draft["id"],
        educator_id=draft["educator_id"],
        student_id=draft["student_id"],
        class_id=draft["class_id"],
        topic=draft["topic"],
        description=draft["description"],
        status=draft["status"],
        nodes=view["nodes"],
        edges=view["edges"],
        candidates=view["candidates"],
        created_at=draft["created_at"],
        updated_at=draft["updated_at"],
    )
