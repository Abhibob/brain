"""Pure-function tests for app.services.lesson_studio."""

from __future__ import annotations

from types import SimpleNamespace

from app.services.lesson_studio import _propose_order, _render_asset_section


def _candidate(asset_id: int, kind: str, title: str, fit: int, **payload_extras) -> dict:
    return {
        "asset": {
            "id": asset_id,
            "kind": kind,
            "title": title,
            "topic": "t",
            "payload": {"title": title, **payload_extras},
            "external_url": "https://youtube.com/watch?v=x" if kind == "video" else None,
            "generated_by": "llm",
        },
        "fit_score": fit,
        "rationale": "",
        "components": {},
    }


class TestProposeOrder:
    def test_visual_learner_gets_video_first(self) -> None:
        candidates = [
            _candidate(1, "reading", "r", 80),
            _candidate(2, "video", "v", 70),
            _candidate(3, "quiz", "q", 60),
        ]
        ordered = _propose_order(candidates, {"visual_orientation": 0.8, "attention_stability": 0.5})
        assert ordered[0]["asset"]["kind"] == "video"

    def test_non_visual_learner_gets_reading_first(self) -> None:
        candidates = [
            _candidate(1, "reading", "r", 80),
            _candidate(2, "video", "v", 70),
            _candidate(3, "quiz", "q", 60),
        ]
        ordered = _propose_order(candidates, {"visual_orientation": 0.3, "attention_stability": 0.5})
        assert ordered[0]["asset"]["kind"] == "reading"

    def test_deduplicates_same_asset(self) -> None:
        candidates = [_candidate(1, "reading", "r", 80), _candidate(1, "reading", "r", 80)]
        ordered = _propose_order(candidates, {})
        assert len({item["asset"]["id"] for item in ordered}) == len(ordered)

    def test_highest_fit_wins_within_kind(self) -> None:
        candidates = [
            _candidate(1, "reading", "low", 40),
            _candidate(2, "reading", "high", 90),
        ]
        ordered = _propose_order(candidates, {"visual_orientation": 0.3, "attention_stability": 0.5})
        readings = [c for c in ordered if c["asset"]["kind"] == "reading"]
        assert readings[0]["asset"]["title"] == "high"


class TestRenderAssetSection:
    def test_reading_returns_payload_content(self) -> None:
        asset = SimpleNamespace(kind="reading", title="R", payload={"content": "# hi"}, external_url=None)
        title, content = _render_asset_section(asset)
        assert title == "R"
        assert content == "# hi"

    def test_video_renders_yt_marker_for_lesson_viewer(self) -> None:
        asset = SimpleNamespace(
            kind="video",
            title="V",
            payload={"video_id": "abc123", "description": "d"},
            external_url="https://youtube.com/watch?v=abc123",
        )
        _, content = _render_asset_section(asset)
        # The marker format is parsed by LessonViewer into a YouTube iframe.
        assert content.startswith("YT::abc123::")
        assert "d" in content

    def test_video_without_id_falls_back_to_link(self) -> None:
        asset = SimpleNamespace(
            kind="video",
            title="V",
            payload={"description": "watch this"},
            external_url="https://example.com/vid",
        )
        _, content = _render_asset_section(asset)
        assert "https://example.com/vid" in content

    def test_quiz_renders_questions_and_options(self) -> None:
        asset = SimpleNamespace(
            kind="quiz",
            title="Q",
            payload={"questions": [{"question": "what?", "options": ["A", "B"]}]},
            external_url=None,
        )
        _, content = _render_asset_section(asset)
        assert "what?" in content
        assert "- A" in content
        assert "- B" in content

    def test_practice_renders_prompts_and_hints(self) -> None:
        asset = SimpleNamespace(
            kind="practice",
            title="P",
            payload={"problems": [{"prompt": "do it", "hint": "use X"}]},
            external_url=None,
        )
        _, content = _render_asset_section(asset)
        assert "do it" in content
        assert "hint: use X" in content
