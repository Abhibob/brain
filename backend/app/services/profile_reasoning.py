from __future__ import annotations

import json
import re
from typing import Any

from app.services.learning_profile import STYLE_AXES
from app.services.llm import llm_client, llm_model
from app.settings import get_settings


def _clip_delta(value: Any) -> float:
    try:
        v = float(value)
    except (TypeError, ValueError):
        return 0.0
    return max(-0.15, min(0.15, v))


def _normalize_reasoning(raw: dict[str, Any]) -> dict[str, Any]:
    delta = raw.get("style_vector_delta") or {}
    cleaned_delta = {axis: _clip_delta(delta.get(axis, 0.0)) for axis in STYLE_AXES}
    prefs_raw = raw.get("content_preferences") or {}
    prefs: dict[str, bool] = {}
    if isinstance(prefs_raw, dict):
        for key, value in prefs_raw.items():
            if isinstance(value, bool):
                prefs[str(key)[:64]] = value
    hints_raw = raw.get("lesson_plan_hints") or []
    hints: list[str] = []
    if isinstance(hints_raw, list):
        for hint in hints_raw:
            if isinstance(hint, str) and hint.strip():
                hints.append(hint.strip()[:240])
    insights_raw = raw.get("per_topic_insights") or []
    insights: list[dict[str, str]] = []
    if isinstance(insights_raw, list):
        for item in insights_raw:
            if isinstance(item, dict):
                topic = str(item.get("topic") or "").strip().lower()
                note = str(item.get("note") or "").strip()
                if topic and note:
                    insights.append({"topic": topic[:128], "note": note[:300]})
    return {
        "style_vector_delta": cleaned_delta,
        "style_narrative": str(raw.get("style_narrative") or "").strip()[:600],
        "content_preferences": prefs,
        "per_topic_insights": insights,
        "lesson_plan_hints": hints[:5],
    }


def _deterministic_reasoning(
    lesson_info: dict[str, Any],
    session_focus: dict[str, Any],
    section_focus: list[dict[str, Any]],
    profile_snapshot: dict[str, Any],
) -> dict[str, Any]:
    label = session_focus.get("label", "engaged")
    breakdown = session_focus.get("breakdown") or {}
    delta: dict[str, float] = {axis: 0.0 for axis in STYLE_AXES}
    notes: list[str] = []
    prefs: dict[str, bool] = {}
    hints: list[str] = []

    pace_component = float(breakdown.get("pace", 0.5))
    if pace_component > 0.8:
        delta["pace"] += 0.04
    elif pace_component < 0.4:
        delta["pace"] -= 0.04
        hints.append("break sections into shorter chunks to match their slower pace")

    completion = float(breakdown.get("completion", 0.5))
    if completion > 0.85:
        delta["depth"] += 0.03
    elif completion < 0.5:
        delta["depth"] -= 0.03
        prefs["benefits_from_section_summaries"] = True
        hints.append("add a quick summary at the start of each section")

    attention = float(breakdown.get("attention", 0.5))
    if attention > 0.8:
        delta["attention_stability"] += 0.04
    elif attention < 0.5:
        delta["attention_stability"] -= 0.05
        hints.append("keep individual passages under 120 words to help attention hold")

    engagement = float(breakdown.get("engagement", 0.5))
    if engagement > 0.7:
        delta["engagement_mode"] += 0.04
        delta["visual_orientation"] += 0.02
    elif engagement < 0.4:
        delta["engagement_mode"] -= 0.03

    skimmed_sections = [row for row in section_focus if row.get("label") == "skimmed"]
    distracted_sections = [row for row in section_focus if row.get("label") == "distracted"]
    focused_sections = [row for row in section_focus if row.get("label") == "focused"]
    if distracted_sections:
        hints.append("insert a checkpoint question before the distracted section type")
    if focused_sections and not skimmed_sections:
        prefs["tolerates_long_prose"] = True

    rereads = len(section_focus) - len({row["section_id"] for row in section_focus})
    if rereads > 0 or any(row["breakdown"].get("re_read_count", 0) > 0 for row in section_focus):
        delta["revisit_tendency"] += 0.03
        prefs["benefits_from_review_blocks"] = True

    topics = lesson_info.get("topics") or []
    insights: list[dict[str, str]] = []
    for topic in topics[:3]:
        insights.append(
            {
                "topic": topic,
                "note": (
                    f"session was {label}; attention {attention:.2f}, engagement {engagement:.2f}; "
                    f"lesson '{lesson_info.get('title', 'untitled')}'"
                ),
            }
        )

    if label == "focused":
        notes.append(
            f"Stayed on '{lesson_info.get('title', 'the lesson')}' with strong completion "
            f"({completion:.2f}) and steady attention."
        )
    elif label == "distracted":
        notes.append(
            f"Lost focus through '{lesson_info.get('title', 'the lesson')}'. "
            "Shorter passages and concrete examples may help next time."
        )
    elif label == "skimming":
        notes.append(
            f"Moved quickly through '{lesson_info.get('title', 'the lesson')}' with low completion. "
            "Consider summaries and lower section word counts."
        )
    else:
        notes.append(
            f"Engaged with '{lesson_info.get('title', 'the lesson')}' at a moderate pace; "
            "maintain current scaffolding."
        )

    return {
        "style_vector_delta": delta,
        "style_narrative": " ".join(notes),
        "content_preferences": prefs,
        "per_topic_insights": insights,
        "lesson_plan_hints": hints[:5],
    }


def _build_prompt(
    lesson_info: dict[str, Any],
    session_focus: dict[str, Any],
    section_focus: list[dict[str, Any]],
    profile_snapshot: dict[str, Any],
) -> str:
    return (
        "You analyze a student's reading session and output a structured update to their learning-style profile. "
        "Return ONLY JSON matching this shape (numbers in style_vector_delta clamped to [-0.15, 0.15]): "
        "{\"style_vector_delta\": {\"pace\": 0.0, \"depth\": 0.0, \"attention_stability\": 0.0, "
        "\"engagement_mode\": 0.0, \"revisit_tendency\": 0.0, \"visual_orientation\": 0.0, \"motor_style\": 0.0}, "
        "\"style_narrative\": \"...\", \"content_preferences\": {\"<snake_case_bool_key>\": true|false}, "
        "\"per_topic_insights\": [{\"topic\": \"...\", \"note\": \"...\"}], "
        "\"lesson_plan_hints\": [\"...\"]}\n\n"
        f"LESSON: {json.dumps(lesson_info)[:1800]}\n"
        f"SESSION_FOCUS: {json.dumps(session_focus)[:800]}\n"
        f"SECTION_FOCUS: {json.dumps(section_focus)[:2000]}\n"
        f"PROFILE_SNAPSHOT: {json.dumps(profile_snapshot)[:2000]}\n"
    )


async def reason_about_session(
    lesson_info: dict[str, Any],
    session_focus: dict[str, Any],
    section_focus: list[dict[str, Any]],
    profile_snapshot: dict[str, Any],
) -> dict[str, Any]:
    settings = get_settings()
    if settings.resolved_llm_provider == "deterministic":
        return _normalize_reasoning(
            _deterministic_reasoning(lesson_info, session_focus, section_focus, profile_snapshot)
        )
    client = llm_client()
    response = await client.chat.completions.create(
        model=llm_model(),
        messages=[{"role": "user", "content": _build_prompt(lesson_info, session_focus, section_focus, profile_snapshot)}],
    )
    raw = response.choices[0].message.content or "{}"
    match = re.search(r"\{.*\}", raw, re.DOTALL)
    data = json.loads(match.group(0) if match else raw)
    return _normalize_reasoning(data)
