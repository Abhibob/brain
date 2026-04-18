from __future__ import annotations

from typing import Any


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def _style(snapshot: dict[str, Any]) -> dict[str, float]:
    vec = (snapshot or {}).get("style_vector") or {}
    return {
        "pace": float(vec.get("pace", 0.5)),
        "depth": float(vec.get("depth", 0.5)),
        "attention_stability": float(vec.get("attention_stability", 0.5)),
        "engagement_mode": float(vec.get("engagement_mode", 0.5)),
        "revisit_tendency": float(vec.get("revisit_tendency", 0.5)),
        "visual_orientation": float(vec.get("visual_orientation", 0.5)),
        "motor_style": float(vec.get("motor_style", 0.5)),
    }


def _reading_components(payload: dict[str, Any], style: dict[str, float]) -> tuple[dict[str, float], list[str]]:
    words = float(payload.get("estimated_word_count") or 200)
    components: dict[str, float] = {}
    rationale: list[str] = []

    ideal_short = 140
    ideal_long = 260
    if style["attention_stability"] < 0.45:
        pace_fit = 1.0 if words <= ideal_short + 40 else max(0.2, 1.0 - (words - ideal_short) / 300)
        rationale.append("prefers shorter passages")
    elif style["depth"] > 0.6:
        pace_fit = 1.0 if ideal_long - 40 <= words <= ideal_long + 80 else max(0.3, 1.0 - abs(words - ideal_long) / 220)
        rationale.append("tolerates longer readings when depth is high")
    else:
        pace_fit = 1.0 - abs(words - 190) / 280
    components["length_fit"] = _clamp(pace_fit)

    narrative_style = str(payload.get("style") or "").lower()
    depth_fit = 1.0
    if "narrative" in narrative_style and style["depth"] < 0.35:
        depth_fit = 0.7
    if "rigorous" in narrative_style and style["depth"] < 0.4:
        depth_fit = 0.5
        rationale.append("content may be too dense")
    components["depth_fit"] = _clamp(depth_fit)

    components["engagement_fit"] = _clamp(0.5 + 0.3 * style["engagement_mode"])
    components["format_fit"] = _clamp(0.5 + 0.2 * style["depth"])
    return components, rationale


def _quiz_components(payload: dict[str, Any], style: dict[str, float]) -> tuple[dict[str, float], list[str]]:
    difficulty = str(payload.get("difficulty") or "core").lower()
    attention = style["attention_stability"]
    depth = style["depth"]
    components: dict[str, float] = {}
    rationale: list[str] = []

    question_count = len(payload.get("questions") or [])
    if question_count == 0:
        components["length_fit"] = 0.4
    elif attention < 0.45 and question_count > 5:
        components["length_fit"] = 0.4
        rationale.append("fewer questions fit better")
    else:
        components["length_fit"] = 1.0 - abs(question_count - 3) / 10

    if difficulty in {"review", "easy", "core"}:
        components["depth_fit"] = _clamp(0.7 + 0.25 * (1.0 - depth))
    else:
        components["depth_fit"] = _clamp(0.5 + 0.4 * depth)
        if depth < 0.35:
            rationale.append("challenge may be too high")

    components["engagement_fit"] = _clamp(0.6 + 0.2 * style["engagement_mode"])
    components["format_fit"] = _clamp(0.6 + 0.2 * attention)
    return components, rationale


def _video_components(payload: dict[str, Any], style: dict[str, float]) -> tuple[dict[str, float], list[str]]:
    components: dict[str, float] = {}
    rationale: list[str] = []

    minutes = float(payload.get("duration_minutes") or 10)
    if style["attention_stability"] < 0.45:
        components["length_fit"] = _clamp(1.0 - max(0.0, minutes - 8) / 20)
        if minutes > 12:
            rationale.append("video length may exceed attention span")
    else:
        components["length_fit"] = _clamp(1.0 - max(0.0, minutes - 15) / 30)

    components["format_fit"] = _clamp(0.5 + 0.4 * style["visual_orientation"])
    if style["visual_orientation"] > 0.6:
        rationale.append("strong visual orientation - video plays to their strength")

    components["depth_fit"] = _clamp(0.55 + 0.25 * style["depth"])
    components["engagement_fit"] = _clamp(0.5 + 0.3 * style["engagement_mode"])
    return components, rationale


def _practice_components(payload: dict[str, Any], style: dict[str, float]) -> tuple[dict[str, float], list[str]]:
    components: dict[str, float] = {}
    rationale: list[str] = []
    problems = payload.get("problems") or []
    count = len(problems)
    if style["attention_stability"] < 0.45 and count > 2:
        components["length_fit"] = 0.45
        rationale.append("reduce number of problems")
    else:
        components["length_fit"] = _clamp(1.0 - abs(count - 2) / 4)
    components["engagement_fit"] = _clamp(0.55 + 0.35 * style["engagement_mode"])
    components["depth_fit"] = _clamp(0.4 + 0.5 * style["depth"])
    components["format_fit"] = _clamp(0.55 + 0.2 * style["motor_style"])
    return components, rationale


def _mastery_alignment(topic: str, snapshot: dict[str, Any]) -> tuple[float, str | None]:
    nodes = (snapshot or {}).get("top_mastery") or []
    struggles = (snapshot or {}).get("top_struggles") or []
    topic_l = (topic or "").strip().lower()
    if not topic_l:
        return 0.6, None
    for node in struggles:
        if node.get("topic") == topic_l:
            return 0.95, "targets a known struggle area"
    for node in nodes:
        if node.get("topic") == topic_l and float(node.get("mastery_score", 0.5)) > 0.8:
            return 0.35, "already near-mastered; may be redundant"
    return 0.65, None


def score_asset_for_student(
    asset: dict[str, Any],
    profile_snapshot: dict[str, Any],
) -> dict[str, Any]:
    kind = asset.get("kind")
    payload = asset.get("payload") or {}
    style = _style(profile_snapshot)

    if kind == "reading":
        components, rationale = _reading_components(payload, style)
    elif kind == "quiz":
        components, rationale = _quiz_components(payload, style)
    elif kind == "video":
        components, rationale = _video_components(payload, style)
    elif kind == "practice":
        components, rationale = _practice_components(payload, style)
    else:
        components = {"length_fit": 0.5, "depth_fit": 0.5, "engagement_fit": 0.5, "format_fit": 0.5}
        rationale = []

    mastery_fit, mastery_note = _mastery_alignment(asset.get("topic") or "", profile_snapshot)
    components["mastery_fit"] = mastery_fit
    if mastery_note:
        rationale.append(mastery_note)

    weights = {
        "length_fit": 0.18,
        "depth_fit": 0.22,
        "engagement_fit": 0.18,
        "format_fit": 0.18,
        "mastery_fit": 0.24,
    }
    raw = sum(components[k] * weights[k] for k in weights)
    fit_score = int(round(_clamp(raw) * 100))

    if not rationale:
        rationale.append("balanced fit against current learning style")
    return {
        "fit_score": fit_score,
        "rationale": "; ".join(rationale[:3]),
        "components": {key: round(value, 3) for key, value in components.items()},
    }
