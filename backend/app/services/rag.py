from __future__ import annotations

import hashlib
import json
import math
import re
from datetime import UTC, datetime
from typing import Any

from pgvector.sqlalchemy import Vector
from sqlalchemy import literal, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import (
    Class,
    Enrollment,
    Material,
    MaterialSection,
    MaterialTopic,
    PersonalizedLesson,
    StudentProfileEntry,
    TopicMasteryEdge,
    TopicMasteryNode,
    TrackingSession,
    UserLearningProfile,
)
from app.services.llm import embedding_model, llm_client, llm_model
from app.settings import get_settings


def deterministic_embedding(text: str, dim: int = 1536) -> list[float]:
    vector = [0.0] * dim
    tokens = [token.strip(".,:;!?()[]{}").lower() for token in text.split() if token.strip()]
    if not tokens:
        tokens = [text or "empty"]
    for token in tokens:
        digest = hashlib.blake2b(token.encode("utf-8"), digest_size=16).digest()
        for offset in range(0, len(digest), 4):
            idx = int.from_bytes(digest[offset : offset + 2], "big") % dim
            sign = 1.0 if digest[offset + 2] % 2 == 0 else -1.0
            magnitude = (digest[offset + 3] / 255.0) + 0.1
            vector[idx] += sign * magnitude
    norm = math.sqrt(sum(value * value for value in vector)) or 1.0
    return [round(value / norm, 8) for value in vector]


async def embed_text(text: str) -> list[float]:
    settings = get_settings()
    if settings.resolved_llm_provider != "deterministic":
        client = llm_client()
        response = await client.embeddings.create(model=embedding_model(), input=text)
        return list(response.data[0].embedding)
    return deterministic_embedding(text, settings.embedding_dim)


async def embed_material_sections(material_id: int, db: AsyncSession) -> int:
    sections = (await db.scalars(select(MaterialSection).where(MaterialSection.material_id == material_id))).all()
    for section in sections:
        section.embedding = await embed_text(f"{section.title}\n{section.content}")
    await db.commit()
    return len(sections)


async def retrieve_profile_entries(student_id: int, query_text: str, db: AsyncSession, top_k: int = 8) -> list[StudentProfileEntry]:
    query_vector = await embed_text(query_text)
    if db.bind and db.bind.dialect.name != "postgresql":
        entries = (
            await db.scalars(
                select(StudentProfileEntry)
                .where(StudentProfileEntry.user_id == student_id, StudentProfileEntry.embedding.is_not(None))
                .order_by(StudentProfileEntry.created_at.desc())
            )
        ).all()

        def cosine_distance(entry: StudentProfileEntry) -> float:
            embedding = entry.embedding or []
            dot = sum(float(a) * float(b) for a, b in zip(embedding, query_vector, strict=False))
            norm_a = math.sqrt(sum(float(value) * float(value) for value in embedding)) or 1.0
            norm_b = math.sqrt(sum(value * value for value in query_vector)) or 1.0
            return 1.0 - dot / (norm_a * norm_b)

        return sorted(entries, key=cosine_distance)[:top_k]
    rows = (
        await db.scalars(
            select(StudentProfileEntry)
            .where(StudentProfileEntry.user_id == student_id, StudentProfileEntry.embedding.is_not(None))
            .order_by(
                StudentProfileEntry.embedding.op("<=>")(literal(query_vector, type_=Vector(get_settings().embedding_dim))),
                StudentProfileEntry.created_at.desc(),
            )
            .limit(top_k)
        )
    ).all()
    return list(rows)


def _lesson_markdown(material: Material) -> str:
    return "\n\n".join(f"## {section.title}\n{section.content}" for section in sorted(material.sections, key=lambda item: item.order_index))


def build_personalization_prompt(
    profile_chunks: list[str],
    material: Material,
    *,
    style_summary_lines: list[str] | None = None,
    mastery_lines: list[str] | None = None,
) -> str:
    style_block = "\n".join(style_summary_lines or []) or "(no consolidated style summary yet)"
    mastery_block = "\n".join(mastery_lines or []) or "(no topic mastery data yet)"
    return (
        "You are a skilled educator. Rewrite this lesson for a specific student.\n\n"
        "STUDENT STYLE SUMMARY:\n"
        f"{style_block}\n\n"
        "STUDENT TOPIC MASTERY (relevant):\n"
        f"{mastery_block}\n\n"
        "STUDENT PROFILE ENTRIES:\n"
        f"{chr(10).join(profile_chunks)}\n\n"
        "ORIGINAL LESSON:\n"
        f"{_lesson_markdown(material)}\n\n"
        "Rewrite the lesson maintaining all factual content but adapt examples, scaffolding, pacing, and section length. "
        "Keep the same quiz questions and learning objectives. Return structured markdown."
    )


async def generate_markdown(prompt: str, material: Material, profile_chunks: list[str]) -> str:
    settings = get_settings()
    if settings.resolved_llm_provider != "deterministic":
        client = llm_client()
        response = await client.chat.completions.create(
            model=llm_model(),
            messages=[{"role": "user", "content": prompt}],
        )
        return response.choices[0].message.content or ""

    return deterministic_personalized_markdown(material, profile_chunks)


def deterministic_personalized_markdown(material: Material, profile_chunks: list[str]) -> str:
    profile_summary = " ".join(profile_chunks).lower()
    sections = sorted(material.sections, key=lambda item: item.order_index)
    needs_visuals = "visual" in profile_summary or "diagram" in profile_summary
    needs_steps = "step-through" in profile_summary or "scaffold" in profile_summary or "confusion" in profile_summary
    concise = "slow careful reader" in profile_summary

    intro = (
        f"# {material.title}\n\n"
        "Read this as a sequence of small moves. First name the stopping point, then name the smaller problem, "
        "then trace how the answer comes back."
    )
    if concise:
        intro += " Each section is kept short, with a quick check before moving on."
    if needs_visuals:
        intro += " When a call or branch appears, picture it as a box connected to the next box in the chain."

    rendered_sections = [intro]
    for section in sections:
        rendered_sections.append(_rewrite_section(section.title, section.content, needs_visuals, needs_steps))
    rendered_sections.append(_closing_practice(material.title))
    return "\n\n".join(rendered_sections)


def _rewrite_section(title: str, content: str, needs_visuals: bool, needs_steps: bool) -> str:
    title_l = title.lower()
    content_l = content.lower()
    parts = [f"## {title}", content.strip()]

    if "base case" in content_l or "base" in title_l or "stopping" in content_l:
        parts.append(
            "Think of the base case as the exit door. For `countdown(3)`, the calls can keep asking for `countdown(2)`, "
            "`countdown(1)`, and then `countdown(0)`. The `0` case is where the function stops asking and starts returning."
        )
        parts.append("**Check:** If this case runs, does the function make another recursive call? If yes, it is not a base case yet.")
    elif "recursive step" in content_l or "call stack" in content_l or "reduces" in content_l or "step" in title_l:
        parts.append(
            "The recursive step is the handoff. It should keep the same goal, but pass a smaller input forward. "
            "After the smaller call finishes, the current call uses that result and returns its own answer."
        )
        parts.append("**Trace:** Write one line per call, then read the lines backward to see how values return.")
    elif "tree" in content_l or "branch" in content_l:
        parts.append(
            "Tree recursion splits one problem into multiple smaller branches. Keep each branch separate until it returns, "
            "then combine the branch answers into one result."
        )
        parts.append("**Check:** What does the left branch return? What does the right branch return? What operation combines them?")
    else:
        parts.append(
            "Before moving on, restate the section in one sentence: what changes, what stays the same, and what result should come back?"
        )

    if needs_visuals:
        parts.append("> Visual cue: draw each call as a box. Put the input inside the box and draw an arrow to the smaller call it creates.")
    if needs_steps:
        parts.append("**Step-through:** identify the current input, choose the stop condition, make one smaller call, then return one value.")

    return "\n\n".join(parts)


def _closing_practice(title: str) -> str:
    return (
        "## Quick Practice\n"
        "1. Circle the base case.\n"
        "2. Underline the part that makes the input smaller.\n"
        "3. Trace two calls by hand before answering the quiz.\n\n"
        f"When those three checks are clear, you are ready for the {title} quiz."
    )


async def personalize_lesson(student_id: int, material_id: int, db: AsyncSession) -> PersonalizedLesson | None:
    material = await db.scalar(
        select(Material)
        .where(Material.id == material_id)
        .options(selectinload(Material.sections), selectinload(Material.class_))
    )
    if material is None or material.published_at is None:
        return None
    query_text = f"{material.title}\n{_lesson_markdown(material)}"
    entries = await retrieve_profile_entries(student_id, query_text, db)
    if not entries:
        return None
    profile_chunks = [entry.profile_text for entry in entries]
    context = await build_learning_context(student_id, material.title, db, material_id=material.id)
    prompt = build_personalization_prompt(
        profile_chunks,
        material,
        style_summary_lines=context["style_summary_lines"],
        mastery_lines=context["mastery_lines"],
    )
    generated_content = await generate_markdown(prompt, material, profile_chunks)

    if db.bind and db.bind.dialect.name == "postgresql":
        stmt = (
            insert(PersonalizedLesson)
            .values(
                educator_id=material.class_.educator_id,
                student_id=student_id,
                base_material_id=material_id,
                prompt_used=prompt,
                generated_content=generated_content,
                assigned_at=datetime.now(UTC),
            )
            .on_conflict_do_update(
                constraint="uq_personalized_student_material",
                set_={
                    "prompt_used": prompt,
                    "generated_content": generated_content,
                    "assigned_at": datetime.now(UTC),
                },
            )
            .returning(PersonalizedLesson)
        )
        lesson = await db.scalar(stmt)
        await db.commit()
        return lesson

    lesson = await db.scalar(
        select(PersonalizedLesson).where(
            PersonalizedLesson.student_id == student_id,
            PersonalizedLesson.base_material_id == material_id,
        )
    )
    if lesson is None:
        lesson = PersonalizedLesson(
            educator_id=material.class_.educator_id,
            student_id=student_id,
            base_material_id=material_id,
            prompt_used=prompt,
            generated_content=generated_content,
            assigned_at=datetime.now(UTC),
        )
        db.add(lesson)
    else:
        lesson.prompt_used = prompt
        lesson.generated_content = generated_content
        lesson.assigned_at = datetime.now(UTC)
    await db.commit()
    await db.refresh(lesson)
    return lesson


async def _retrieve_mastery_nodes(
    student_id: int,
    seed_vector: list[float],
    db: AsyncSession,
    *,
    top_k: int = 8,
) -> list[TopicMasteryNode]:
    if db.bind and db.bind.dialect.name != "postgresql":
        nodes = (
            await db.scalars(
                select(TopicMasteryNode).where(TopicMasteryNode.user_id == student_id)
            )
        ).all()

        def distance(node: TopicMasteryNode) -> float:
            embedding = node.embedding or []
            if not embedding:
                return 1.0
            dot = sum(float(a) * float(b) for a, b in zip(embedding, seed_vector, strict=False))
            norm_a = math.sqrt(sum(float(value) * float(value) for value in embedding)) or 1.0
            norm_b = math.sqrt(sum(value * value for value in seed_vector)) or 1.0
            return 1.0 - dot / (norm_a * norm_b)

        return sorted(nodes, key=distance)[:top_k]
    return list(
        (
            await db.scalars(
                select(TopicMasteryNode)
                .where(
                    TopicMasteryNode.user_id == student_id,
                    TopicMasteryNode.embedding.is_not(None),
                )
                .order_by(
                    TopicMasteryNode.embedding.op("<=>")(
                        literal(seed_vector, type_=Vector(get_settings().embedding_dim))
                    ),
                    TopicMasteryNode.last_seen_at.desc(),
                )
                .limit(top_k)
            )
        ).all()
    )


async def build_learning_context(
    student_id: int,
    seed_text: str,
    db: AsyncSession,
    *,
    material_id: int | None = None,
    top_k_entries: int = 6,
    top_k_nodes: int = 6,
) -> dict[str, Any]:
    from app.services.learning_profile import get_profile_snapshot, render_style_summary

    snapshot = await get_profile_snapshot(student_id, db)
    style_summary_lines = render_style_summary(snapshot)

    seed_vector = await embed_text(seed_text)
    mastery_nodes = await _retrieve_mastery_nodes(student_id, seed_vector, db, top_k=top_k_nodes)
    mastery_topics = [node.topic for node in mastery_nodes]

    edge_rows: list[TopicMasteryEdge] = []
    if mastery_topics:
        edge_rows = list(
            (
                await db.scalars(
                    select(TopicMasteryEdge).where(
                        TopicMasteryEdge.user_id == student_id,
                        TopicMasteryEdge.from_topic.in_(mastery_topics),
                    )
                )
            ).all()
        )

    entries = await retrieve_profile_entries(student_id, seed_text, db, top_k=top_k_entries)

    recent_sessions = list(
        (
            await db.scalars(
                select(TrackingSession)
                .where(
                    TrackingSession.student_id == student_id,
                    TrackingSession.focus_label.is_not(None),
                )
                .order_by(TrackingSession.ended_at.desc())
                .limit(5)
            )
        ).all()
    )

    mastery_lines = [
        (
            f"- {node.topic}: mastery {node.mastery_score:.2f}, "
            f"exposure {node.exposure_score:.2f}, "
            f"encounters {node.encounter_count}, "
            f"struggle {node.struggle_signal:.2f}"
        )
        for node in mastery_nodes
    ]

    hints = (snapshot.get("behavioral_signals") or {}).get("recent_hints") or []
    recent_focus = [
        {"label": s.focus_label, "score": s.focus_score, "material_id": s.material_id}
        for s in recent_sessions
    ]

    return {
        "style_summary_lines": style_summary_lines,
        "snapshot": snapshot,
        "mastery_nodes": [
            {
                "topic": n.topic,
                "mastery_score": n.mastery_score,
                "exposure_score": n.exposure_score,
                "encounter_count": n.encounter_count,
                "struggle_signal": n.struggle_signal,
                "strength_signal": n.strength_signal,
            }
            for n in mastery_nodes
        ],
        "mastery_lines": mastery_lines,
        "topic_edges": [
            {
                "from_topic": e.from_topic,
                "to_topic": e.to_topic,
                "relation": e.relation,
                "weight": e.weight,
            }
            for e in edge_rows
        ],
        "profile_entries": [
            {
                "id": entry.id,
                "profile_text": entry.profile_text,
                "quiz_score": entry.quiz_score,
            }
            for entry in entries
        ],
        "recent_focus": recent_focus,
        "recent_hints": hints,
        "seed_text": seed_text,
        "material_id": material_id,
    }


def _deterministic_lesson_plan(topic: str, context: dict[str, Any]) -> dict[str, Any]:
    snapshot = context.get("snapshot") or {}
    style = snapshot.get("style_vector") or {}
    pace = float(style.get("pace", 0.5))
    depth = float(style.get("depth", 0.5))
    visual = float(style.get("visual_orientation", 0.5))
    attention = float(style.get("attention_stability", 0.5))
    base_words = 150 if attention < 0.5 else 220 if depth > 0.6 else 180

    sections: list[dict[str, Any]] = []
    sections.append(
        {
            "title": f"Why {topic} matters",
            "angle": "motivation, concrete example",
            "why_this_works_for_them": "starts concrete before abstract which suits their profile",
            "estimated_word_count": base_words,
        }
    )
    if visual > 0.55:
        sections.append(
            {
                "title": f"{topic} - visual walkthrough",
                "angle": "diagram-first explanation with labeled parts",
                "why_this_works_for_them": "high visual_orientation, hover-heavy engagement",
                "estimated_word_count": base_words,
            }
        )
    sections.append(
        {
            "title": f"Core idea of {topic}",
            "angle": "definition plus one worked example, chunked",
            "why_this_works_for_them": "deeper reader benefits from examples before formal statement"
            if depth > 0.5
            else "keep this short and punchy",
            "estimated_word_count": base_words + (40 if depth > 0.6 else 0),
        }
    )
    sections.append(
        {
            "title": "Guided practice",
            "angle": "two problems with step-through scaffolding",
            "why_this_works_for_them": "reinforces with active recall; suits their engagement mode",
            "estimated_word_count": 140,
        }
    )
    sections.append(
        {
            "title": "Check for understanding",
            "angle": "three quick questions before the quiz",
            "why_this_works_for_them": "matches preferred session length and attention window",
            "estimated_word_count": 80,
        }
    )

    prerequisites = [
        node["topic"]
        for node in context.get("mastery_nodes", [])
        if float(node.get("mastery_score", 0.5)) < 0.6
    ][:3]
    cautions = []
    if pace < 0.4:
        cautions.append("keep passages short; slow reader")
    if attention < 0.5:
        cautions.append("insert checkpoints to prevent drift")
    for hint in (context.get("recent_hints") or [])[:3]:
        cautions.append(hint)

    return {
        "topic": topic,
        "sections": sections,
        "prerequisites_to_reinforce": prerequisites,
        "cautions": cautions,
        "style_summary": context.get("style_summary_lines") or [],
    }


def _extract_json(raw: str) -> dict[str, Any]:
    match = re.search(r"\{.*\}", raw, re.DOTALL)
    if not match:
        return {}
    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError:
        return {}


async def generate_lesson_plan(
    student_id: int,
    topic: str,
    db: AsyncSession,
    *,
    material_id: int | None = None,
) -> dict[str, Any]:
    context = await build_learning_context(student_id, topic, db, material_id=material_id)
    settings = get_settings()
    if settings.resolved_llm_provider == "deterministic":
        return _deterministic_lesson_plan(topic, context)
    client = llm_client()
    style = "\n".join(context["style_summary_lines"])
    mastery = "\n".join(context["mastery_lines"]) or "(none yet)"
    hints = "; ".join(context["recent_hints"] or []) or "(none)"
    prompt = (
        f"Design a personalized lesson plan on '{topic}' for a specific student. "
        "Return ONLY JSON with this shape: "
        "{\"topic\": \"...\", \"sections\": [{\"title\": \"...\", \"angle\": \"...\", "
        "\"why_this_works_for_them\": \"...\", \"estimated_word_count\": 180}], "
        "\"prerequisites_to_reinforce\": [\"...\"], \"cautions\": [\"...\"]}.\n\n"
        f"STUDENT STYLE:\n{style}\n\n"
        f"TOPIC MASTERY:\n{mastery}\n\n"
        f"RECENT HINTS: {hints}\n"
    )
    response = await client.chat.completions.create(
        model=llm_model(),
        messages=[{"role": "user", "content": prompt}],
    )
    data = _extract_json(response.choices[0].message.content or "{}")
    if not data.get("sections"):
        raise RuntimeError("LLM returned no lesson plan sections")
    data.setdefault("topic", topic)
    data["style_summary"] = context.get("style_summary_lines") or []
    return data


async def retroactively_personalize(student_id: int, db: AsyncSession) -> int:
    materials = (
        await db.scalars(
            select(Material)
            .join(Enrollment, Enrollment.class_id == Material.class_id)
            .where(Enrollment.student_id == student_id, Material.published_at.is_not(None))
        )
    ).all()
    created = 0
    for material in materials:
        lesson = await personalize_lesson(student_id, material.id, db)
        if lesson is not None:
            created += 1
    return created
