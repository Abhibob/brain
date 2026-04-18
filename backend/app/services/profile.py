from __future__ import annotations

import json
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import Material, QuizAttempt, ScorePrediction, StudentProfileEntry, TrackingSession
from app.services.llm import llm_client, llm_model
from app.services.rag import embed_text
from app.settings import get_settings

PROFILE_KEYS = {
    "topic",
    "observed_score",
    "predicted_score",
    "strengths_observed",
    "struggles_observed",
    "engagement_notes",
    "behavioral_summary",
    "recommendation",
}


def _lesson_summary(material: Material) -> str:
    parts = [f"{section.title}: {section.content[:400]}" for section in sorted(material.sections, key=lambda item: item.order_index)]
    return "\n".join(parts)


def build_entry_prompt(material: Material, features: dict[str, Any], score: float, max_score: float, predicted: float | None) -> str:
    return (
        "You are analyzing a student's learning session. Generate a focused profile entry.\n\n"
        f"LESSON: {material.title}\n"
        f"CONTENT SUMMARY: {_lesson_summary(material)}\n"
        f"BEHAVIORAL SESSION: {json.dumps(features, sort_keys=True)}\n"
        f"QUIZ SCORE: {score}/{max_score}\n"
        f"SCORE PREDICTION WAS: {predicted}\n\n"
        "Generate a JSON profile entry documenting what this session reveals about the student. "
        "Focus on observed strengths/struggles for this topic, engagement patterns, and concrete recommendations. "
        "Be specific and evidence-based. Return only valid JSON."
    )


def deterministic_profile_entry(material: Material, features: dict[str, Any], score: float, max_score: float, predicted: float | None) -> dict[str, Any]:
    normalized = score / max_score if max_score else 0.0
    rereads = len(features.get("re_read_sections") or [])
    strengths = ["completed most lesson sections"] if features.get("section_completion_rate", 0) >= 0.8 else ["attempted the lesson workflow"]
    struggles = []
    if normalized < 0.75:
        struggles.append("needs more scaffolding before independent recall")
    if features.get("back_scroll_count", 0) > 3 or rereads:
        struggles.append("revisited prior material while resolving confusion")
    if not struggles:
        struggles.append("should continue practicing transfer problems")
    behavioral = "slow careful reader, benefits from visual aids" if features.get("reading_speed_wpm", 0) < 150 else "steady pacing with enough engagement signals"
    return {
        "topic": material.title,
        "observed_score": round(normalized, 4),
        "predicted_score": predicted,
        "strengths_observed": strengths,
        "struggles_observed": struggles,
        "engagement_notes": f"completed {features.get('section_completion_rate', 0)} of sections, {features.get('hover_count', 0)} hovers, {rereads} re-read sections",
        "behavioral_summary": behavioral,
        "recommendation": "use step-through examples, short checks for understanding, and concrete visuals before abstract definitions",
    }


def normalize_entry(raw: dict[str, Any]) -> dict[str, Any]:
    entry = {key: raw.get(key) for key in PROFILE_KEYS}
    entry["strengths_observed"] = list(entry.get("strengths_observed") or [])
    entry["struggles_observed"] = list(entry.get("struggles_observed") or [])
    entry["observed_score"] = float(entry.get("observed_score") or 0.0)
    predicted = entry.get("predicted_score")
    entry["predicted_score"] = float(predicted) if predicted is not None else None
    for key in ["topic", "engagement_notes", "behavioral_summary", "recommendation"]:
        entry[key] = str(entry.get(key) or "")
    return entry


def parse_profile_entry_content(content: str) -> dict[str, Any]:
    stripped = content.strip()
    if stripped.startswith("```"):
        lines = stripped.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        stripped = "\n".join(lines).strip()
    if not stripped.startswith("{"):
        start = stripped.find("{")
        end = stripped.rfind("}")
        if start >= 0 and end > start:
            stripped = stripped[start : end + 1]
    return normalize_entry(json.loads(stripped))


def profile_text(entry: dict[str, Any]) -> str:
    return (
        f"Topic: {entry['topic']}. Observed score: {entry['observed_score']}. "
        f"Strengths: {', '.join(entry['strengths_observed'])}. "
        f"Struggles: {', '.join(entry['struggles_observed'])}. "
        f"Engagement: {entry['engagement_notes']}. "
        f"Behavior: {entry['behavioral_summary']}. "
        f"Recommendation: {entry['recommendation']}."
    )


async def generate_profile_entry(student_id: int, quiz_attempt_id: int, db: AsyncSession) -> StudentProfileEntry:
    attempt = await db.scalar(select(QuizAttempt).where(QuizAttempt.id == quiz_attempt_id))
    if attempt is None or attempt.student_id != student_id:
        raise ValueError("Quiz attempt not found for student")
    material = await db.scalar(select(Material).where(Material.id == attempt.material_id).options(selectinload(Material.sections)))
    if material is None:
        raise ValueError("Attempt material not found")
    session = None
    prediction = None
    if attempt.session_id:
        session = await db.scalar(select(TrackingSession).where(TrackingSession.id == attempt.session_id))
        prediction = await db.scalar(select(ScorePrediction).where(ScorePrediction.session_id == attempt.session_id))
    features = session.features if session and session.features else {}
    predicted = prediction.predicted_score if prediction else None
    prompt = build_entry_prompt(material, features, attempt.score, attempt.max_score, predicted)

    settings = get_settings()
    if settings.resolved_llm_provider != "deterministic":
        client = llm_client()
        response = await client.chat.completions.create(model=llm_model(), messages=[{"role": "user", "content": prompt}])
        content = response.choices[0].message.content or "{}"
        entry_json = parse_profile_entry_content(content)
    else:
        entry_json = deterministic_profile_entry(material, features, attempt.score, attempt.max_score, predicted)

    text = profile_text(entry_json)
    entry = StudentProfileEntry(
        user_id=student_id,
        profile_text=text,
        profile_json=entry_json,
        embedding=await embed_text(text),
        trigger_material_id=material.id,
        quiz_attempt_id=attempt.id,
        quiz_score=attempt.score / attempt.max_score if attempt.max_score else 0.0,
    )
    db.add(entry)
    await db.commit()
    await db.refresh(entry)
    return entry
