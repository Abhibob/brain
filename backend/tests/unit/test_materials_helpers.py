"""Unit tests for synchronous helpers in app.api.materials."""

from __future__ import annotations

from app.api.materials import _word_count


class TestWordCount:
    def test_simple(self) -> None:
        assert _word_count("hello world") == 2

    def test_collapses_multiple_spaces(self) -> None:
        assert _word_count("one   two") == 2

    def test_newline_treated_as_space(self) -> None:
        assert _word_count("one\ntwo\nthree") == 3

    def test_empty(self) -> None:
        assert _word_count("") == 0

    def test_whitespace_only(self) -> None:
        assert _word_count("   \n  ") == 0
