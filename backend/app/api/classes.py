from __future__ import annotations

import secrets

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_current_user, require_role
from app.db import get_db
from app.models import Class, Enrollment, Material, MaterialSection, PredictionModel, ScorePrediction, StudentProfileEntry, TrackingSession, User
from app.schemas import ClassAnalyticsOut, ClassCreate, ClassOut, EnrollRequest
from app.services.ml import drift_status

router = APIRouter(prefix="/classes", tags=["classes"])


def _class_out(class_: Class) -> ClassOut:
    return ClassOut(
        id=class_.id,
        educator_id=class_.educator_id,
        title=class_.title,
        description=class_.description,
        enrollment_code=class_.enrollment_code,
        created_at=class_.created_at,
    )


def _can_read_class(user: User, class_: Class, enrollment_id: int | None = None) -> bool:
    if user.role == "researcher":
        return True
    if user.role == "educator":
        return class_.educator_id == user.id
    return bool(enrollment_id)


async def _new_enrollment_code(db: AsyncSession) -> str:
    while True:
        code = secrets.token_urlsafe(6).replace("-", "").replace("_", "").upper()[:8]
        exists = await db.scalar(select(Class.id).where(Class.enrollment_code == code))
        if not exists:
            return code


@router.get("", response_model=list[ClassOut])
async def list_classes(current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)) -> list[ClassOut]:
    if current_user.role == "educator":
        rows = (await db.scalars(select(Class).where(Class.educator_id == current_user.id).order_by(Class.created_at.desc()))).all()
    elif current_user.role == "student":
        rows = (
            await db.scalars(
                select(Class)
                .join(Enrollment, Enrollment.class_id == Class.id)
                .where(Enrollment.student_id == current_user.id)
                .order_by(Class.created_at.desc())
            )
        ).all()
    else:
        rows = (await db.scalars(select(Class).order_by(Class.created_at.desc()))).all()
    return [_class_out(row) for row in rows]


@router.post("", response_model=ClassOut)
async def create_class(
    payload: ClassCreate,
    current_user: User = Depends(require_role("educator")),
    db: AsyncSession = Depends(get_db),
) -> ClassOut:
    class_ = Class(
        educator_id=current_user.id,
        title=payload.title,
        description=payload.description,
        enrollment_code=await _new_enrollment_code(db),
    )
    db.add(class_)
    await db.commit()
    await db.refresh(class_)
    return _class_out(class_)


@router.get("/{class_id}", response_model=dict)
async def get_class(class_id: int, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)) -> dict:
    class_ = await db.scalar(select(Class).where(Class.id == class_id).options(selectinload(Class.materials)))
    if class_ is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Class not found")
    enrollment_id = None
    if current_user.role == "student":
        enrollment_id = await db.scalar(select(Enrollment.id).where(Enrollment.class_id == class_id, Enrollment.student_id == current_user.id))
    if not _can_read_class(current_user, class_, enrollment_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Class access denied")
    return {
        **_class_out(class_).model_dump(),
        "materials": [
            {
                "id": material.id,
                "title": material.title,
                "type": material.type,
                "order_index": material.order_index,
                "published_at": material.published_at,
            }
            for material in sorted(class_.materials, key=lambda item: item.order_index)
        ],
    }


@router.post("/{class_id}/enroll", response_model=dict)
async def enroll(
    class_id: int,
    payload: EnrollRequest,
    current_user: User = Depends(require_role("student")),
    db: AsyncSession = Depends(get_db),
) -> dict:
    class_ = await db.scalar(select(Class).where(Class.id == class_id))
    if class_ is None or class_.enrollment_code != payload.enrollment_code:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Class or enrollment code not found")
    existing = await db.scalar(select(Enrollment).where(Enrollment.class_id == class_id, Enrollment.student_id == current_user.id))
    if existing:
        return {"status": "already_enrolled", "class_id": class_id}
    db.add(Enrollment(class_id=class_id, student_id=current_user.id))
    await db.commit()
    return {"status": "enrolled", "class_id": class_id}


@router.get("/{class_id}/students", response_model=list[dict])
async def roster(
    class_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    class_ = await db.scalar(select(Class).where(Class.id == class_id))
    if class_ is None or not _can_read_class(current_user, class_):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Class not found")
    if current_user.role not in {"educator", "researcher"}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Roster access denied")

    if current_user.role == "researcher":
        students = (
            await db.execute(
                select(User, func.count(StudentProfileEntry.id), func.max(StudentProfileEntry.created_at))
                .join(Enrollment, Enrollment.student_id == User.id)
                .outerjoin(StudentProfileEntry, StudentProfileEntry.user_id == User.id)
                .where(Enrollment.class_id == class_id)
                .group_by(User.id)
                .order_by(User.email)
            )
        ).all()
    else:
        students = (
            await db.execute(
                select(User, func.count(StudentProfileEntry.id), func.max(StudentProfileEntry.created_at))
                .join(Enrollment, Enrollment.student_id == User.id)
                .outerjoin(StudentProfileEntry, StudentProfileEntry.user_id == User.id)
                .where(Enrollment.class_id == class_id, class_.educator_id == current_user.id)
                .group_by(User.id)
                .order_by(User.email)
            )
        ).all()
    material_count = await db.scalar(select(func.count(Material.id)).where(Material.class_id == class_id))
    return [
        {
            "id": student.id,
            "email": student.email,
            **(
                {
                    "profile_entry_count": entry_count,
                    "latest_profile_at": latest,
                }
                if current_user.role == "researcher"
                else {}
            ),
            "class_material_count": material_count or 0,
        }
        for student, entry_count, latest in students
    ]


@router.get("/{class_id}/analytics", response_model=ClassAnalyticsOut)
async def class_analytics(
    class_id: int,
    current_user: User = Depends(require_role("researcher")),
    db: AsyncSession = Depends(get_db),
) -> ClassAnalyticsOut:
    class_ = await db.scalar(select(Class).where(Class.id == class_id))
    if class_ is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Class not found")

    latest_model = await db.scalar(
        select(PredictionModel)
        .where(PredictionModel.class_id == class_id)
        .order_by(PredictionModel.trained_at.desc(), PredictionModel.id.desc())
        .limit(1)
    )
    model_payload = None
    if latest_model is not None:
        model_payload = {
            "id": latest_model.id,
            "version": latest_model.version,
            "model_type": latest_model.model_type,
            "rmse": latest_model.rmse,
            "sample_count": latest_model.sample_count,
            "trained_at": latest_model.trained_at,
            "feature_importances": latest_model.feature_importances,
        }

    prediction_rows = (
        await db.execute(
            select(User, TrackingSession, ScorePrediction)
            .join(Enrollment, Enrollment.student_id == User.id)
            .join(TrackingSession, TrackingSession.student_id == User.id)
            .join(Material, Material.id == TrackingSession.material_id)
            .outerjoin(ScorePrediction, ScorePrediction.session_id == TrackingSession.id)
            .where(Enrollment.class_id == class_id, Material.class_id == class_id)
            .order_by(User.email, TrackingSession.started_at)
        )
    ).all()

    student_map: dict[int, dict] = {}
    material_map: dict[int, dict] = {}
    section_map: dict[str, dict] = {}
    materials = (await db.scalars(select(Material).where(Material.class_id == class_id).options(selectinload(Material.sections)))).all()
    material_titles = {material.id: material.title for material in materials}
    section_titles = {str(section.id): section.title for material in materials for section in material.sections}

    for student, session, prediction in prediction_rows:
        student_payload = student_map.setdefault(
            student.id,
            {
                "id": student.id,
                "email": student.email,
                "session_count": 0,
                "prediction_count": 0,
                "average_predicted": None,
                "average_actual": None,
                "latest_prediction": None,
                "_predicted_values": [],
                "_actual_values": [],
            },
        )
        student_payload["session_count"] += 1
        material_payload = material_map.setdefault(
            session.material_id,
            {
                "material_id": session.material_id,
                "title": material_titles.get(session.material_id, "Material"),
                "session_count": 0,
                "_completion_values": [],
                "_idle_values": [],
                "_total_time_values": [],
            },
        )
        material_payload["session_count"] += 1
        features = session.features or {}
        material_payload["_completion_values"].append(float(features.get("section_completion_rate") or 0.0))
        material_payload["_idle_values"].append(float(features.get("idle_total_s") or 0.0))
        material_payload["_total_time_values"].append(float(features.get("total_time_s") or 0.0))
        for section_id, seconds in (features.get("time_per_section") or {}).items():
            section_payload = section_map.setdefault(
                str(section_id),
                {
                    "section_id": str(section_id),
                    "title": section_titles.get(str(section_id), f"Section {section_id}"),
                    "session_count": 0,
                    "_time_values": [],
                    "_hover_values": [],
                },
            )
            section_payload["session_count"] += 1
            section_payload["_time_values"].append(float(seconds or 0.0))
            section_payload["_hover_values"].append(float((features.get("hover_per_section") or {}).get(str(section_id), 0)))
        if prediction is not None:
            student_payload["prediction_count"] += 1
            student_payload["_predicted_values"].append(prediction.predicted_score)
            if prediction.actual_score is not None:
                student_payload["_actual_values"].append(float(prediction.actual_score))
            student_payload["latest_prediction"] = {
                "session_id": session.id,
                "predicted_score": prediction.predicted_score,
                "actual_score": prediction.actual_score,
                "model_version": prediction.model_version,
                "created_at": prediction.created_at,
            }

    students = []
    for payload in student_map.values():
        predicted_values = payload.pop("_predicted_values")
        actual_values = payload.pop("_actual_values")
        payload["average_predicted"] = sum(predicted_values) / len(predicted_values) if predicted_values else None
        payload["average_actual"] = sum(actual_values) / len(actual_values) if actual_values else None
        students.append(payload)

    material_engagement = []
    for payload in material_map.values():
        completion_values = payload.pop("_completion_values")
        idle_values = payload.pop("_idle_values")
        total_time_values = payload.pop("_total_time_values")
        payload["average_completion_rate"] = sum(completion_values) / len(completion_values) if completion_values else 0.0
        payload["average_idle_s"] = sum(idle_values) / len(idle_values) if idle_values else 0.0
        payload["average_total_time_s"] = sum(total_time_values) / len(total_time_values) if total_time_values else 0.0
        material_engagement.append(payload)

    section_heatmap = []
    for payload in section_map.values():
        time_values = payload.pop("_time_values")
        hover_values = payload.pop("_hover_values")
        payload["average_time_s"] = sum(time_values) / len(time_values) if time_values else 0.0
        payload["average_hovers"] = sum(hover_values) / len(hover_values) if hover_values else 0.0
        section_heatmap.append(payload)

    return ClassAnalyticsOut(
        class_id=class_id,
        model=model_payload,
        drift=await drift_status(class_id, db),
        students=sorted(students, key=lambda item: item["email"]),
        material_engagement=sorted(material_engagement, key=lambda item: item["title"]),
        section_heatmap=sorted(section_heatmap, key=lambda item: item["title"]),
    )
