"""Pure-function unit tests for app.services.ml (no DB)."""

from __future__ import annotations

import pytest

from app.services.ml import FEATURE_KEYS, clamp, flatten_features, heuristic_score


class TestClamp:
    @pytest.mark.parametrize(
        "value,low,high,expected",
        [
            (0.5, 0.0, 1.0, 0.5),
            (-0.1, 0.0, 1.0, 0.0),
            (1.5, 0.0, 1.0, 1.0),
            (0.0, 0.0, 1.0, 0.0),
            (1.0, 0.0, 1.0, 1.0),
            (5.0, 2.0, 10.0, 5.0),
        ],
    )
    def test_clamp(self, value: float, low: float, high: float, expected: float) -> None:
        assert clamp(value, low, high) == expected

    def test_default_range(self) -> None:
        assert clamp(-3) == 0.0
        assert clamp(42) == 1.0


class TestFlattenFeatures:
    def test_returns_14_values_in_key_order(self) -> None:
        values = flatten_features({})
        assert len(values) == len(FEATURE_KEYS) == 14
        assert all(v == 0.0 for v in values)

    def test_missing_keys_default_to_zero(self) -> None:
        values = flatten_features({"total_time_s": 120, "hover_count": 3})
        assert values[FEATURE_KEYS.index("total_time_s")] == 120.0
        assert values[FEATURE_KEYS.index("hover_count")] == 3.0
        assert values[FEATURE_KEYS.index("scroll_depth_pct")] == 0.0

    def test_re_read_count_comes_from_list_length(self) -> None:
        values = flatten_features({"re_read_sections": ["1", "2", "3"]})
        assert values[FEATURE_KEYS.index("re_read_count")] == 3.0

    def test_none_input(self) -> None:
        assert flatten_features(None) == [0.0] * 14

    def test_non_numeric_value_becomes_zero(self) -> None:
        values = flatten_features({"total_time_s": "not-a-number"})
        assert values[FEATURE_KEYS.index("total_time_s")] == 0.0


class TestHeuristicScore:
    def test_baseline_is_half(self) -> None:
        assert heuristic_score({}) == 0.5

    def test_strong_signal_caps_at_one(self) -> None:
        features = {
            "reading_speed_wpm": 200,
            "section_completion_rate": 1.0,
            "hover_count": 5,
            "total_time_s": 100,
            "idle_total_s": 5,
            "back_scroll_count": 1,
        }
        assert 0.8 <= heuristic_score(features) <= 1.0

    def test_high_idle_penalizes(self) -> None:
        low_idle = heuristic_score({"total_time_s": 100, "idle_total_s": 5})
        high_idle = heuristic_score({"total_time_s": 100, "idle_total_s": 60})
        assert high_idle < low_idle

    def test_excessive_backscroll_penalizes(self) -> None:
        base = heuristic_score({})
        heavy = heuristic_score({"back_scroll_count": 10})
        assert heavy < base

    def test_reading_speed_outside_band_no_bonus(self) -> None:
        slow = heuristic_score({"reading_speed_wpm": 30})
        sweet = heuristic_score({"reading_speed_wpm": 180})
        assert sweet > slow

    def test_never_above_one_or_below_zero(self) -> None:
        extreme = heuristic_score({"idle_total_s": 10_000, "total_time_s": 1, "back_scroll_count": 200})
        assert 0.0 <= extreme <= 1.0
