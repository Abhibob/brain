from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import Enrollment, Material, PersonalizedLesson, TribePrediction
from app.settings import get_settings

HEMODYNAMIC_LAG_S = 5.0
OUTPUT_SPACE = "fsaverage5"


def lesson_text(material: Material, personalized: PersonalizedLesson | None) -> tuple[str, str]:
    if personalized is not None:
        return personalized.generated_content, "personalized_lesson"
    sections = sorted(material.sections, key=lambda item: item.order_index)
    return "\n\n".join(f"## {section.title}\n{section.content}" for section in sections), "base_lesson"


def stimulus_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


async def load_material_and_personalization(
    db: AsyncSession,
    *,
    material_id: int,
    student_id: int,
) -> tuple[Material, PersonalizedLesson | None]:
    material = await db.scalar(
        select(Material)
        .where(Material.id == material_id)
        .options(selectinload(Material.sections), selectinload(Material.class_))
    )
    if material is None:
        raise ValueError("Material not found")
    enrolled = await db.scalar(select(Enrollment.id).where(Enrollment.class_id == material.class_id, Enrollment.student_id == student_id))
    if not enrolled:
        raise ValueError("Student is not enrolled in this material's class")
    personalized = await db.scalar(
        select(PersonalizedLesson).where(
            PersonalizedLesson.base_material_id == material_id,
            PersonalizedLesson.student_id == student_id,
        )
    )
    return material, personalized


def _empty_prediction(
    *,
    student_id: int,
    material_id: int,
    personalized_id: int | None,
    text: str,
    title: str,
    kind: str,
    status: str,
    request_payload: dict[str, Any],
    error: str | None = None,
) -> TribePrediction:
    return TribePrediction(
        student_id=student_id,
        material_id=material_id,
        personalized_lesson_id=personalized_id,
        status=status,
        stimulus_hash=stimulus_hash(text),
        stimulus_title=title,
        stimulus_kind=kind,
        model_version=None,
        hemodynamic_lag_s=HEMODYNAMIC_LAG_S,
        request_payload=request_payload,
        response_payload=None,
        roi_timeseries={},
        roi_summary={},
        connectivity=[],
        surface_summary={},
        error=error,
        completed_at=datetime.now(UTC) if status in {"not_configured", "failed"} else None,
    )


def _normalize_roi_timeseries(response: dict[str, Any]) -> dict[str, Any]:
    raw = response.get("roi_timeseries") or response.get("roi_time_series") or response.get("time_series") or {}
    if not isinstance(raw, dict):
        return {}
    out: dict[str, Any] = {}
    for key, values in raw.items():
        if isinstance(values, dict):
            series = values.get("values") or values.get("timecourse") or []
        else:
            series = values
        if isinstance(series, list):
            out[str(key)] = [round(float(v), 6) for v in series if isinstance(v, (int, float))]
    return out


def _summarize_roi(roi_timeseries: dict[str, Any], response: dict[str, Any]) -> dict[str, Any]:
    raw_summary = response.get("roi_summary")
    if isinstance(raw_summary, dict) and raw_summary:
        return raw_summary
    summary: dict[str, Any] = {}
    for roi, values in roi_timeseries.items():
        numeric = [float(v) for v in values if isinstance(v, (int, float))]
        if not numeric:
            continue
        peak = max(numeric, key=lambda v: abs(v))
        mean = sum(numeric) / len(numeric)
        summary[roi] = {
            "mean": round(mean, 6),
            "peak": round(peak, 6),
            "peak_t": numeric.index(peak),
        }
    return summary


def _normalize_connectivity(response: dict[str, Any], roi_timeseries: dict[str, Any]) -> list[dict[str, Any]]:
    raw = response.get("connectivity") or response.get("networks") or []
    if isinstance(raw, list) and raw:
        normalized = []
        for item in raw:
            if not isinstance(item, dict):
                continue
            source = item.get("source") or item.get("from") or item.get("roi_a")
            target = item.get("target") or item.get("to") or item.get("roi_b")
            weight = item.get("weight") or item.get("correlation") or item.get("value")
            if source is None or target is None or not isinstance(weight, (int, float)):
                continue
            normalized.append({"source": str(source), "target": str(target), "weight": round(float(weight), 6)})
        return normalized

    # If the service only gives time series, derive a compact ROI correlation graph.
    rois = list(roi_timeseries.keys())[:10]
    derived: list[dict[str, Any]] = []
    for i, source in enumerate(rois):
        a = roi_timeseries.get(source) or []
        for target in rois[i + 1 :]:
            b = roi_timeseries.get(target) or []
            n = min(len(a), len(b))
            if n < 2:
                continue
            mean_a = sum(a[:n]) / n
            mean_b = sum(b[:n]) / n
            num = sum((a[j] - mean_a) * (b[j] - mean_b) for j in range(n))
            den_a = sum((a[j] - mean_a) ** 2 for j in range(n)) ** 0.5
            den_b = sum((b[j] - mean_b) ** 2 for j in range(n)) ** 0.5
            if den_a and den_b:
                derived.append({"source": source, "target": target, "weight": round(num / (den_a * den_b), 6)})
    return sorted(derived, key=lambda item: abs(item["weight"]), reverse=True)[:24]


def _surface_summary(response: dict[str, Any], roi_summary: dict[str, Any]) -> dict[str, Any]:
    surface = response.get("surface") or response.get("cortical_surface") or {}
    if isinstance(surface, dict) and surface:
        return {
            "space": surface.get("space") or response.get("output_space") or OUTPUT_SPACE,
            "vertex_count": surface.get("vertex_count") or surface.get("vertices") or surface.get("n_vertices"),
            "frame_count": surface.get("frame_count") or surface.get("frames") or surface.get("n_frames"),
            "payload_url": surface.get("payload_url") or surface.get("url"),
            "hemispheres": surface.get("hemispheres") or ["lh", "rh"],
        }
    return {
        "space": response.get("output_space") or OUTPUT_SPACE,
        "vertex_count": None,
        "frame_count": max((len(v) for v in roi_summary.values() if isinstance(v, list)), default=None),
        "payload_url": response.get("surface_payload_url"),
        "hemispheres": ["lh", "rh"],
        "roi_projection": True,
    }


async def get_latest_prediction(
    db: AsyncSession,
    *,
    student_id: int,
    material_id: int,
) -> TribePrediction | None:
    return await db.scalar(
        select(TribePrediction)
        .where(TribePrediction.student_id == student_id, TribePrediction.material_id == material_id)
        .order_by(TribePrediction.created_at.desc(), TribePrediction.id.desc())
        .limit(1)
    )


async def run_prediction(
    db: AsyncSession,
    *,
    student_id: int,
    material_id: int,
) -> TribePrediction:
    settings = get_settings()
    material, personalized = await load_material_and_personalization(db, material_id=material_id, student_id=student_id)
    text, kind = lesson_text(material, personalized)
    request_payload = {
        "model": "tribe-v2",
        "output_space": OUTPUT_SPACE,
        "hemodynamic_lag_s": HEMODYNAMIC_LAG_S,
        "student_id": student_id,
        "material_id": material_id,
        "stimulus": {
            "title": material.title,
            "kind": kind,
            "text": text,
            "sections": [
                {"id": section.id, "title": section.title, "content": section.content, "order_index": section.order_index}
                for section in sorted(material.sections, key=lambda item: item.order_index)
            ],
        },
    }

    if not settings.tribe_v2_enabled or not settings.tribe_v2_base_url:
        prediction = _empty_prediction(
            student_id=student_id,
            material_id=material_id,
            personalized_id=personalized.id if personalized else None,
            text=text,
            title=material.title,
            kind=kind,
            status="not_configured",
            request_payload={**request_payload, "stimulus": {**request_payload["stimulus"], "text": f"<{len(text)} chars>"}},
            error="EDUTRACK_TRIBE_V2_ENABLED and EDUTRACK_TRIBE_V2_BASE_URL are required to call TRIBE v2.",
        )
        db.add(prediction)
        await db.commit()
        await db.refresh(prediction)
        return prediction

    headers: dict[str, str] = {"Content-Type": "application/json"}
    if settings.tribe_v2_api_key:
        headers["Authorization"] = f"Bearer {settings.tribe_v2_api_key}"
    url = f"{settings.tribe_v2_base_url.rstrip('/')}/predict"
    try:
        async with httpx.AsyncClient(timeout=settings.tribe_v2_timeout_s) as client:
            response = await client.post(url, headers=headers, json=request_payload)
            response.raise_for_status()
            body = response.json()
    except Exception as exc:
        prediction = _empty_prediction(
            student_id=student_id,
            material_id=material_id,
            personalized_id=personalized.id if personalized else None,
            text=text,
            title=material.title,
            kind=kind,
            status="failed",
            request_payload={**request_payload, "stimulus": {**request_payload["stimulus"], "text": f"<{len(text)} chars>"}},
            error=str(exc),
        )
        db.add(prediction)
        await db.commit()
        await db.refresh(prediction)
        return prediction

    roi_timeseries = _normalize_roi_timeseries(body)
    roi_summary = _summarize_roi(roi_timeseries, body)
    connectivity = _normalize_connectivity(body, roi_timeseries)
    surface_summary = _surface_summary(body, roi_summary)
    status = str(body.get("status") or ("complete" if roi_timeseries or roi_summary or surface_summary else "queued"))
    completed = datetime.now(UTC) if status in {"complete", "failed"} else None
    values = {
        "student_id": student_id,
        "material_id": material_id,
        "personalized_lesson_id": personalized.id if personalized else None,
        "status": status,
        "stimulus_hash": stimulus_hash(text),
        "stimulus_title": material.title,
        "stimulus_kind": kind,
        "model_version": body.get("model_version") or body.get("version") or "tribe-v2",
        "hemodynamic_lag_s": float(body.get("hemodynamic_lag_s") or HEMODYNAMIC_LAG_S),
        "request_payload": {**request_payload, "stimulus": {**request_payload["stimulus"], "text": f"<{len(text)} chars>"}},
        "response_payload": body,
        "roi_timeseries": roi_timeseries,
        "roi_summary": roi_summary,
        "connectivity": connectivity,
        "surface_summary": surface_summary,
        "error": body.get("error"),
        "completed_at": completed,
    }
    if db.bind and db.bind.dialect.name == "postgresql":
        stmt = (
            insert(TribePrediction)
            .values(**values)
            .on_conflict_do_update(
                constraint="uq_tribe_student_material_stimulus",
                set_={key: value for key, value in values.items() if key not in {"student_id", "material_id", "stimulus_hash"}},
            )
            .returning(TribePrediction)
        )
        prediction = await db.scalar(stmt)
        await db.commit()
        return prediction

    existing = await db.scalar(
        select(TribePrediction).where(
            TribePrediction.student_id == student_id,
            TribePrediction.material_id == material_id,
            TribePrediction.stimulus_hash == values["stimulus_hash"],
        )
    )
    if existing is None:
        prediction = TribePrediction(**values)
        db.add(prediction)
    else:
        prediction = existing
        for key, value in values.items():
            setattr(prediction, key, value)
    await db.commit()
    await db.refresh(prediction)
    return prediction


def prediction_payload(prediction: TribePrediction | None) -> dict[str, Any]:
    if prediction is None:
        return {"status": "not_requested", "prediction": None}
    return {
        "status": prediction.status,
        "prediction": {
            "id": prediction.id,
            "student_id": prediction.student_id,
            "material_id": prediction.material_id,
            "personalized_lesson_id": prediction.personalized_lesson_id,
            "stimulus_hash": prediction.stimulus_hash,
            "stimulus_title": prediction.stimulus_title,
            "stimulus_kind": prediction.stimulus_kind,
            "model_version": prediction.model_version,
            "hemodynamic_lag_s": prediction.hemodynamic_lag_s,
            "roi_timeseries": prediction.roi_timeseries or {},
            "roi_summary": prediction.roi_summary or {},
            "connectivity": prediction.connectivity or [],
            "surface_summary": prediction.surface_summary or {},
            "error": prediction.error,
            "created_at": prediction.created_at,
            "completed_at": prediction.completed_at,
        },
    }
