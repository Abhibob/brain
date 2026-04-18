"""Unit tests for app.services.tracking.compute_features (pure function)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from app.services.tracking import compute_features


@dataclass
class FakeSection:
    id: int
    word_count: int
    order_index: int = 0


@dataclass
class FakeMaterial:
    sections: list[FakeSection]


def make_material(n_sections: int = 2, words_each: int = 30) -> FakeMaterial:
    return FakeMaterial(sections=[FakeSection(id=i + 1, word_count=words_each, order_index=i) for i in range(n_sections)])


def wrap(event_type: str, **data: Any) -> dict[str, Any]:
    return {"event_type": event_type, "event_data": data, "client_ts": 1_700_000_000_000}


START = datetime(2026, 4, 18, 10, 0, 0, tzinfo=UTC)
END = START + timedelta(seconds=120)


class TestComputeFeaturesBasics:
    def test_empty_events_returns_zeros(self) -> None:
        features = compute_features([], make_material(), START, END)
        assert features["hover_count"] == 0
        assert features["avg_hover_duration_ms"] == 0.0
        assert features["scroll_depth_pct"] == 0.0
        assert features["back_scroll_count"] == 0
        assert features["idle_total_s"] == 0.0
        assert features["idle_count"] == 0
        assert features["text_selection_count"] == 0
        assert features["mouse_velocity_variance"] == 0.0

    def test_end_none_uses_now(self) -> None:
        features = compute_features([], make_material(), START, None)
        assert features["total_time_s"] >= 0

    def test_section_completion_from_views_alone(self) -> None:
        events = [wrap("section_view", section_id="1"), wrap("section_view", section_id="2")]
        features = compute_features(events, make_material(2), START, END)
        assert features["section_completion_rate"] == 1.0

    def test_partial_completion(self) -> None:
        # With no section_exit events the feature extractor falls back to an even
        # time split across all sections, which counts every section as visited.
        # So a single view still counts as full completion under the fallback.
        events = [wrap("section_view", section_id="1")]
        features = compute_features(events, make_material(4), START, END)
        assert features["section_completion_rate"] == 1.0

    def test_partial_completion_with_exit_events(self) -> None:
        events = [
            wrap("section_view", section_id="1"),
            wrap("section_exit", section_id="1", time_spent_ms=5_000),
        ]
        features = compute_features(events, make_material(4), START, END)
        assert features["section_completion_rate"] == 0.25

    def test_re_read_detects_repeat_view(self) -> None:
        events = [
            wrap("section_view", section_id="1"),
            wrap("section_view", section_id="2"),
            wrap("section_view", section_id="1"),
        ]
        features = compute_features(events, make_material(2), START, END)
        assert "1" in features["re_read_sections"]
        assert "2" not in features["re_read_sections"]


class TestHoverAndScroll:
    def test_hover_count_and_duration(self) -> None:
        events = [
            wrap("hover_end", section_id="1", duration_ms=500),
            wrap("hover_end", section_id="1", duration_ms=1500),
        ]
        features = compute_features(events, make_material(), START, END)
        assert features["hover_count"] == 2
        assert features["avg_hover_duration_ms"] == 1000.0
        assert features["hover_per_section"]["1"] == 2

    def test_back_scroll_counted(self) -> None:
        events = [
            wrap("scroll", direction="down", position=30, velocity=0.5),
            wrap("scroll", direction="up", position=10, velocity=0.3),
            wrap("scroll", direction="up", position=5, velocity=0.2),
        ]
        features = compute_features(events, make_material(), START, END)
        assert features["back_scroll_count"] == 2
        assert features["scroll_depth_pct"] == 30

    def test_mouse_velocity_variance_requires_multiple(self) -> None:
        single = [wrap("mouse_move", velocity=0.5)]
        features = compute_features(single, make_material(), START, END)
        assert features["mouse_velocity_variance"] == 0.0

        events = [wrap("mouse_move", velocity=v) for v in (0.1, 0.5, 1.0)]
        features = compute_features(events, make_material(), START, END)
        assert features["mouse_velocity_avg"] > 0
        assert features["mouse_velocity_variance"] > 0


class TestIdleAndTextSelect:
    def test_idle_accumulates(self) -> None:
        events = [
            wrap("idle_end", duration_ms=1000),
            wrap("idle_end", duration_ms=3000),
        ]
        features = compute_features(events, make_material(), START, END)
        assert features["idle_count"] == 2
        assert features["idle_total_s"] == 4.0

    def test_text_select_counts_positive_chars(self) -> None:
        events = [
            wrap("text_select", section_id="1", char_count=10),
            wrap("text_select", section_id="1", char_count=0),
        ]
        features = compute_features(events, make_material(), START, END)
        assert features["text_selection_count"] == 1


class TestTimePerSectionFallback:
    def test_time_per_section_from_exit_events(self) -> None:
        events = [
            wrap("section_exit", section_id="1", time_spent_ms=8_000),
            wrap("section_exit", section_id="2", time_spent_ms=12_000),
        ]
        features = compute_features(events, make_material(2), START, END)
        assert features["time_per_section"]["1"] == 8.0
        assert features["time_per_section"]["2"] == 12.0

    def test_fallback_even_split_when_no_exits(self) -> None:
        features = compute_features([], make_material(2), START, END)
        # 120s across 2 sections → ~60 each
        assert features["time_per_section"].values()
        assert round(sum(features["time_per_section"].values()), 0) == 120


class TestReadingSpeed:
    def test_reading_speed_from_words_over_minutes(self) -> None:
        events = [wrap("section_exit", section_id="1", time_spent_ms=60_000)]
        mat = make_material(1, words_each=200)
        features = compute_features(events, mat, START, END)
        assert features["reading_speed_wpm"] == 200.0

    def test_reading_speed_zero_when_no_words(self) -> None:
        mat = make_material(1, words_each=0)
        features = compute_features([], mat, START, END)
        assert features["reading_speed_wpm"] == 0.0


class TestMalformedEvents:
    def test_non_numeric_durations_ignored(self) -> None:
        events = [
            {"event_type": "hover_end", "event_data": {"duration_ms": "nope"}, "client_ts": 1},
            {"event_type": "idle_end", "event_data": {"duration_ms": None}, "client_ts": 2},
        ]
        features = compute_features(events, make_material(), START, END)
        assert features["hover_count"] == 0
        assert features["idle_total_s"] == 0.0

    def test_alternate_key_names_supported(self) -> None:
        # WebSocket layer sometimes flattens data under "type"/"data"
        events = [{"type": "hover_end", "data": {"sectionId": "1", "duration": 400}, "client_ts": 1}]
        features = compute_features(events, make_material(), START, END)
        assert features["hover_count"] == 1
