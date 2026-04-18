"""Pure-function unit tests for app.services.profile."""

from __future__ import annotations

import json
from dataclasses import dataclass

import pytest

from app.services.profile import (
    PROFILE_KEYS,
    build_entry_prompt,
    deterministic_profile_entry,
    normalize_entry,
    parse_profile_entry_content,
    profile_text,
)


@dataclass
class FakeSection:
    title: str
    content: str
    order_index: int


@dataclass
class FakeMaterial:
    title: str
    sections: list[FakeSection]


def material() -> FakeMaterial:
    return FakeMaterial(
        title="Recursion",
        sections=[
            FakeSection(title="Base", content="A recursive function needs a stopping condition.", order_index=0),
            FakeSection(title="Step", content="The recursive step reduces the problem.", order_index=1),
        ],
    )


def _valid_payload() -> dict:
    return {
        "topic": "recursion",
        "observed_score": 0.8,
        "predicted_score": 0.7,
        "strengths_observed": ["base case"],
        "struggles_observed": [],
        "engagement_notes": "steady",
        "behavioral_summary": "visual",
        "recommendation": "diagrams",
    }


class TestParseProfileEntryContent:
    def test_plain_json(self) -> None:
        raw = json.dumps(_valid_payload())
        parsed = parse_profile_entry_content(raw)
        assert set(parsed.keys()) == PROFILE_KEYS
        assert parsed["observed_score"] == 0.8

    def test_fenced_json_block(self) -> None:
        content = f"```json\n{json.dumps(_valid_payload())}\n```"
        parsed = parse_profile_entry_content(content)
        assert parsed["topic"] == "recursion"
        assert parsed["observed_score"] == 0.8

    def test_surrounding_prose_stripped(self) -> None:
        content = f"Sure! Here is the profile:\n{json.dumps(_valid_payload())}\nThanks!"
        parsed = parse_profile_entry_content(content)
        assert set(parsed.keys()) == PROFILE_KEYS
        assert parsed["topic"] == "recursion"

    def test_invalid_json_raises(self) -> None:
        with pytest.raises(json.JSONDecodeError):
            parse_profile_entry_content("not json at all")


class TestNormalizeEntry:
    def test_coerces_types(self) -> None:
        out = normalize_entry({"topic": None, "observed_score": None, "strengths_observed": None, "struggles_observed": None})
        assert out["topic"] == ""
        assert out["observed_score"] == 0.0
        assert out["strengths_observed"] == []
        assert out["struggles_observed"] == []
        assert out["predicted_score"] is None

    def test_predicted_score_preserved_when_present(self) -> None:
        out = normalize_entry({"predicted_score": 0.42})
        assert out["predicted_score"] == 0.42

    def test_keys_subset_fills_missing(self) -> None:
        out = normalize_entry({"topic": "derivatives"})
        assert PROFILE_KEYS.issubset(out.keys())
        assert out["topic"] == "derivatives"


class TestDeterministicProfileEntry:
    def test_returns_all_keys(self) -> None:
        entry = deterministic_profile_entry(material(), {"section_completion_rate": 1.0, "reading_speed_wpm": 200}, 4, 5, 0.8)
        assert PROFILE_KEYS.issubset(entry.keys())
        assert entry["topic"] == "Recursion"

    def test_score_normalized(self) -> None:
        entry = deterministic_profile_entry(material(), {}, 3, 4, None)
        assert entry["observed_score"] == 0.75

    def test_zero_max_score_safe(self) -> None:
        entry = deterministic_profile_entry(material(), {}, 0, 0, None)
        assert entry["observed_score"] == 0.0

    def test_slow_reader_flagged_in_behavior(self) -> None:
        entry = deterministic_profile_entry(material(), {"reading_speed_wpm": 80}, 1, 1, None)
        assert "slow" in entry["behavioral_summary"].lower() or "visual" in entry["behavioral_summary"].lower()

    def test_low_score_produces_scaffolding_struggle(self) -> None:
        entry = deterministic_profile_entry(material(), {}, 1, 5, None)
        assert any("scaffolding" in s.lower() for s in entry["struggles_observed"])

    def test_heavy_backscroll_recorded_as_struggle(self) -> None:
        entry = deterministic_profile_entry(material(), {"back_scroll_count": 5}, 5, 5, None)
        assert any("revisit" in s.lower() or "confusion" in s.lower() for s in entry["struggles_observed"])


class TestProfileText:
    def test_formats_known_entry(self) -> None:
        entry = {
            "topic": "Recursion",
            "observed_score": 0.8,
            "strengths_observed": ["base case"],
            "struggles_observed": ["edge cases"],
            "engagement_notes": "steady",
            "behavioral_summary": "visual",
            "recommendation": "use diagrams",
        }
        text = profile_text(entry)
        assert "Recursion" in text
        assert "0.8" in text
        assert "base case" in text
        assert "use diagrams" in text


class TestBuildEntryPrompt:
    def test_includes_scores_and_features(self) -> None:
        prompt = build_entry_prompt(material(), {"total_time_s": 120, "hover_count": 3}, 4, 5, 0.72)
        assert "Recursion" in prompt
        assert "4/5" in prompt
        assert "0.72" in prompt
        assert "total_time_s" in prompt
        assert "Return only valid JSON" in prompt
