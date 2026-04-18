from __future__ import annotations

import pytest

from app.services.focus import compute_focus_score, compute_section_focus


def _focused_features() -> dict:
    return {
        "total_time_s": 180,
        "reading_speed_wpm": 200,
        "section_completion_rate": 0.95,
        "hover_count": 4,
        "mouse_velocity_variance": 5.0,
        "idle_total_s": 5,
        "back_scroll_count": 1,
        "text_selection_count": 2,
        "re_read_sections": ["1"],
    }


def _distracted_features() -> dict:
    return {
        "total_time_s": 200,
        "reading_speed_wpm": 550,
        "section_completion_rate": 0.3,
        "hover_count": 0,
        "mouse_velocity_variance": 300,
        "idle_total_s": 110,
        "back_scroll_count": 15,
        "text_selection_count": 0,
        "re_read_sections": [],
    }


def test_focused_session_scores_high():
    result = compute_focus_score(_focused_features())
    assert 0 <= result["focus_score"] <= 1
    assert result["focus_score"] > 0.7
    assert result["label"] in {"focused", "engaged"}
    assert set(result["breakdown"]) == {"pace", "completion", "attention", "engagement"}


def test_distracted_session_scores_low_and_labels_distracted_or_skimming():
    result = compute_focus_score(_distracted_features())
    assert result["focus_score"] < 0.55
    assert result["label"] in {"distracted", "skimming", "abandoned"}


def test_abandoned_when_total_time_very_short():
    features = {"total_time_s": 4, "section_completion_rate": 0.1}
    result = compute_focus_score(features)
    assert result["label"] == "abandoned"


def test_empty_features_is_safe():
    result = compute_focus_score({})
    assert 0 <= result["focus_score"] <= 1
    assert "label" in result


def test_section_focus_scores_focused_section_higher_than_distracted():
    events = [
        {"event_type": "mouse_move", "event_data": {"section_id": "1", "velocity": 0.2}},
        {"event_type": "mouse_move", "event_data": {"section_id": "1", "velocity": 0.25}},
        {"event_type": "hover_end", "event_data": {"section_id": "1", "duration_ms": 900}},
        {"event_type": "text_select", "event_data": {"section_id": "1", "char_count": 20}},
        {"event_type": "idle_end", "event_data": {"section_id": "2", "duration_ms": 45000}},
        {"event_type": "mouse_move", "event_data": {"section_id": "2", "velocity": 4.0}},
        {"event_type": "mouse_move", "event_data": {"section_id": "2", "velocity": 8.0}},
    ]
    section_meta = [
        {"section_id": 1, "word_count": 80, "title": "Base"},
        {"section_id": 2, "word_count": 80, "title": "Recursive"},
    ]
    section_times = {"1": 30.0, "2": 50.0}
    view_counts = {"1": 2, "2": 1}
    rows = compute_section_focus(events, section_meta, section_times, view_counts)
    assert len(rows) == 2
    by_id = {row["section_id"]: row for row in rows}
    assert by_id[1]["focus_score"] > by_id[2]["focus_score"]
    assert by_id[1]["breakdown"]["re_read_count"] == 1
    assert by_id[2]["breakdown"]["idle_ratio"] > 0
