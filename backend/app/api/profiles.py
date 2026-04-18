from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_role
from app.db import get_db
from app.models import Class, Enrollment, StudentProfileEntry, User
from app.schemas import ProfileEntryOut

router = APIRouter(tags=["profiles"])


@router.get("/students/{student_id}/profile", response_model=dict)
async def get_student_profile(
    student_id: int,
    current_user: User = Depends(require_role("researcher")),
    db: AsyncSession = Depends(get_db),
) -> dict:
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
