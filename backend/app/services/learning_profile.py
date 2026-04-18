from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    StudentProfileEntry,
    TopicMasteryEdge,
    TopicMasteryNode,
    TrackingSession,
    UserLearningProfile,
)
from app.services.rag import embed_text

ALPHA = 0.25
STYLE_AXES = (
    "pace",
    "depth",
    "attention_stability",
    "engagement_mode",
    "revisit_tendency",
    "visual_orientation",
    "motor_style",
)


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def _ema(current: float | None, observed: float, alpha: float = ALPHA) -> float:
    if current is None or current == 0:
        return round(observed, 4)
    return round(alpha * observed + (1 - alpha) * current, 4)


def _default_style_vector() -> dict[str, float]:
    return {axis: 0.5 for axis in STYLE_AXES}


def _default_fingerprint() -> dict[str, Any]:
    return {
        "hover_heavy": 0.0,
        "selector": 0.0,
        "re_reader": 0.0,
        "back_scroller": 0.0,
        "skimmer": 0.0,
        "session_samples": 0,
    }


def _default_behavioral_signals() -> dict[str, Any]:
    return {
        "narrative_notes": [],
        "content_preferences": {},
        "recent_hints": [],
    }


def _observed_style_from_features(features: dict[str, Any], focus: dict[str, Any]) -> dict[str, float]:
    wpm = float(features.get("reading_speed_wpm") or 0.0)
    pace = _clamp(wpm / 280) if wpm else 0.4
    completion = float(features.get("section_completion_rate") or 0.0)
    total_time = max(float(features.get("total_time_s") or 1.0), 1.0)
    idle_ratio = float(features.get("idle_total_s") or 0.0) / total_time
    rereads = len(features.get("re_read_sections") or [])
    hover_count = float(features.get("hover_count") or 0.0)
    selections = float(features.get("text_selection_count") or 0.0)
    back_scroll = float(features.get("back_scroll_count") or 0.0)
    attention_stability = _clamp(1.0 - min(idle_ratio * 1.5, 0.8))
    depth = _clamp(completion * 0.6 + min(rereads / 3, 0.3) + min(selections / 4, 0.2))
    engagement_mode = _clamp(0.2 + min(hover_count / 10, 0.4) + min(selections / 4, 0.3) + min(rereads / 3, 0.2))
    revisit_tendency = _clamp(min(rereads / 3, 0.7) + min(back_scroll / 15, 0.3))
    visual_orientation = _clamp(0.3 + min(hover_count / 8, 0.6))
    motor_style = _clamp(0.2 + min(hover_count / 8, 0.6) - min(back_scroll / 10, 0.2))
    return {
        "pace": pace,
        "depth": depth,
        "attention_stability": attention_stability,
        "engagement_mode": engagement_mode,
        "revisit_tendency": revisit_tendency,
        "visual_orientation": visual_orientation,
        "motor_style": motor_style,
    }


def _observed_fingerprint(features: dict[str, Any], focus: dict[str, Any]) -> dict[str, float]:
    hover_count = float(features.get("hover_count") or 0.0)
    selections = float(features.get("text_selection_count") or 0.0)
    rereads = len(features.get("re_read_sections") or [])
    back_scroll = float(features.get("back_scroll_count") or 0.0)
    label = focus.get("label")
    return {
        "hover_heavy": 1.0 if hover_count >= 6 else min(hover_count / 6, 1.0),
        "selector": 1.0 if selections >= 2 else min(selections / 2, 1.0),
        "re_reader": 1.0 if rereads >= 2 else min(rereads / 2, 1.0),
        "back_scroller": 1.0 if back_scroll >= 5 else min(back_scroll / 5, 1.0),
        "skimmer": 1.0 if label == "skimming" else 0.2 if label == "distracted" else 0.0,
    }


def _update_time_of_day(current: dict[str, Any], started_at: datetime | None) -> dict[str, Any]:
    if started_at is None:
        return current
    hour = str(started_at.hour)
    histogram = dict(current.get("histogram") or {})
    histogram[hour] = histogram.get(hour, 0) + 1
    top_hour = max(histogram.items(), key=lambda item: item[1])[0] if histogram else None
    return {"histogram": histogram, "peak_hour": top_hour}


async def get_or_create_profile(user_id: int, db: AsyncSession) -> UserLearningProfile:
    profile = await db.scalar(select(UserLearningProfile).where(UserLearningProfile.user_id == user_id))
    if profile is not None:
        return profile
    profile = UserLearningProfile(
        user_id=user_id,
        style_vector=_default_style_vector(),
        rolling_focus_score=0.5,
        rolling_reading_speed_wpm=0.0,
        rolling_completion_rate=0.0,
        preferred_session_length_s=0.0,
        peak_focus_time_of_day={"histogram": {}, "peak_hour": None},
        engagement_fingerprint=_default_fingerprint(),
        behavioral_signals=_default_behavioral_signals(),
    )
    db.add(profile)
    await db.flush()
    return profile


async def upsert_from_session(
    db: AsyncSession,
    session: TrackingSession,
    features: dict[str, Any],
    focus: dict[str, Any],
    topics: list[str],
) -> UserLearningProfile:
    profile = await get_or_create_profile(session.student_id, db)
    observed_style = _observed_style_from_features(features, focus)
    new_vector = dict(profile.style_vector or _default_style_vector())
    for axis in STYLE_AXES:
        new_vector[axis] = _clamp(_ema(float(new_vector.get(axis, 0.5)), observed_style[axis]))
    profile.style_vector = new_vector

    profile.rolling_focus_score = _ema(profile.rolling_focus_score, float(focus.get("focus_score", 0.5)))
    wpm = float(features.get("reading_speed_wpm") or 0.0)
    if wpm > 0:
        profile.rolling_reading_speed_wpm = _ema(profile.rolling_reading_speed_wpm, wpm)
    profile.rolling_completion_rate = _ema(profile.rolling_completion_rate, float(features.get("section_completion_rate") or 0.0))
    total_time = float(features.get("total_time_s") or 0.0)
    if total_time > 0:
        profile.preferred_session_length_s = _ema(profile.preferred_session_length_s, total_time)

    observed_fingerprint = _observed_fingerprint(features, focus)
    new_fp = dict(profile.engagement_fingerprint or _default_fingerprint())
    for key, value in observed_fingerprint.items():
        new_fp[key] = _ema(float(new_fp.get(key, 0.0)), value)
    new_fp["session_samples"] = int(new_fp.get("session_samples", 0)) + 1
    profile.engagement_fingerprint = new_fp

    profile.peak_focus_time_of_day = _update_time_of_day(profile.peak_focus_time_of_day or {}, session.started_at)
    profile.last_focus_label = focus.get("label")
    profile.session_count = (profile.session_count or 0) + 1
    profile.lesson_count = (profile.lesson_count or 0) + 1
    profile.last_updated_at = datetime.now(UTC)

    await _upsert_topic_nodes_from_session(
        db,
        user_id=session.student_id,
        topics=topics,
        focus_score=float(focus.get("focus_score", 0.5)),
    )
    await _upsert_topic_cooccurrence(db, user_id=session.student_id, topics=topics)
    await db.flush()
    return profile


async def upsert_from_quiz_entry(
    db: AsyncSession,
    entry: StudentProfileEntry,
    topics: list[str],
) -> UserLearningProfile:
    profile = await get_or_create_profile(entry.user_id, db)
    profile.quiz_count = (profile.quiz_count or 0) + 1
    profile.last_updated_at = datetime.now(UTC)

    quiz_score = float(entry.quiz_score) if entry.quiz_score is not None else None
    if quiz_score is not None:
        for topic in topics:
            node = await _get_or_create_topic_node(db, entry.user_id, topic)
            node.mastery_score = _ema(node.mastery_score, quiz_score)
            node.quiz_sample_count = (node.quiz_sample_count or 0) + 1
            if quiz_score >= 0.75:
                node.strength_signal = _ema(node.strength_signal, quiz_score)
            if quiz_score < 0.6:
                node.struggle_signal = _ema(node.struggle_signal, 1.0 - quiz_score)
            node.last_seen_at = datetime.now(UTC)
    await db.flush()
    return profile


async def apply_style_delta(
    db: AsyncSession,
    user_id: int,
    delta: dict[str, Any],
) -> UserLearningProfile:
    profile = await get_or_create_profile(user_id, db)
    vector = dict(profile.style_vector or _default_style_vector())
    for axis, change in (delta.get("style_vector_delta") or {}).items():
        if axis not in STYLE_AXES:
            continue
        try:
            shift = float(change)
        except (TypeError, ValueError):
            continue
        vector[axis] = _clamp(float(vector.get(axis, 0.5)) + shift)
    profile.style_vector = vector

    signals = dict(profile.behavioral_signals or _default_behavioral_signals())
    narrative = delta.get("style_narrative")
    if narrative:
        notes = list(signals.get("narrative_notes") or [])
        notes.append({"note": str(narrative), "ts": datetime.now(UTC).isoformat()})
        signals["narrative_notes"] = notes[-10:]
    prefs = delta.get("content_preferences") or {}
    if isinstance(prefs, dict):
        current_prefs = dict(signals.get("content_preferences") or {})
        for key, value in prefs.items():
            if isinstance(value, bool):
                observed = 1.0 if value else 0.0
                current_prefs[key] = _ema(float(current_prefs.get(key, 0.5)), observed)
        signals["content_preferences"] = current_prefs
    hints = delta.get("lesson_plan_hints") or []
    if isinstance(hints, list) and hints:
        existing = list(signals.get("recent_hints") or [])
        for hint in hints:
            if isinstance(hint, str) and hint.strip():
                existing.append(hint.strip())
        signals["recent_hints"] = existing[-5:]
    profile.behavioral_signals = signals
    profile.last_updated_at = datetime.now(UTC)
    await db.flush()
    return profile


async def _get_or_create_topic_node(db: AsyncSession, user_id: int, topic: str) -> TopicMasteryNode:
    node = await db.scalar(
        select(TopicMasteryNode).where(
            TopicMasteryNode.user_id == user_id,
            TopicMasteryNode.topic == topic,
        )
    )
    if node is None:
        node = TopicMasteryNode(
            user_id=user_id,
            topic=topic,
            mastery_score=0.5,
            exposure_score=0.5,
            encounter_count=0,
            quiz_sample_count=0,
            struggle_signal=0.0,
            strength_signal=0.0,
            embedding=await embed_text(topic),
        )
        db.add(node)
        await db.flush()
    return node


async def _upsert_topic_nodes_from_session(
    db: AsyncSession,
    *,
    user_id: int,
    topics: list[str],
    focus_score: float,
) -> None:
    for topic in topics:
        node = await _get_or_create_topic_node(db, user_id, topic)
        node.exposure_score = _ema(node.exposure_score, focus_score)
        node.encounter_count = (node.encounter_count or 0) + 1
        node.last_seen_at = datetime.now(UTC)


async def _upsert_topic_cooccurrence(db: AsyncSession, *, user_id: int, topics: list[str]) -> None:
    if len(topics) < 2:
        return
    for i, first in enumerate(topics):
        for second in topics[i + 1 :]:
            for from_t, to_t in ((first, second), (second, first)):
                edge = await db.scalar(
                    select(TopicMasteryEdge).where(
                        TopicMasteryEdge.user_id == user_id,
                        TopicMasteryEdge.from_topic == from_t,
                        TopicMasteryEdge.to_topic == to_t,
                        TopicMasteryEdge.relation == "co_occurred",
                    )
                )
                if edge is None:
                    edge = TopicMasteryEdge(
                        user_id=user_id,
                        from_topic=from_t,
                        to_topic=to_t,
                        relation="co_occurred",
                        weight=1.0,
                    )
                    db.add(edge)
                else:
                    edge.weight = round(edge.weight + 1.0, 4)
                    edge.last_seen_at = datetime.now(UTC)


async def get_profile_snapshot(user_id: int, db: AsyncSession, *, top_k: int = 5) -> dict[str, Any]:
    profile = await db.scalar(select(UserLearningProfile).where(UserLearningProfile.user_id == user_id))
    if profile is None:
        return {
            "style_vector": _default_style_vector(),
            "rolling_focus_score": 0.5,
            "engagement_fingerprint": _default_fingerprint(),
            "behavioral_signals": _default_behavioral_signals(),
            "top_mastery": [],
            "top_struggles": [],
        }
    nodes = (
        await db.scalars(
            select(TopicMasteryNode)
            .where(TopicMasteryNode.user_id == user_id)
            .order_by(TopicMasteryNode.encounter_count.desc(), TopicMasteryNode.last_seen_at.desc())
            .limit(20)
        )
    ).all()
    by_mastery = sorted(nodes, key=lambda n: n.mastery_score, reverse=True)[:top_k]
    by_struggle = sorted(nodes, key=lambda n: n.struggle_signal, reverse=True)[:top_k]
    return {
        "style_vector": profile.style_vector or _default_style_vector(),
        "rolling_focus_score": profile.rolling_focus_score,
        "rolling_reading_speed_wpm": profile.rolling_reading_speed_wpm,
        "rolling_completion_rate": profile.rolling_completion_rate,
        "preferred_session_length_s": profile.preferred_session_length_s,
        "engagement_fingerprint": profile.engagement_fingerprint or _default_fingerprint(),
        "behavioral_signals": profile.behavioral_signals or _default_behavioral_signals(),
        "last_focus_label": profile.last_focus_label,
        "peak_focus_time_of_day": profile.peak_focus_time_of_day or {"histogram": {}, "peak_hour": None},
        "session_count": profile.session_count,
        "lesson_count": profile.lesson_count,
        "quiz_count": profile.quiz_count,
        "top_mastery": [
            {"topic": n.topic, "mastery_score": n.mastery_score, "exposure_score": n.exposure_score, "encounter_count": n.encounter_count}
            for n in by_mastery
        ],
        "top_struggles": [
            {"topic": n.topic, "mastery_score": n.mastery_score, "struggle_signal": n.struggle_signal}
            for n in by_struggle
            if n.struggle_signal > 0
        ],
    }


def render_style_summary(snapshot: dict[str, Any]) -> list[str]:
    vector = snapshot.get("style_vector") or {}
    lines: list[str] = []
    pace = float(vector.get("pace", 0.5))
    depth = float(vector.get("depth", 0.5))
    stability = float(vector.get("attention_stability", 0.5))
    engagement = float(vector.get("engagement_mode", 0.5))
    revisit = float(vector.get("revisit_tendency", 0.5))
    visual = float(vector.get("visual_orientation", 0.5))
    lines.append(f"Pace: {'fast' if pace > 0.66 else 'slow' if pace < 0.33 else 'moderate'} ({pace:.2f}).")
    lines.append(f"Depth: {'deep' if depth > 0.66 else 'skim' if depth < 0.33 else 'mixed'} ({depth:.2f}).")
    lines.append(f"Attention stability: {stability:.2f}. Engagement mode: {engagement:.2f}.")
    lines.append(f"Revisit tendency: {revisit:.2f}. Visual orientation: {visual:.2f}.")
    fp = snapshot.get("engagement_fingerprint") or {}
    traits = [name for name in ("hover_heavy", "selector", "re_reader", "back_scroller", "skimmer") if float(fp.get(name, 0)) > 0.5]
    if traits:
        lines.append("Traits: " + ", ".join(traits) + ".")
    hints = (snapshot.get("behavioral_signals") or {}).get("recent_hints") or []
    if hints:
        lines.append("Recent guidance: " + "; ".join(hints[-3:]) + ".")
    return lines
