"""Pure-function tests for app.services.asset_generation deterministic helpers."""

from __future__ import annotations

from app.services.asset_generation import (
    _deterministic_practice,
    _deterministic_quiz,
    _deterministic_reading,
    _extract_json,
)


class TestExtractJson:
    def test_returns_dict_from_raw_json(self) -> None:
        assert _extract_json('{"a": 1}') == {"a": 1}

    def test_finds_json_inside_prose(self) -> None:
        raw = "Sure, here it is:\n{\"title\": \"x\", \"n\": 2}\nbye"
        assert _extract_json(raw) == {"title": "x", "n": 2}

    def test_returns_empty_on_missing_brace(self) -> None:
        assert _extract_json("no json here") == {}

    def test_returns_empty_on_malformed_json(self) -> None:
        assert _extract_json("{title: }") == {}


class TestDeterministicReading:
    def test_contains_title_and_content(self) -> None:
        out = _deterministic_reading("arrays")
        assert "arrays" in out["title"].lower()
        assert "# " in out["content"]
        assert isinstance(out["estimated_word_count"], int)

    def test_length_longer_for_deep_readers(self) -> None:
        short = _deterministic_reading("t", style_vector={"depth": 0.2, "pace": 0.2})
        deep = _deterministic_reading("t", style_vector={"depth": 0.9})
        assert deep["estimated_word_count"] >= short["estimated_word_count"]

    def test_visual_cue_added_for_visual_learners(self) -> None:
        visual = _deterministic_reading("t", style_vector={"visual_orientation": 0.8})
        plain = _deterministic_reading("t", style_vector={"visual_orientation": 0.2})
        assert "## Visual cue" in visual["content"]
        assert "## Visual cue" not in plain["content"]


class TestDeterministicQuiz:
    def test_has_three_questions(self) -> None:
        out = _deterministic_quiz("arrays")
        assert len(out["questions"]) == 3
        for q in out["questions"]:
            assert q["correct_answer"] in q["options"]
            assert q["points"] == 1

    def test_difficulty_passed_through(self) -> None:
        out = _deterministic_quiz("arrays", difficulty="challenge")
        assert out["difficulty"] == "challenge"


class TestDeterministicPractice:
    def test_fewer_problems_for_low_attention_students(self) -> None:
        low = _deterministic_practice("t", style_vector={"attention_stability": 0.2})
        high = _deterministic_practice("t", style_vector={"attention_stability": 0.9})
        assert len(low["problems"]) <= len(high["problems"])

    def test_problems_have_prompt_and_hint(self) -> None:
        out = _deterministic_practice("arrays")
        for problem in out["problems"]:
            assert problem["prompt"]
            assert problem["hint"]
            assert isinstance(problem["expected_steps"], int)
