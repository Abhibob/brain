from __future__ import annotations

import math
import pickle
from datetime import UTC, datetime
from typing import Any

import numpy as np
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Material, PredictionModel, QuizAttempt, ScorePrediction, TrackingSession
from app.settings import get_settings

FEATURE_KEYS = [
    "total_time_s",
    "hover_count",
    "avg_hover_duration_ms",
    "scroll_depth_pct",
    "back_scroll_count",
    "scroll_velocity_avg",
    "mouse_velocity_avg",
    "mouse_velocity_variance",
    "idle_total_s",
    "idle_count",
    "text_selection_count",
    "reading_speed_wpm",
    "section_completion_rate",
    "re_read_count",
]


def clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def flatten_features(features: dict[str, Any] | None) -> list[float]:
    features = features or {}
    values: dict[str, float] = {}
    for key in FEATURE_KEYS:
        if key == "re_read_count":
            values[key] = float(len(features.get("re_read_sections") or []))
        else:
            raw = features.get(key, 0.0)
            try:
                values[key] = float(raw)
            except (TypeError, ValueError):
                values[key] = 0.0
    return [values[key] for key in FEATURE_KEYS]


def heuristic_score(features: dict[str, Any]) -> float:
    score = 0.5
    reading_speed = float(features.get("reading_speed_wpm") or 0.0)
    if 120 <= reading_speed <= 260:
        score += 0.1
    if float(features.get("section_completion_rate") or 0.0) > 0.8:
        score += 0.15
    if float(features.get("hover_count") or 0.0) >= 2:
        score += 0.1
    total_time = max(float(features.get("total_time_s") or 0.0), 1.0)
    if float(features.get("idle_total_s") or 0.0) / total_time > 0.4:
        score -= 0.2
    if float(features.get("back_scroll_count") or 0.0) > 6:
        score -= 0.1
    return round(clamp(score), 4)


async def _latest_model(db: AsyncSession, class_id: int | None) -> PredictionModel | None:
    if class_id is None:
        criterion = PredictionModel.class_id.is_(None)
    else:
        criterion = PredictionModel.class_id == class_id
    return await db.scalar(
        select(PredictionModel)
        .where(criterion, PredictionModel.artifact.is_not(None))
        .order_by(PredictionModel.trained_at.desc(), PredictionModel.id.desc())
        .limit(1)
    )


async def predict_for_session(session_id: int, db: AsyncSession) -> ScorePrediction:
    session = await db.scalar(select(TrackingSession).where(TrackingSession.id == session_id))
    if session is None:
        raise ValueError(f"Tracking session {session_id} not found")
    material = await db.scalar(select(Material).where(Material.id == session.material_id))
    if material is None:
        raise ValueError("Session material not found")

    prediction_value: float
    confidence: float
    model_version: str
    model = await _latest_model(db, material.class_id) or await _latest_model(db, None)
    if model and model.artifact:
        artifact = pickle.loads(model.artifact)
        estimator = artifact["model"]
        x = np.array([flatten_features(session.features)], dtype=float)
        prediction_value = clamp(float(estimator.predict(x)[0]))
        confidence = clamp(1.0 - float(model.rmse), 0.35, 0.95)
        model_version = f"ml-{model.version}"
    else:
        prediction_value = heuristic_score(session.features or {})
        confidence = 0.45
        model_version = "heuristic-v1"

    existing = await db.scalar(select(ScorePrediction).where(ScorePrediction.session_id == session_id))
    if existing:
        existing.predicted_score = prediction_value
        existing.confidence = confidence
        existing.model_version = model_version
        prediction = existing
    else:
        prediction = ScorePrediction(
            session_id=session_id,
            predicted_score=prediction_value,
            confidence=confidence,
            model_version=model_version,
        )
        db.add(prediction)
    await db.commit()
    await db.refresh(prediction)
    return prediction


async def train_model_for_class(class_id: int | None, db: AsyncSession) -> PredictionModel | None:
    settings = get_settings()
    query = (
        select(TrackingSession, QuizAttempt)
        .join(QuizAttempt, QuizAttempt.session_id == TrackingSession.id)
        .join(Material, Material.id == TrackingSession.material_id)
        .where(TrackingSession.features.is_not(None), QuizAttempt.max_score > 0)
    )
    if class_id is not None:
        query = query.where(Material.class_id == class_id)
    rows = (await db.execute(query)).all()
    if len(rows) < settings.xgboost_min_samples:
        return None

    x = np.array([flatten_features(session.features) for session, _attempt in rows], dtype=float)
    y = np.array([attempt.score / attempt.max_score for _session, attempt in rows], dtype=float)

    from xgboost import XGBRegressor

    estimator = XGBRegressor(
        n_estimators=60,
        max_depth=3,
        learning_rate=0.08,
        subsample=0.9,
        colsample_bytree=0.9,
        objective="reg:squarederror",
        random_state=42,
    )
    estimator.fit(x, y)
    preds = estimator.predict(x)
    rmse = float(math.sqrt(np.mean((preds - y) ** 2)))
    importances = {
        feature: float(value)
        for feature, value in sorted(zip(FEATURE_KEYS, estimator.feature_importances_, strict=True), key=lambda item: item[1], reverse=True)
    }
    version = datetime.now(UTC).strftime("%Y%m%d%H%M%S")
    artifact = pickle.dumps({"model": estimator, "feature_keys": FEATURE_KEYS})
    model = PredictionModel(
        class_id=class_id,
        version=version,
        model_type="xgboost",
        feature_importances=importances,
        rmse=rmse,
        sample_count=len(rows),
        artifact=artifact,
    )
    db.add(model)
    await db.commit()
    await db.refresh(model)
    return model


async def drift_status(class_id: int, db: AsyncSession) -> dict[str, Any]:
    model = await _latest_model(db, class_id)
    if model is None:
        return {"checked": False, "flagged": False, "reason": "no_class_model"}
    rows = (
        await db.execute(
            select(ScorePrediction)
            .join(TrackingSession, TrackingSession.id == ScorePrediction.session_id)
            .join(Material, Material.id == TrackingSession.material_id)
            .where(
                Material.class_id == class_id,
                ScorePrediction.actual_score.is_not(None),
                ScorePrediction.model_version.like("ml-%"),
            )
            .order_by(ScorePrediction.created_at.desc())
            .limit(50)
        )
    ).scalars().all()
    if len(rows) < 5:
        return {"checked": False, "flagged": False, "reason": "insufficient_recent_ml_predictions", "baseline_rmse": model.rmse}
    recent_rmse = math.sqrt(np.mean([(row.predicted_score - float(row.actual_score)) ** 2 for row in rows]))
    threshold = model.rmse * 1.15
    return {
        "checked": True,
        "flagged": recent_rmse > threshold,
        "baseline_rmse": model.rmse,
        "recent_rmse": recent_rmse,
        "threshold": threshold,
        "sample_count": len(rows),
    }
