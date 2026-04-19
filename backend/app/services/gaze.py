"""Gaze feature extraction.

Translates raw `gaze_fixation`, `gaze_lost`, and `gaze_calibrated` events into
session-level features that feed the focus scorer, researcher heatmaps, and the
learning profile update pipeline.

Gaze is treated as an optional signal: if no gaze events are present the
extractor returns None so upstream code can fall back to the heuristic
attention model.
"""

from __future__ import annotations

from collections import defaultdict
from math import log2
from statistics import mean, median
from typing import Any

GAZE_EVENT_TYPES = {"gaze_fixation", "gaze_lost", "gaze_calibrated"}


def _numeric(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _as_section_id(raw: Any) -> str | None:
    if raw is None:
        return None
    text = str(raw).strip()
    if not text or text.lower() in {"none", "null", "undefined"}:
        return None
    return text


def extract_gaze_features(
    events: list[dict[str, Any]],
    total_time_s: float,
) -> dict[str, Any] | None:
    """Compute gaze features for a session.

    Returns None when no gaze-related events are in the stream so that callers
    can differentiate "no camera" from "camera but zero attention".
    """
    fixations: list[dict[str, Any]] = []
    loss_ms = 0.0
    has_calibration = False
    gaze_present = False

    for event in events:
        event_type = event.get("event_type")
        if event_type not in GAZE_EVENT_TYPES:
            continue
        gaze_present = True
        data = event.get("event_data") or {}
        if event_type == "gaze_fixation":
            fixations.append(data)
        elif event_type == "gaze_lost":
            loss_ms += _numeric(data.get("duration_ms"))
        elif event_type == "gaze_calibrated":
            has_calibration = bool(data.get("has_calibration"))

    if not gaze_present:
        return None

    total_fixation_ms = 0.0
    reading_time_ms = 0.0
    off_content_ms = 0.0
    durations: list[float] = []
    fixations_per_section: dict[str, int] = defaultdict(int)
    time_per_section_ms: dict[str, float] = defaultdict(float)
    heatmap: dict[str, list[dict[str, Any]]] = defaultdict(list)

    for fixation in fixations:
        duration = _numeric(fixation.get("duration_ms"))
        if duration <= 0:
            continue
        durations.append(duration)
        total_fixation_ms += duration
        section_id = _as_section_id(fixation.get("section_id"))
        if section_id is not None:
            reading_time_ms += duration
            fixations_per_section[section_id] += 1
            time_per_section_ms[section_id] += duration
            heatmap[section_id].append(
                {
                    "rel_x": round(_numeric(fixation.get("rel_x")), 4),
                    "rel_y": round(_numeric(fixation.get("rel_y")), 4),
                    "weight": round(duration / 1000.0, 3),
                    "confidence": round(_numeric(fixation.get("confidence")), 3),
                }
            )
        else:
            off_content_ms += duration

    entropy = _normalized_entropy(list(time_per_section_ms.values()))
    lost_s = loss_ms / 1000.0
    denom = max(total_time_s, 1.0)
    lost_pct = min(lost_s / denom, 1.0)

    return {
        "gaze_present": True,
        "gaze_has_calibration": has_calibration,
        "gaze_reading_time_s": round(reading_time_ms / 1000.0, 3),
        "gaze_off_content_time_s": round(off_content_ms / 1000.0, 3),
        "gaze_lost_s": round(lost_s, 3),
        "gaze_lost_pct": round(lost_pct, 4),
        "gaze_fixation_count": len(durations),
        "gaze_fixation_ms_mean": round(mean(durations), 2) if durations else 0.0,
        "gaze_fixation_ms_median": round(median(durations), 2) if durations else 0.0,
        "gaze_entropy": round(entropy, 4),
        "gaze_time_per_section": {k: round(v / 1000.0, 3) for k, v in time_per_section_ms.items()},
        "gaze_fixations_per_section": dict(fixations_per_section),
        "gaze_heatmap": {k: v for k, v in heatmap.items()},
    }


def _normalized_entropy(values: list[float]) -> float:
    """Shannon entropy of the distribution, normalized to [0, 1].

    Low entropy means gaze concentrated on one section (focused).
    High entropy means gaze scattered across many sections (skimming / confused).
    """
    total = sum(values)
    if len(values) <= 1 or total <= 0:
        return 0.0
    probs = [v / total for v in values if v > 0]
    if len(probs) <= 1:
        return 0.0
    raw = -sum(p * log2(p) for p in probs)
    max_raw = log2(len(probs))
    return raw / max_raw if max_raw > 0 else 0.0
