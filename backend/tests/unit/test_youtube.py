"""Unit tests for app.services.youtube (fallback path; no network)."""

from __future__ import annotations

import asyncio

from app.services.youtube import _deterministic_videos, search_videos


class TestDeterministicVideos:
    def test_returns_expected_shape(self) -> None:
        videos = _deterministic_videos("pythagorean theorem", max_results=4)
        assert len(videos) == 4
        for video in videos:
            assert video["video_id"].startswith("det-")
            assert "youtube.com/watch?v=" in video["url"]
            assert "img.youtube.com" in video["thumbnail_url"]
            assert "pythagorean" in video["title"].lower() or "pythagorean" in video["description"].lower()

    def test_stable_for_same_topic(self) -> None:
        a = _deterministic_videos("arrays", max_results=3)
        b = _deterministic_videos("arrays", max_results=3)
        assert a == b

    def test_different_topics_different_ids(self) -> None:
        a = {v["video_id"] for v in _deterministic_videos("arrays", max_results=6)}
        b = {v["video_id"] for v in _deterministic_videos("recursion", max_results=6)}
        assert a.isdisjoint(b)

    def test_empty_topic_still_returns_results(self) -> None:
        videos = _deterministic_videos("", max_results=2)
        assert len(videos) == 2


class TestSearchVideosWithoutKey:
    def test_returns_deterministic_when_no_api_key(self) -> None:
        # No EDUTRACK_YOUTUBE_API_KEY set in the test env, so search falls back.
        videos = asyncio.run(search_videos("arrays", max_results=3))
        assert len(videos) == 3
        assert all(v["video_id"].startswith("det-") for v in videos)

    def test_empty_topic_returns_empty_list(self) -> None:
        videos = asyncio.run(search_videos("", max_results=3))
        assert videos == []
