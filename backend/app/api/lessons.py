from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_role
from app.db import get_db
from app.models import Class, Enrollment, Material, User
from app.workers import tasks

router = APIRouter(prefix="/lessons", tags=["lessons"])


@router.post("/{material_id}/personalize/{student_id}", response_model=dict)
async def personalize_now(
    material_id: int,
    student_id: int,
    current_user: User = Depends(require_role("researcher")),
    db: AsyncSession = Depends(get_db),
) -> dict:
    material = await db.scalar(select(Material).join(Class, Class.id == Material.class_id).where(Material.id == material_id))
    if material is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Material not found")
    enrolled = await db.scalar(select(Enrollment.id).where(Enrollment.class_id == material.class_id, Enrollment.student_id == student_id))
    if not enrolled:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student is not enrolled")
    tasks.personalize_lesson_for_student.delay(student_id, material_id)
    return {"status": "queued", "student_id": student_id, "material_id": material_id}
