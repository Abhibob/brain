"""Pure-function unit tests for app.services.rag (no DB / no network)."""

from __future__ import annotations

import math
from dataclasses import dataclass

from app.services.rag import (
    _closing_practice,
    _lesson_markdown,
    _rewrite_section,
    build_personalization_prompt,
    deterministic_embedding,
    deterministic_personalized_markdown,
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
            FakeSection(title="Base cases", content="The base case is the stopping condition.", order_index=0),
            FakeSection(title="Recursive steps", content="The recursive step reduces the problem.", order_index=1),
        ],
    )


class TestDeterministicEmbedding:
    def test_returns_requested_dim(self) -> None:
        vec = deterministic_embedding("hello world", dim=1536)
        assert len(vec) == 1536

    def test_custom_dim(self) -> None:
        vec = deterministic_embedding("hi", dim=64)
        assert len(vec) == 64

    def test_unit_norm(self) -> None:
        vec = deterministic_embedding("the quick brown fox jumps over the lazy dog")
        norm = math.sqrt(sum(v * v for v in vec))
        assert abs(norm - 1.0) < 1e-3

    def test_deterministic_for_same_input(self) -> None:
        a = deterministic_embedding("recursion")
        b = deterministic_embedding("recursion")
        assert a == b

    def test_different_inputs_differ(self) -> None:
        a = deterministic_embedding("recursion")
        b = deterministic_embedding("inheritance")
        assert a != b

    def test_empty_string_produces_valid_vector(self) -> None:
        vec = deterministic_embedding("")
        assert len(vec) == 1536
        assert any(v != 0 for v in vec)


class TestLessonMarkdown:
    def test_sections_ordered_by_order_index(self) -> None:
        m = FakeMaterial(
            title="Ordered",
            sections=[
                FakeSection(title="Second", content="b", order_index=1),
                FakeSection(title="First", content="a", order_index=0),
            ],
        )
        md = _lesson_markdown(m)
        assert md.index("## First") < md.index("## Second")


class TestBuildPersonalizationPrompt:
    def test_contains_profile_marker_and_lesson(self) -> None:
        prompt = build_personalization_prompt(["Learner prefers visuals"], material())
        assert "STUDENT PROFILE ENTRIES" in prompt
        assert "Learner prefers visuals" in prompt
        assert "## Base cases" in prompt

    def test_style_summary_and_mastery_sections_rendered(self) -> None:
        prompt = build_personalization_prompt(
            ["Learner prefers visuals"],
            material(),
            style_summary_lines=["Pace: moderate.", "Depth: deep."],
            mastery_lines=["- recursion: mastery 0.60"],
        )
        assert "STUDENT STYLE SUMMARY" in prompt
        assert "Pace: moderate" in prompt
        assert "STUDENT TOPIC MASTERY" in prompt
        assert "recursion: mastery 0.60" in prompt

    def test_missing_style_and_mastery_renders_placeholder(self) -> None:
        prompt = build_personalization_prompt(["p"], material())
        assert "(no consolidated style summary yet)" in prompt
        assert "(no topic mastery data yet)" in prompt


class TestRewriteSection:
    def test_base_case_hint_added(self) -> None:
        out = _rewrite_section("Base cases", "The base case is the stopping condition.", False, False)
        assert "exit door" in out or "base case" in out.lower()
        assert "**Check:**" in out

    def test_recursive_step_hint_added(self) -> None:
        out = _rewrite_section("Step", "The recursive step reduces the problem via the call stack.", False, False)
        assert "**Trace:**" in out

    def test_tree_branch_hint_added(self) -> None:
        out = _rewrite_section("Branching", "Tree recursion splits into branches.", False, False)
        assert "branch" in out.lower()

    def test_visuals_appended_when_requested(self) -> None:
        out = _rewrite_section("Base cases", "The base case.", needs_visuals=True, needs_steps=False)
        assert "Visual cue" in out

    def test_scaffolding_appended_when_requested(self) -> None:
        out = _rewrite_section("Base cases", "The base case.", needs_visuals=False, needs_steps=True)
        assert "Step-through" in out

    def test_fallback_generic_block(self) -> None:
        out = _rewrite_section("Misc", "Something unrelated", False, False)
        assert "restate" in out.lower()


class TestClosingPractice:
    def test_mentions_title(self) -> None:
        out = _closing_practice("Derivatives")
        assert "Quick Practice" in out
        assert "Derivatives" in out


class TestDeterministicPersonalizedMarkdown:
    def test_includes_all_sections(self) -> None:
        md = deterministic_personalized_markdown(material(), [])
        assert "## Base cases" in md
        assert "## Recursive steps" in md
        assert "## Quick Practice" in md

    def test_visual_profile_triggers_visual_intro(self) -> None:
        md = deterministic_personalized_markdown(material(), ["Learner prefers visual diagrams"])
        assert "box" in md.lower()

    def test_slow_reader_profile_trims_intro(self) -> None:
        md = deterministic_personalized_markdown(material(), ["slow careful reader, benefits from visual aids"])
        assert "short" in md.lower() or "check" in md.lower()
