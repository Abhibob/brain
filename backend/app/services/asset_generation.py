from __future__ import annotations

import json
import logging
import re
from typing import Any

from app.services.llm import llm_client
from app.settings import get_settings

log = logging.getLogger(__name__)


def _extract_json(raw: str) -> dict[str, Any]:
    match = re.search(r"\{.*\}", raw, re.DOTALL)
    if not match:
        return {}
    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError:
        return {}


def _deterministic_reading(topic: str, *, style_vector: dict[str, float] | None = None) -> dict[str, Any]:
    style_vector = style_vector or {}
    depth = float(style_vector.get("depth", 0.5))
    visual = float(style_vector.get("visual_orientation", 0.5))
    pace = float(style_vector.get("pace", 0.5))
    length = 240 if depth > 0.6 else 160 if pace > 0.6 else 180
    intro = (
        f"# {topic.title()}\n\n"
        f"This reading introduces {topic}. "
        "We start from a concrete example, then sharpen the idea, then verify with a small check."
    )
    concrete = (
        "## Concrete example\n\n"
        f"Start with a specific case of {topic}. Draw it out, label the parts, and state what is given "
        "and what is asked. Your job is to produce the answer with as few abstract symbols as possible."
    )
    core = (
        "## Core idea\n\n"
        f"Once the concrete case is clear, the general statement of {topic} becomes the short version of what you did. "
        "State it in one line; every symbol should map onto a piece of the concrete example."
    )
    visual_block = (
        "## Visual cue\n\nDraw the relevant diagram and label each piece. "
        "Use arrows to show which quantity depends on which."
        if visual > 0.55 else ""
    )
    check = (
        "## Check\n\n"
        f"Apply {topic} to one slightly different case. If your process does not work, find where the assumption broke."
    )
    content = "\n\n".join(part for part in [intro, concrete, core, visual_block, check] if part)
    return {
        "title": f"{topic.title()}: reading",
        "content": content,
        "estimated_word_count": length,
        "style": "concrete-first, short paragraphs",
    }


def _deterministic_quiz(topic: str, *, difficulty: str = "core", style_vector: dict[str, float] | None = None) -> dict[str, Any]:
    questions = [
        {
            "question": f"Which best describes {topic}?",
            "options": [
                f"A general idea about {topic}",
                f"An unrelated concept with the same name as {topic}",
                f"A step in solving {topic} problems",
                "None of the above",
            ],
            "correct_answer": f"A general idea about {topic}",
            "points": 1,
            "hint": "restate the one-line definition",
        },
        {
            "question": f"When applying {topic}, what should you check first?",
            "options": [
                "That the setup fits the assumptions",
                "That you memorized the formula",
                "That you ran out of time",
                "That you skipped to the end",
            ],
            "correct_answer": "That the setup fits the assumptions",
            "points": 1,
            "hint": "verify the preconditions",
        },
        {
            "question": f"Pick a worked-example checkpoint for {topic}.",
            "options": [
                "Trace one concrete case end to end",
                "Skip to the answer",
                "Guess and submit",
                "Memorize without examples",
            ],
            "correct_answer": "Trace one concrete case end to end",
            "points": 1,
            "hint": "concrete over abstract first",
        },
    ]
    return {
        "title": f"{topic.title()}: quick check",
        "difficulty": difficulty,
        "questions": questions,
        "estimated_minutes": 4,
    }


def _deterministic_practice(topic: str, *, style_vector: dict[str, float] | None = None) -> dict[str, Any]:
    style_vector = style_vector or {}
    attention = float(style_vector.get("attention_stability", 0.5))
    problems = [
        {
            "prompt": f"Apply {topic} to a small case and explain each step in one sentence.",
            "hint": "identify the setup, the move, and the result",
            "expected_steps": 3,
        },
        {
            "prompt": f"Find a case where {topic} does NOT apply and explain why in two sentences.",
            "hint": "look for a violated assumption",
            "expected_steps": 2,
        },
    ]
    if attention < 0.5:
        problems = problems[:1]
    return {
        "title": f"{topic.title()}: guided practice",
        "problems": problems,
        "estimated_minutes": 6,
    }


async def _llm_json(prompt: str, *, system: str | None = None) -> dict[str, Any]:
    """Call the LLM asking for JSON. Uses OpenAI json_object mode when supported.

    Falls back to regex extraction when the model returns prose. Raises on
    network / auth errors so callers can degrade gracefully.
    """
    settings = get_settings()
    client = llm_client()
    messages: list[dict[str, str]] = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})
    try:
        response = await client.chat.completions.create(
            model=settings.resolved_lesson_asset_model,
            messages=messages,
            response_format={"type": "json_object"},
        )
    except Exception as exc:
        # Some models / proxies reject response_format; retry without it.
        log.warning("LLM json_object mode rejected (%s); retrying without it", exc)
        response = await client.chat.completions.create(
            model=settings.resolved_lesson_asset_model,
            messages=messages,
        )
    return _extract_json(response.choices[0].message.content or "{}")


_SYSTEM = "You are an educational content generator. Reply with a single JSON object. Do not wrap it in prose."


async def generate_reading(topic: str, *, style_vector: dict[str, float] | None = None) -> dict[str, Any]:
    settings = get_settings()
    if settings.resolved_llm_provider == "deterministic":
        return _deterministic_reading(topic, style_vector=style_vector)
    style_json = json.dumps(style_vector or {})
    prompt = (
        "Generate a short educational reading tailored to a student profile. Return ONLY JSON with this shape: "
        '{"title": "...", "content": "markdown body with 3-5 headings", "estimated_word_count": 200, "style": "..."}.\n\n'
        f"TOPIC: {topic}\nSTUDENT_STYLE_VECTOR: {style_json}"
    )
    try:
        data = await _llm_json(prompt, system=_SYSTEM)
    except Exception as exc:
        log.warning("LLM reading generation failed for %r: %s; using deterministic fallback", topic, exc)
        return _deterministic_reading(topic, style_vector=style_vector)
    if not data.get("content"):
        log.warning("LLM returned no reading content for %r; using deterministic fallback", topic)
        return _deterministic_reading(topic, style_vector=style_vector)
    data.setdefault("title", f"{topic.title()}: reading")
    data.setdefault("estimated_word_count", 200)
    data.setdefault("style", "narrative")
    return data


async def generate_quiz(topic: str, *, difficulty: str = "core", style_vector: dict[str, float] | None = None) -> dict[str, Any]:
    settings = get_settings()
    if settings.resolved_llm_provider == "deterministic":
        return _deterministic_quiz(topic, difficulty=difficulty, style_vector=style_vector)
    style_json = json.dumps(style_vector or {})
    prompt = (
        "Generate a 3-question multiple-choice quiz tailored to the student. Return ONLY JSON with this shape: "
        '{"title": "...", "difficulty": "core", "questions": [{"question": "...", "options": ["..."], "correct_answer": "...", "points": 1, "hint": "..."}], "estimated_minutes": 4}.\n\n'
        f"TOPIC: {topic}\nDIFFICULTY: {difficulty}\nSTUDENT_STYLE_VECTOR: {style_json}"
    )
    try:
        data = await _llm_json(prompt, system=_SYSTEM)
    except Exception as exc:
        log.warning("LLM quiz generation failed for %r: %s; using deterministic fallback", topic, exc)
        return _deterministic_quiz(topic, difficulty=difficulty, style_vector=style_vector)
    if not data.get("questions"):
        log.warning("LLM returned no quiz questions for %r; using deterministic fallback", topic)
        return _deterministic_quiz(topic, difficulty=difficulty, style_vector=style_vector)
    data.setdefault("title", f"{topic.title()}: quiz")
    data.setdefault("difficulty", difficulty)
    data.setdefault("estimated_minutes", 4)
    return data


async def generate_practice(topic: str, *, style_vector: dict[str, float] | None = None) -> dict[str, Any]:
    settings = get_settings()
    if settings.resolved_llm_provider == "deterministic":
        return _deterministic_practice(topic, style_vector=style_vector)
    style_json = json.dumps(style_vector or {})
    prompt = (
        "Generate 1-3 guided practice problems tailored to the student. Return ONLY JSON with this shape: "
        '{"title": "...", "problems": [{"prompt": "...", "hint": "...", "expected_steps": 3}], "estimated_minutes": 6}.\n\n'
        f"TOPIC: {topic}\nSTUDENT_STYLE_VECTOR: {style_json}"
    )
    try:
        data = await _llm_json(prompt, system=_SYSTEM)
    except Exception as exc:
        log.warning("LLM practice generation failed for %r: %s; using deterministic fallback", topic, exc)
        return _deterministic_practice(topic, style_vector=style_vector)
    if not data.get("problems"):
        log.warning("LLM returned no practice problems for %r; using deterministic fallback", topic)
        return _deterministic_practice(topic, style_vector=style_vector)
    data.setdefault("title", f"{topic.title()}: practice")
    data.setdefault("estimated_minutes", 6)
    return data
