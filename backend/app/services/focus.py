from __future__ import annotations

from collections import defaultdict
from statistics import mean, variance
from typing import Any

FOCUS_LABELS = ("focused", "engaged", "distracted", "skimming", "abandoned")
SECTION_LABELS = ("focused", "skimmed", "distracted")


def clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def _numeric(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _pace_component(features: dict[str, Any]) -> float:
    wpm = _numeric(features.get("reading_speed_wpm"))
    if wpm == 0:
        return 0.3
    if 140 <= wpm <= 240:
        return 1.0
    if 100 <= wpm < 140 or 240 < wpm <= 300:
        return 0.75
    if 60 <= wpm < 100 or 300 < wpm <= 400:
        return 0.5
    return 0.25


def _completion_component(features: dict[str, Any]) -> float:
    return clamp(_numeric(features.get("section_completion_rate")))


def _attention_component(features: dict[str, Any]) -> float:
    total_time = max(_numeric(features.get("total_time_s")), 1.0)
    idle_ratio = _numeric(features.get("idle_total_s")) / total_time
    variance_val = _numeric(features.get("mouse_velocity_variance"))
    back_scroll = _numeric(features.get("back_scroll_count"))
    score = 1.0
    score -= min(idle_ratio * 1.5, 0.6)
    if variance_val > 50:
        score -= min((variance_val - 50) / 400, 0.35)
    if back_scroll > 8:
        score -= min((back_scroll - 8) / 20, 0.25)
    return clamp(score)


def _gaze_attention_component(features: dict[str, Any]) -> float | None:
    """Return a gaze-derived attention score, or None when gaze data is absent.

    Much stronger signal than the heuristic: reading_ratio is literally "time
    the eyes were on content" divided by session duration.
    """
    if not features.get("gaze_present"):
        return None
    total_time = max(_numeric(features.get("total_time_s")), 1.0)
    reading_time = _numeric(features.get("gaze_reading_time_s"))
    lost_pct = _numeric(features.get("gaze_lost_pct"))
    entropy = _numeric(features.get("gaze_entropy"))
    reading_ratio = clamp(reading_time / total_time)
    score = reading_ratio
    score -= min(lost_pct * 1.25, 0.5)
    # Scattered gaze (high entropy) indicates skimming/confusion — light penalty.
    if entropy > 0.7:
        score -= min((entropy - 0.7) * 0.6, 0.2)
    return clamp(score)


def _engagement_component(features: dict[str, Any]) -> float:
    hover_count = _numeric(features.get("hover_count"))
    selections = _numeric(features.get("text_selection_count"))
    rereads = len(features.get("re_read_sections") or [])
    score = 0.3
    score += min(hover_count / 15, 0.3)
    score += min(selections / 4, 0.2)
    score += min(rereads / 3, 0.2)
    return clamp(score)


def _label_for(score: float, features: dict[str, Any]) -> str:
    total_time = _numeric(features.get("total_time_s"))
    completion = _numeric(features.get("section_completion_rate"))
    # When gaze is present, trust its loss/reading-ratio signals for sharper labels.
    if features.get("gaze_present"):
        lost_pct = _numeric(features.get("gaze_lost_pct"))
        reading_time = _numeric(features.get("gaze_reading_time_s"))
        reading_ratio = reading_time / max(total_time, 1.0)
        if lost_pct >= 0.5 or (reading_ratio < 0.15 and total_time < 30):
            return "abandoned"
        if lost_pct >= 0.3:
            return "distracted"
    if total_time < 8 or (completion < 0.15 and total_time < 30):
        return "abandoned"
    if score >= 0.78:
        return "focused"
    if score >= 0.6:
        return "engaged"
    if completion < 0.5 and total_time < 60:
        return "skimming"
    return "distracted"


def compute_focus_score(features: dict[str, Any] | None) -> dict[str, Any]:
    features = features or {}
    pace = _pace_component(features)
    completion = _completion_component(features)
    gaze_attn = _gaze_attention_component(features)
    heuristic_attn = _attention_component(features)
    attention = gaze_attn if gaze_attn is not None else heuristic_attn
    engagement = _engagement_component(features)

    focus = 0.25 * pace + 0.30 * completion + 0.30 * attention + 0.15 * engagement
    focus = round(clamp(focus), 4)
    total_time = _numeric(features.get("total_time_s"))
    sample_signal = clamp(total_time / 120)
    base_confidence = 0.3 + 0.5 * sample_signal + 0.2 * min(_numeric(features.get("hover_count")) / 10, 1.0)
    if features.get("gaze_present"):
        # Gaze signal is much richer; boost confidence when it's available.
        fix_count = _numeric(features.get("gaze_fixation_count"))
        base_confidence += 0.2 * clamp(fix_count / 30)
    confidence = round(clamp(base_confidence), 4)
    label = _label_for(focus, features)
    return {
        "focus_score": focus,
        "confidence": confidence,
        "breakdown": {
            "pace": round(pace, 4),
            "completion": round(completion, 4),
            "attention": round(attention, 4),
            "engagement": round(engagement, 4),
        },
        "attention_source": "gaze" if gaze_attn is not None else "heuristic",
        "label": label,
    }


def _section_attention(events: list[dict[str, Any]], total_time_s: float) -> tuple[float, float, int, float]:
    idle_ms = 0.0
    mouse_velocities: list[float] = []
    hover_count = 0
    text_selections = 0
    for event in events:
        event_type = event.get("event_type")
        data = event.get("event_data") or {}
        if event_type == "idle_end":
            idle_ms += _numeric(data.get("duration") or data.get("duration_ms"))
        elif event_type == "mouse_move":
            mouse_velocities.append(abs(_numeric(data.get("velocity"))))
        elif event_type in {"hover_end", "hover"}:
            hover_count += 1
        elif event_type == "text_select" and _numeric(data.get("char_count")) > 0:
            text_selections += 1
    idle_ratio = (idle_ms / 1000) / max(total_time_s, 1.0)
    variance_val = variance(mouse_velocities) if len(mouse_velocities) > 1 else 0.0
    return idle_ratio, variance_val, hover_count + text_selections, _numeric_safe_mean(mouse_velocities)


def _numeric_safe_mean(values: list[float]) -> float:
    return mean(values) if values else 0.0


def compute_section_focus(
    events: list[dict[str, Any]],
    section_meta: list[dict[str, Any]],
    section_times: dict[str, float],
    section_view_counts: dict[str, int],
) -> list[dict[str, Any]]:
    """Return per-section focus rows.

    section_meta: list of {"section_id": int, "word_count": int, "title": str}
    section_times: seconds spent per section (keyed by str(section_id))
    section_view_counts: how many times each section was viewed (re-read tracking)
    """
    by_section: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for event in events:
        data = event.get("event_data") or {}
        sid = data.get("section_id") or data.get("sectionId")
        if sid is None:
            continue
        by_section[str(sid)].append(event)

    results: list[dict[str, Any]] = []
    for meta in section_meta:
        sid_int = int(meta["section_id"])
        sid = str(sid_int)
        time_s = _numeric(section_times.get(sid))
        if time_s <= 0 and not by_section.get(sid):
            continue
        events_for = by_section.get(sid, [])
        idle_ratio, variance_val, engagement_events, avg_mouse = _section_attention(events_for, time_s)

        words = _numeric(meta.get("word_count"))
        expected_time = (words / 200) * 60 if words else 0.0
        if expected_time > 0:
            ratio = time_s / expected_time
            if 0.6 <= ratio <= 1.6:
                pace = 1.0
            elif ratio < 0.6:
                pace = clamp(ratio / 0.6)
            else:
                pace = clamp(1.0 - (ratio - 1.6) / 3)
        else:
            pace = 0.6 if time_s > 5 else 0.3

        attention = 1.0 - min(idle_ratio * 1.5, 0.7)
        if variance_val > 50:
            attention -= min((variance_val - 50) / 400, 0.3)
        attention = clamp(attention)

        engagement = clamp(0.2 + min(engagement_events / 6, 0.6) + min((section_view_counts.get(sid, 1) - 1) / 3, 0.2))

        focus = 0.35 * pace + 0.4 * attention + 0.25 * engagement
        focus = round(clamp(focus), 4)
        if time_s < 3 and pace < 0.4:
            label = "distracted"
        elif pace < 0.4 and attention < 0.5:
            label = "skimmed"
        elif focus >= 0.65:
            label = "focused"
        elif focus >= 0.45:
            label = "skimmed"
        else:
            label = "distracted"

        results.append(
            {
                "section_id": sid_int,
                "focus_score": focus,
                "breakdown": {
                    "pace": round(pace, 4),
                    "attention": round(attention, 4),
                    "engagement": round(engagement, 4),
                    "time_s": round(time_s, 3),
                    "idle_ratio": round(idle_ratio, 4),
                    "mouse_variance": round(variance_val, 4),
                    "avg_mouse_velocity": round(avg_mouse, 4),
                    "re_read_count": max(section_view_counts.get(sid, 1) - 1, 0),
                },
                "label": label,
            }
        )
    return results
