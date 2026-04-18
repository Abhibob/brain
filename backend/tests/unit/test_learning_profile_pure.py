from __future__ import annotations

from app.services.learning_profile import STYLE_AXES, render_style_summary
from app.services.profile_reasoning import _deterministic_reasoning, _normalize_reasoning


def test_style_axes_complete():
    assert set(STYLE_AXES) == {
        "pace",
        "depth",
        "attention_stability",
        "engagement_mode",
        "revisit_tendency",
        "visual_orientation",
        "motor_style",
    }


def test_render_style_summary_mentions_traits():
    snapshot = {
        "style_vector": {axis: 0.7 for axis in STYLE_AXES},
        "engagement_fingerprint": {
            "hover_heavy": 0.8,
            "selector": 0.7,
            "re_reader": 0.3,
            "back_scroller": 0.1,
            "skimmer": 0.0,
        },
        "behavioral_signals": {"recent_hints": ["keep sections short", "use examples"]},
    }
    lines = render_style_summary(snapshot)
    assert any("Traits" in line for line in lines)
    assert any("Recent guidance" in line for line in lines)


def test_deterministic_reasoning_clamps_and_shape():
    lesson = {"title": "Arrays", "topics": ["arrays", "indexing"]}
    focus = {
        "focus_score": 0.35,
        "label": "distracted",
        "breakdown": {"pace": 0.3, "completion": 0.4, "attention": 0.3, "engagement": 0.3},
    }
    section_focus = [
        {"section_id": 1, "label": "distracted", "focus_score": 0.3, "breakdown": {"re_read_count": 0}},
    ]
    snapshot = {
        "style_vector": {axis: 0.5 for axis in STYLE_AXES},
    }
    reasoning = _normalize_reasoning(_deterministic_reasoning(lesson, focus, section_focus, snapshot))
    assert set(reasoning["style_vector_delta"]) == set(STYLE_AXES)
    for value in reasoning["style_vector_delta"].values():
        assert -0.15 <= value <= 0.15
    assert reasoning["style_narrative"]
    assert isinstance(reasoning["lesson_plan_hints"], list)
    assert reasoning["per_topic_insights"]


def test_normalize_reasoning_drops_unknown_axes_and_non_bool_prefs():
    raw = {
        "style_vector_delta": {"pace": 0.5, "unknown_axis": 1.0, "depth": "nope"},
        "content_preferences": {"likes_videos": True, "rating": 5},
        "lesson_plan_hints": ["use one"],
    }
    cleaned = _normalize_reasoning(raw)
    assert cleaned["style_vector_delta"]["pace"] == 0.15  # clamped
    assert "unknown_axis" not in cleaned["style_vector_delta"]
    assert cleaned["style_vector_delta"]["depth"] == 0.0
    assert cleaned["content_preferences"] == {"likes_videos": True}
