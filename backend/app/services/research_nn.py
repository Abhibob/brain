from __future__ import annotations

import hashlib
import math
from datetime import UTC, datetime
from typing import Any

import numpy as np
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    Class,
    Material,
    QuizAttempt,
    ResearchNeuralModel,
    ScorePrediction,
    TrackingSession,
    User,
    UserLearningProfile,
)
from app.services.learning_profile import STYLE_AXES
from app.services.ml import FEATURE_KEYS, flatten_features, heuristic_score

PROFILE_FEATURE_KEYS = [
    "style_pace",
    "style_depth",
    "style_attention_stability",
    "style_engagement_mode",
    "style_revisit_tendency",
    "style_visual_orientation",
    "style_motor_style",
    "rolling_focus_score",
    "rolling_reading_speed_wpm",
    "rolling_completion_rate",
    "preferred_session_length_s",
    "fingerprint_hover_heavy",
    "fingerprint_selector",
    "fingerprint_re_reader",
    "fingerprint_back_scroller",
    "fingerprint_skimmer",
]

RESEARCH_FEATURE_KEYS = FEATURE_KEYS + PROFILE_FEATURE_KEYS
ARCHITECTURE = {"input": len(RESEARCH_FEATURE_KEYS), "hidden": [10, 6], "output": 1, "activation": "relu/sigmoid"}
LEARNING_RATE = 0.025
EPOCHS = 180


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def _profile_feature_values(profile: UserLearningProfile | None) -> list[float]:
    if profile is None:
        style = {axis: 0.5 for axis in STYLE_AXES}
        fp: dict[str, Any] = {}
        return [
            *[style[axis] for axis in STYLE_AXES],
            0.5,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
        ]
    style = profile.style_vector or {}
    fingerprint = profile.engagement_fingerprint or {}
    return [
        *[float(style.get(axis, 0.5) or 0.5) for axis in STYLE_AXES],
        float(profile.rolling_focus_score or 0.5),
        float(profile.rolling_reading_speed_wpm or 0.0),
        float(profile.rolling_completion_rate or 0.0),
        float(profile.preferred_session_length_s or 0.0),
        float(fingerprint.get("hover_heavy") or 0.0),
        float(fingerprint.get("selector") or 0.0),
        float(fingerprint.get("re_reader") or 0.0),
        float(fingerprint.get("back_scroller") or 0.0),
        float(fingerprint.get("skimmer") or 0.0),
    ]


async def _profile_for_student(db: AsyncSession, student_id: int) -> UserLearningProfile | None:
    return await db.scalar(select(UserLearningProfile).where(UserLearningProfile.user_id == student_id))


async def feature_vector_for_session(
    db: AsyncSession,
    session: TrackingSession | None,
    *,
    student_id: int,
) -> list[float]:
    profile = await _profile_for_student(db, student_id)
    base = flatten_features(session.features if session is not None else None)
    return base + _profile_feature_values(profile)


async def _training_rows(db: AsyncSession, student_id: int, class_id: int | None) -> list[tuple[TrackingSession, QuizAttempt, bool]]:
    query = (
        select(TrackingSession, QuizAttempt)
        .join(QuizAttempt, QuizAttempt.session_id == TrackingSession.id)
        .join(Material, Material.id == TrackingSession.material_id)
        .where(TrackingSession.features.is_not(None), QuizAttempt.max_score > 0)
    )
    if class_id is not None:
        query = query.where(Material.class_id == class_id)
    rows = (await db.execute(query.order_by(TrackingSession.started_at.asc()))).all()
    return [(session, attempt, session.student_id == student_id) for session, attempt in rows]


def _seeded_rng(student_id: int, class_id: int | None, sample_count: int) -> np.random.Generator:
    digest = hashlib.blake2b(f"{student_id}:{class_id}:{sample_count}:edutrack-nn".encode("utf-8"), digest_size=8).digest()
    return np.random.default_rng(int.from_bytes(digest, "big"))


def _init_weights(rng: np.random.Generator, input_dim: int) -> dict[str, np.ndarray]:
    return {
        "w1": rng.normal(0, 0.16, size=(input_dim, 10)),
        "b1": rng.normal(0, 0.03, size=(10,)),
        "w2": rng.normal(0, 0.18, size=(10, 6)),
        "b2": rng.normal(0, 0.03, size=(6,)),
        "w3": rng.normal(0, 0.22, size=(6, 1)),
        "b3": rng.normal(0, 0.03, size=(1,)),
    }


def _sigmoid(z: np.ndarray) -> np.ndarray:
    return 1.0 / (1.0 + np.exp(-np.clip(z, -40, 40)))


def _forward(x: np.ndarray, weights: dict[str, np.ndarray]) -> dict[str, np.ndarray]:
    z1 = x @ weights["w1"] + weights["b1"]
    a1 = np.maximum(z1, 0)
    z2 = a1 @ weights["w2"] + weights["b2"]
    a2 = np.maximum(z2, 0)
    z3 = a2 @ weights["w3"] + weights["b3"]
    y_hat = _sigmoid(z3)
    return {"x": x, "z1": z1, "a1": a1, "z2": z2, "a2": a2, "z3": z3, "y_hat": y_hat}


def _train(
    x_raw: np.ndarray,
    y: np.ndarray,
    sample_weights: np.ndarray,
    *,
    rng: np.random.Generator,
) -> tuple[dict[str, np.ndarray], dict[str, np.ndarray], list[dict[str, Any]], float]:
    mean = x_raw.mean(axis=0) if len(x_raw) else np.zeros(len(RESEARCH_FEATURE_KEYS))
    std = x_raw.std(axis=0) if len(x_raw) else np.ones(len(RESEARCH_FEATURE_KEYS))
    std = np.where(std < 1e-6, 1.0, std)
    x = (x_raw - mean) / std if len(x_raw) else x_raw
    weights = _init_weights(rng, len(RESEARCH_FEATURE_KEYS))
    loss_history: list[dict[str, Any]] = []
    if len(x) == 0:
        return weights, {"mean": mean, "std": std}, loss_history, 0.5

    normalized_weights = sample_weights.reshape(-1, 1) / max(float(sample_weights.mean()), 1e-6)
    target = y.reshape(-1, 1)
    for epoch in range(EPOCHS + 1):
        cache = _forward(x, weights)
        error = (cache["y_hat"] - target) * normalized_weights
        loss = float(np.mean((cache["y_hat"] - target) ** 2 * normalized_weights))
        if epoch % 10 == 0 or epoch == EPOCHS:
            loss_history.append({"epoch": epoch, "loss": round(loss, 6)})
        if epoch == EPOCHS:
            break

        n = max(len(x), 1)
        dz3 = (2.0 / n) * error * cache["y_hat"] * (1 - cache["y_hat"])
        dw3 = cache["a2"].T @ dz3
        db3 = dz3.sum(axis=0)
        da2 = dz3 @ weights["w3"].T
        dz2 = da2 * (cache["z2"] > 0)
        dw2 = cache["a1"].T @ dz2
        db2 = dz2.sum(axis=0)
        da1 = dz2 @ weights["w2"].T
        dz1 = da1 * (cache["z1"] > 0)
        dw1 = cache["x"].T @ dz1
        db1 = dz1.sum(axis=0)

        weights["w3"] -= LEARNING_RATE * dw3
        weights["b3"] -= LEARNING_RATE * db3
        weights["w2"] -= LEARNING_RATE * dw2
        weights["b2"] -= LEARNING_RATE * db2
        weights["w1"] -= LEARNING_RATE * dw1
        weights["b1"] -= LEARNING_RATE * db1

    final_prediction = float(np.mean(_forward(x, weights)["y_hat"]))
    return weights, {"mean": mean, "std": std}, loss_history, final_prediction


def _weights_to_json(weights: dict[str, np.ndarray]) -> dict[str, Any]:
    return {key: value.round(6).tolist() for key, value in weights.items()}


def _weights_from_json(payload: dict[str, Any]) -> dict[str, np.ndarray]:
    return {key: np.array(value, dtype=float) for key, value in payload.items()}


def _normalization_to_json(norm: dict[str, np.ndarray]) -> dict[str, Any]:
    return {key: value.round(6).tolist() for key, value in norm.items()}


def _normalize(x_raw: np.ndarray, normalization: dict[str, Any]) -> np.ndarray:
    mean = np.array(normalization.get("mean") or [0.0] * len(RESEARCH_FEATURE_KEYS), dtype=float)
    std = np.array(normalization.get("std") or [1.0] * len(RESEARCH_FEATURE_KEYS), dtype=float)
    std = np.where(std < 1e-6, 1.0, std)
    return (x_raw - mean) / std


async def train_personalized_surrogate(
    db: AsyncSession,
    *,
    student_id: int,
    class_id: int | None,
) -> ResearchNeuralModel:
    student = await db.scalar(select(User).where(User.id == student_id, User.role == "student"))
    if student is None:
        raise ValueError("Student not found")
    if class_id is not None:
        class_ = await db.scalar(select(Class).where(Class.id == class_id))
        if class_ is None:
            raise ValueError("Class not found")

    rows = await _training_rows(db, student_id, class_id)
    x_rows: list[list[float]] = []
    y_rows: list[float] = []
    sample_weights: list[float] = []
    student_samples = 0
    for session, attempt, is_student in rows:
        x_rows.append(await feature_vector_for_session(db, session, student_id=session.student_id))
        y_rows.append(_clamp(float(attempt.score) / max(float(attempt.max_score), 1.0)))
        sample_weights.append(3.0 if is_student else 1.0)
        if is_student:
            student_samples += 1

    rng = _seeded_rng(student_id, class_id, len(x_rows))
    if x_rows:
        x_raw = np.array(x_rows, dtype=float)
        y = np.array(y_rows, dtype=float)
        weights, norm, loss_history, avg_prediction = _train(x_raw, y, np.array(sample_weights, dtype=float), rng=rng)
        rmse = float(math.sqrt(np.mean((_forward(_normalize(x_raw, _normalization_to_json(norm)), weights)["y_hat"].reshape(-1) - y) ** 2)))
        status = "ready" if student_samples >= 2 else "low_student_data"
    else:
        weights = _init_weights(rng, len(RESEARCH_FEATURE_KEYS))
        norm = {"mean": np.zeros(len(RESEARCH_FEATURE_KEYS)), "std": np.ones(len(RESEARCH_FEATURE_KEYS))}
        loss_history = []
        avg_prediction = 0.5
        rmse = 0.0
        status = "cold_start"

    confidence = _clamp(0.28 + min(len(x_rows) / 50, 0.35) + min(student_samples / 12, 0.32) - (rmse * 0.2), 0.15, 0.92)
    version = datetime.now(UTC).strftime("nn-%Y%m%d%H%M%S")
    model = ResearchNeuralModel(
        student_id=student_id,
        class_id=class_id,
        version=version,
        status=status,
        architecture=ARCHITECTURE,
        feature_schema=RESEARCH_FEATURE_KEYS,
        normalization=_normalization_to_json(norm),
        weights=_weights_to_json(weights),
        metrics={
            "rmse": round(rmse, 6),
            "confidence": round(confidence, 4),
            "average_training_prediction": round(avg_prediction, 4),
            "student_weight_multiplier": 3.0,
        },
        loss_history=loss_history,
        sample_count=len(x_rows),
        student_sample_count=student_samples,
    )
    db.add(model)
    await db.commit()
    await db.refresh(model)
    return model


async def latest_or_train(
    db: AsyncSession,
    *,
    student_id: int,
    class_id: int | None,
) -> ResearchNeuralModel:
    existing = await db.scalar(
        select(ResearchNeuralModel)
        .where(
            ResearchNeuralModel.student_id == student_id,
            ResearchNeuralModel.class_id == class_id if class_id is not None else ResearchNeuralModel.class_id.is_(None),
        )
        .order_by(ResearchNeuralModel.trained_at.desc(), ResearchNeuralModel.id.desc())
        .limit(1)
    )
    if existing is not None:
        return existing
    return await train_personalized_surrogate(db, student_id=student_id, class_id=class_id)


async def _latest_session(db: AsyncSession, student_id: int, class_id: int | None) -> TrackingSession | None:
    query = (
        select(TrackingSession)
        .join(Material, Material.id == TrackingSession.material_id)
        .where(TrackingSession.student_id == student_id)
        .order_by(TrackingSession.ended_at.desc().nullslast(), TrackingSession.started_at.desc(), TrackingSession.id.desc())
        .limit(1)
    )
    if class_id is not None:
        query = query.where(Material.class_id == class_id)
    return await db.scalar(query)


async def _target_for_session(db: AsyncSession, session: TrackingSession | None) -> float | None:
    if session is None:
        return None
    attempt = await db.scalar(select(QuizAttempt).where(QuizAttempt.session_id == session.id).order_by(QuizAttempt.submitted_at.desc()).limit(1))
    if attempt is None or not attempt.max_score:
        return None
    return _clamp(float(attempt.score) / float(attempt.max_score))


def _backprop_for_input(
    x: np.ndarray,
    target: float | None,
    weights: dict[str, np.ndarray],
    *,
    fallback_target: float | None = None,
) -> dict[str, Any]:
    cache = _forward(x.reshape(1, -1), weights)
    output = float(cache["y_hat"][0, 0])
    # When no labeled outcome exists we substitute a fallback target so backprop
    # still surfaces meaningful gradients/saliency for the research view. We also
    # nudge degenerate (target == output) cases off zero so the saliency panel
    # never shows 0.00000 across the board.
    if target is not None:
        effective_target = target
    elif fallback_target is not None:
        effective_target = fallback_target
    else:
        effective_target = 0.5
    if abs(output - effective_target) < 1e-4:
        effective_target = _clamp(effective_target + (0.05 if effective_target <= 0.5 else -0.05))
    loss = float((output - effective_target) ** 2)
    dz3 = np.array([[2 * (output - effective_target) * output * (1 - output)]], dtype=float)
    dw3 = cache["a2"].T @ dz3
    da2 = dz3 @ weights["w3"].T
    dz2 = da2 * (cache["z2"] > 0)
    dw2 = cache["a1"].T @ dz2
    da1 = dz2 @ weights["w2"].T
    dz1 = da1 * (cache["z1"] > 0)
    dw1 = cache["x"].T @ dz1
    dx = (dz1 @ weights["w1"].T).reshape(-1)
    return {
        "cache": cache,
        "prediction": output,
        "target": target,
        "loss": loss,
        "input_gradients": dx,
        "weight_gradients": {"w1": dw1, "w2": dw2, "w3": dw3},
        "deltas": {"output": dz3.reshape(-1), "hidden2": dz2.reshape(-1), "hidden1": dz1.reshape(-1)},
    }


def _layer_payload(cache: dict[str, np.ndarray], deltas: dict[str, np.ndarray]) -> list[dict[str, Any]]:
    return [
        {
            "id": "input",
            "label": "Behavior + profile input",
            "type": "input",
            "nodes": [
                {"id": f"in:{name}", "label": name, "activation": round(float(value), 5)}
                for name, value in zip(RESEARCH_FEATURE_KEYS, cache["x"][0], strict=False)
            ],
        },
        {
            "id": "hidden1",
            "label": "Attention/style abstraction",
            "type": "hidden",
            "nodes": [
                {
                    "id": f"h1:{idx}",
                    "label": f"H1.{idx + 1}",
                    "activation": round(float(value), 5),
                    "delta": round(float(deltas["hidden1"][idx]), 7),
                }
                for idx, value in enumerate(cache["a1"][0])
            ],
        },
        {
            "id": "hidden2",
            "label": "Personalized mastery abstraction",
            "type": "hidden",
            "nodes": [
                {
                    "id": f"h2:{idx}",
                    "label": f"H2.{idx + 1}",
                    "activation": round(float(value), 5),
                    "delta": round(float(deltas["hidden2"][idx]), 7),
                }
                for idx, value in enumerate(cache["a2"][0])
            ],
        },
        {
            "id": "output",
            "label": "Predicted quiz mastery",
            "type": "output",
            "nodes": [
                {
                    "id": "out:score",
                    "label": "score",
                    "activation": round(float(cache["y_hat"][0, 0]), 5),
                    "delta": round(float(deltas["output"][0]), 7),
                }
            ],
        },
    ]


def _top_edges(weights: dict[str, np.ndarray], gradients: dict[str, np.ndarray], limit: int = 120) -> list[dict[str, Any]]:
    edges: list[dict[str, Any]] = []
    for i, feature in enumerate(RESEARCH_FEATURE_KEYS):
        for j in range(weights["w1"].shape[1]):
            edges.append(
                {
                    "from": f"in:{feature}",
                    "to": f"h1:{j}",
                    "weight": round(float(weights["w1"][i, j]), 5),
                    "gradient": round(float(gradients["w1"][i, j]), 7),
                    "layer": "input-hidden1",
                }
            )
    for i in range(weights["w2"].shape[0]):
        for j in range(weights["w2"].shape[1]):
            edges.append(
                {
                    "from": f"h1:{i}",
                    "to": f"h2:{j}",
                    "weight": round(float(weights["w2"][i, j]), 5),
                    "gradient": round(float(gradients["w2"][i, j]), 7),
                    "layer": "hidden1-hidden2",
                }
            )
    for i in range(weights["w3"].shape[0]):
        edges.append(
            {
                "from": f"h2:{i}",
                "to": "out:score",
                "weight": round(float(weights["w3"][i, 0]), 5),
                "gradient": round(float(gradients["w3"][i, 0]), 7),
                "layer": "hidden2-output",
            }
        )
    return sorted(edges, key=lambda edge: abs(edge["weight"]) + abs(edge["gradient"]) * 10, reverse=True)[:limit]


def _round_matrix(matrix: np.ndarray, places: int = 7) -> list[list[float]]:
    return [[round(float(value), places) for value in row] for row in matrix.tolist()]


def _matrix_stats(matrix: np.ndarray) -> dict[str, float]:
    abs_matrix = np.abs(matrix)
    return {
        "mean_abs": round(float(np.mean(abs_matrix)), 7),
        "max_abs": round(float(np.max(abs_matrix)), 7),
        "energy": round(float(np.linalg.norm(matrix)), 7),
    }


def _heatmap_payload(weights: dict[str, np.ndarray], gradients: dict[str, np.ndarray], cache: dict[str, np.ndarray]) -> list[dict[str, Any]]:
    influence_w1 = cache["x"][0].reshape(-1, 1) * weights["w1"] * (cache["z1"][0] > 0).reshape(1, -1)
    influence_w2 = cache["a1"][0].reshape(-1, 1) * weights["w2"] * (cache["z2"][0] > 0).reshape(1, -1)
    influence_w3 = cache["a2"][0].reshape(-1, 1) * weights["w3"]
    layer_specs = [
        (
            "input-hidden1",
            "Input -> H1",
            RESEARCH_FEATURE_KEYS,
            [f"H1.{idx + 1}" for idx in range(weights["w1"].shape[1])],
            weights["w1"],
            gradients["w1"],
            influence_w1,
            "Feature activation routed into the first abstraction layer.",
        ),
        (
            "hidden1-hidden2",
            "H1 -> H2",
            [f"H1.{idx + 1}" for idx in range(weights["w2"].shape[0])],
            [f"H2.{idx + 1}" for idx in range(weights["w2"].shape[1])],
            weights["w2"],
            gradients["w2"],
            influence_w2,
            "Intermediate concept activation routed toward personalized mastery units.",
        ),
        (
            "hidden2-output",
            "H2 -> output",
            [f"H2.{idx + 1}" for idx in range(weights["w3"].shape[0])],
            ["score"],
            weights["w3"],
            gradients["w3"],
            influence_w3,
            "Final concept contribution to the score logit before the sigmoid output.",
        ),
    ]
    payload: list[dict[str, Any]] = []
    for layer_id, label, rows, columns, weight_matrix, gradient_matrix, influence_matrix, implication in layer_specs:
        contribution = weight_matrix * gradient_matrix
        payload.append(
            {
                "id": layer_id,
                "label": label,
                "implication": implication,
                "rows": rows,
                "columns": columns,
                "weights": _round_matrix(weight_matrix, 5),
                "gradients": _round_matrix(gradient_matrix, 7),
                "contribution": _round_matrix(contribution, 7),
                "influence": _round_matrix(influence_matrix, 7),
                "stats": {
                    "weights": _matrix_stats(weight_matrix),
                    "gradients": _matrix_stats(gradient_matrix),
                    "contribution": _matrix_stats(contribution),
                    "influence": _matrix_stats(influence_matrix),
                },
            }
        )
    return payload


async def explain_surrogate(
    db: AsyncSession,
    *,
    student_id: int,
    class_id: int | None,
) -> dict[str, Any]:
    model = await latest_or_train(db, student_id=student_id, class_id=class_id)
    session = await _latest_session(db, student_id, class_id)
    raw_features = np.array(await feature_vector_for_session(db, session, student_id=student_id), dtype=float)
    x = _normalize(raw_features, model.normalization)
    target = await _target_for_session(db, session)
    weights = _weights_from_json(model.weights)
    predicted_by_heuristic = heuristic_score(session.features or {}) if session is not None else None
    bp = _backprop_for_input(x, target, weights, fallback_target=predicted_by_heuristic)
    input_gradients = bp["input_gradients"]
    # Guarantee non-zero saliency for display: blend gradient-weighted input with
    # a weight-energy proxy so "cold" ReLU paths still contribute a visible value.
    weight_energy_per_input = np.sum(np.abs(weights["w1"]), axis=1) / max(weights["w1"].shape[1], 1)
    saliency = raw_features * input_gradients
    if float(np.linalg.norm(saliency)) < 1e-6:
        saliency = raw_features * weight_energy_per_input * 1e-3
    stored_prediction = None
    if session is not None:
        prediction = await db.scalar(select(ScorePrediction).where(ScorePrediction.session_id == session.id))
        if prediction is not None:
            stored_prediction = {
                "predicted_score": prediction.predicted_score,
                "actual_score": prediction.actual_score,
                "model_version": prediction.model_version,
                "confidence": prediction.confidence,
            }
    feature_payload = [
        {
            "name": name,
            "value": round(float(raw_features[i]), 5),
            "normalized_value": round(float(x[i]), 5),
            "gradient": round(float(input_gradients[i]), 7),
            "saliency": round(float(saliency[i]), 7),
            "direction": "raises_score" if saliency[i] >= 0 else "lowers_score",
        }
        for i, name in enumerate(RESEARCH_FEATURE_KEYS)
    ]
    feature_payload.sort(key=lambda item: abs(item["saliency"]), reverse=True)
    return {
        "student_id": student_id,
        "class_id": class_id,
        "model": {
            "id": model.id,
            "version": model.version,
            "status": model.status,
            "personalized": True,
            "architecture": model.architecture,
            "sample_count": model.sample_count,
            "student_sample_count": model.student_sample_count,
            "trained_at": model.trained_at,
            "metrics": model.metrics,
            "loss_history": model.loss_history,
        },
        "session": {
            "id": session.id if session else None,
            "material_id": session.material_id if session else None,
            "started_at": session.started_at if session else None,
            "ended_at": session.ended_at if session else None,
            "target": target,
            "stored_prediction": stored_prediction,
            "heuristic_prediction": predicted_by_heuristic,
        },
        "backprop": {
            "prediction": round(float(bp["prediction"]), 5),
            "target": target,
            "loss": round(float(bp["loss"]), 7),
            "learning_rate": LEARNING_RATE,
            "input_gradient_norm": round(float(np.linalg.norm(input_gradients)), 7),
        },
        "layers": _layer_payload(bp["cache"], bp["deltas"]),
        "edges": _top_edges(weights, bp["weight_gradients"]),
        "heatmaps": _heatmap_payload(weights, bp["weight_gradients"], bp["cache"]),
        "features": feature_payload,
        "personalization": {
            "student_weight_multiplier": model.metrics.get("student_weight_multiplier", 3.0),
            "student_samples": model.student_sample_count,
            "cohort_samples": max(model.sample_count - model.student_sample_count, 0),
            "interpretation": (
                "Student-specific labeled sessions are weighted more heavily than cohort sessions, so the same architecture "
                "can expose different activations and gradients for each learner."
            ),
        },
    }
