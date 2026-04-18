from __future__ import annotations

from app.services.asset_scoring import score_asset_for_student


def _snapshot(**style) -> dict:
    return {
        "style_vector": {
            "pace": 0.5,
            "depth": 0.5,
            "attention_stability": 0.5,
            "engagement_mode": 0.5,
            "revisit_tendency": 0.5,
            "visual_orientation": 0.5,
            "motor_style": 0.5,
            **style,
        },
        "top_mastery": [],
        "top_struggles": [],
    }


def test_short_reading_scores_higher_for_low_attention():
    short = {"kind": "reading", "topic": "arrays", "payload": {"estimated_word_count": 120, "style": "narrative"}}
    long = {"kind": "reading", "topic": "arrays", "payload": {"estimated_word_count": 320, "style": "narrative"}}
    snap = _snapshot(attention_stability=0.2)
    assert score_asset_for_student(short, snap)["fit_score"] > score_asset_for_student(long, snap)["fit_score"]


def test_video_scores_higher_for_visual_learners():
    video = {
        "kind": "video",
        "topic": "pythagorean theorem",
        "payload": {"duration_minutes": 10, "title": "Visual intro"},
    }
    visual = _snapshot(visual_orientation=0.9)
    non_visual = _snapshot(visual_orientation=0.2)
    assert score_asset_for_student(video, visual)["fit_score"] > score_asset_for_student(video, non_visual)["fit_score"]


def test_mastery_boost_when_topic_is_a_known_struggle():
    asset = {"kind": "reading", "topic": "recursion", "payload": {"estimated_word_count": 180, "style": "narrative"}}
    snapshot = _snapshot()
    snapshot["top_struggles"] = [{"topic": "recursion", "mastery_score": 0.3, "struggle_signal": 0.9}]
    scored = score_asset_for_student(asset, snapshot)
    assert scored["fit_score"] >= 60
    assert "struggle" in scored["rationale"]


def test_mastery_penalty_when_topic_already_near_mastered():
    asset = {"kind": "quiz", "topic": "arrays", "payload": {"questions": [{}, {}, {}], "difficulty": "core"}}
    baseline = score_asset_for_student(asset, _snapshot())
    snapshot = _snapshot()
    snapshot["top_mastery"] = [{"topic": "arrays", "mastery_score": 0.9}]
    penalized = score_asset_for_student(asset, snapshot)
    assert penalized["fit_score"] < baseline["fit_score"]
    assert "redundant" in penalized["rationale"]


def test_unknown_kind_returns_balanced_score():
    asset = {"kind": "mystery", "topic": "x", "payload": {}}
    scored = score_asset_for_student(asset, _snapshot())
    assert 30 <= scored["fit_score"] <= 70
    assert set(scored["components"].keys()) >= {"length_fit", "depth_fit", "engagement_fit", "format_fit", "mastery_fit"}
