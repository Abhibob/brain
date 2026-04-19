from app.services.focus import compute_focus_score
from app.services.gaze import extract_gaze_features


def _fixation(section_id: str | None, duration_ms: float, rel_x: float = 0.5, rel_y: float = 0.5, confidence: float = 0.8):
    return {
        "event_type": "gaze_fixation",
        "event_data": {
            "section_id": section_id,
            "duration_ms": duration_ms,
            "rel_x": rel_x,
            "rel_y": rel_y,
            "confidence": confidence,
        },
    }


def test_returns_none_without_gaze_events():
    events = [
        {"event_type": "section_view", "event_data": {"section_id": "1"}},
        {"event_type": "mouse_move", "event_data": {"velocity": 0.1}},
    ]
    assert extract_gaze_features(events, total_time_s=60) is None


def test_counts_fixations_and_sections():
    events = [
        {"event_type": "gaze_calibrated", "event_data": {"points": 9, "has_calibration": True}},
        _fixation("1", 500),
        _fixation("1", 700),
        _fixation("2", 300),
        _fixation(None, 200),
        {"event_type": "gaze_lost", "event_data": {"duration_ms": 2000, "reason": "no_face"}},
    ]
    features = extract_gaze_features(events, total_time_s=60)
    assert features is not None
    assert features["gaze_present"] is True
    assert features["gaze_has_calibration"] is True
    assert features["gaze_fixation_count"] == 4
    assert features["gaze_reading_time_s"] == 1.5  # 500 + 700 + 300
    assert features["gaze_off_content_time_s"] == 0.2
    assert features["gaze_lost_s"] == 2.0
    assert round(features["gaze_lost_pct"], 4) == round(2.0 / 60, 4)
    assert features["gaze_time_per_section"] == {"1": 1.2, "2": 0.3}
    assert features["gaze_fixations_per_section"] == {"1": 2, "2": 1}
    assert "1" in features["gaze_heatmap"] and len(features["gaze_heatmap"]["1"]) == 2


def test_entropy_is_low_for_focused_reading():
    # All fixations on one section → entropy 0 (perfectly focused)
    events = [_fixation("1", 800) for _ in range(5)]
    features = extract_gaze_features(events, total_time_s=30)
    assert features is not None
    assert features["gaze_entropy"] == 0.0


def test_entropy_is_high_for_scattered_gaze():
    # Equal time across 4 sections → entropy = 1 (maximal scatter)
    events = [_fixation(str(i), 400) for i in range(1, 5)]
    features = extract_gaze_features(events, total_time_s=30)
    assert features is not None
    assert features["gaze_entropy"] > 0.99  # close to 1.0


def test_focus_score_uses_gaze_when_present():
    # Session where the student stared at the screen the whole time,
    # gaze confirms reading, no loss.
    focused_features = {
        "total_time_s": 60,
        "section_completion_rate": 0.9,
        "reading_speed_wpm": 180,
        "idle_total_s": 0,
        "idle_count": 0,
        "mouse_velocity_variance": 0,
        "back_scroll_count": 0,
        "hover_count": 5,
        "text_selection_count": 0,
        "re_read_sections": [],
        # Gaze signal
        "gaze_present": True,
        "gaze_reading_time_s": 54,  # 90% of the time
        "gaze_lost_pct": 0.05,
        "gaze_entropy": 0.3,
        "gaze_fixation_count": 80,
        "gaze_has_calibration": True,
    }
    result = compute_focus_score(focused_features)
    assert result["attention_source"] == "gaze"
    assert result["focus_score"] > 0.75
    assert result["label"] in {"focused", "engaged"}
    # Confidence should be higher with gaze data.
    assert result["confidence"] >= 0.7


def test_focus_label_turns_distracted_when_gaze_lost():
    # Student looked away from screen for half the session — even though other
    # signals look OK, gaze truth wins.
    features = {
        "total_time_s": 120,
        "section_completion_rate": 0.85,
        "reading_speed_wpm": 200,
        "idle_total_s": 10,
        "idle_count": 1,
        "mouse_velocity_variance": 0,
        "back_scroll_count": 0,
        "hover_count": 3,
        "text_selection_count": 0,
        "re_read_sections": [],
        "gaze_present": True,
        "gaze_reading_time_s": 60,
        "gaze_lost_pct": 0.5,  # major loss
        "gaze_entropy": 0.4,
        "gaze_fixation_count": 40,
    }
    result = compute_focus_score(features)
    assert result["label"] in {"distracted", "abandoned"}


def test_focus_score_falls_back_to_heuristic_without_gaze():
    # No gaze flags → should use heuristic attention path, no crash.
    features = {
        "total_time_s": 60,
        "section_completion_rate": 0.8,
        "reading_speed_wpm": 180,
        "idle_total_s": 0,
        "idle_count": 0,
        "mouse_velocity_variance": 0,
        "back_scroll_count": 0,
        "hover_count": 5,
        "text_selection_count": 0,
        "re_read_sections": [],
    }
    result = compute_focus_score(features)
    assert result["attention_source"] == "heuristic"
    assert 0 <= result["focus_score"] <= 1
