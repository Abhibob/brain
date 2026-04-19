from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import (
    AssetFitScore,
    LessonAsset,
    LessonPlanDraft,
    LessonPlanEdge,
    LessonPlanNode,
    Material,
    MaterialSection,
    PersonalizedLesson,
    QuizQuestion,
)
from app.services import asset_generation, asset_scoring, youtube
from app.services.learning_profile import get_profile_snapshot
from app.services.rag import embed_text


VIDEO_RE = re.compile(r"^YT::([A-Za-z0-9_-]+)(?:::([\s\S]*))?$")


async def create_draft(
    db: AsyncSession,
    *,
    educator_id: int,
    student_id: int,
    class_id: int | None,
    topic: str,
    description: str | None,
) -> LessonPlanDraft:
    draft = LessonPlanDraft(
        educator_id=educator_id,
        student_id=student_id,
        class_id=class_id,
        topic=topic.strip(),
        description=description,
        status="draft",
    )
    db.add(draft)
    await db.commit()
    await db.refresh(draft)
    return draft


async def seed_draft_from_material(
    db: AsyncSession,
    draft: LessonPlanDraft,
    material: Material,
) -> list[LessonPlanNode]:
    """Turn an existing material's sections + quiz into draft nodes + candidate assets.

    Each reading section becomes a `reading` asset, video sections (content prefixed
    with `YT::<id>`) become `video` assets, and the material's quiz questions collapse
    into a single `quiz` asset appended at the end.
    """
    sections = sorted(material.sections, key=lambda s: s.order_index)
    snapshot = await get_profile_snapshot(draft.student_id, db)
    rows_to_persist: list[LessonAsset] = []

    for section in sections:
        content = section.content or ""
        match = VIDEO_RE.match(content.strip())
        if match:
            video_id = match.group(1)
            caption = (match.group(2) or "").strip()
            payload = {
                "title": section.title,
                "video_id": video_id,
                "description": caption,
                "duration_minutes": None,
                "url": f"https://www.youtube.com/watch?v={video_id}",
            }
            rows_to_persist.append(
                LessonAsset(
                    kind="video",
                    topic=material.title,
                    title=section.title,
                    payload=payload,
                    external_url=payload["url"],
                    generated_by="source",
                )
            )
        else:
            payload = {
                "title": section.title,
                "content": content,
                "estimated_word_count": section.word_count or len(content.split()),
                "style": "source-material",
            }
            rows_to_persist.append(
                LessonAsset(
                    kind="reading",
                    topic=material.title,
                    title=section.title,
                    payload=payload,
                    external_url=None,
                    generated_by="source",
                )
            )

    # Quiz from the material's existing questions (if any).
    questions = list(material.questions) if hasattr(material, "questions") else []
    if not questions:
        questions = (
            await db.scalars(select(QuizQuestion).where(QuizQuestion.material_id == material.id))
        ).all()
    if questions:
        quiz_payload = {
            "title": f"{material.title}: check for understanding",
            "difficulty": "core",
            "questions": [
                {
                    "question": q.question,
                    "options": list(q.options or []),
                    "correct_answer": q.correct_answer,
                    "points": q.points,
                }
                for q in questions
            ],
            "estimated_minutes": max(3, len(questions) * 1),
        }
        rows_to_persist.append(
            LessonAsset(
                kind="quiz",
                topic=material.title,
                title=f"{material.title}: check for understanding",
                payload=quiz_payload,
                external_url=None,
                generated_by="source",
            )
        )

    persisted = await _persist_assets(db, rows_to_persist)
    nodes: list[LessonPlanNode] = []
    for index, asset in enumerate(persisted):
        score = asset_scoring.score_asset_for_student(
            {"kind": asset.kind, "payload": asset.payload, "topic": asset.topic},
            snapshot,
        )
        existing_fit = await db.scalar(
            select(AssetFitScore).where(
                AssetFitScore.asset_id == asset.id,
                AssetFitScore.student_id == draft.student_id,
            )
        )
        if existing_fit is None:
            db.add(
                AssetFitScore(
                    asset_id=asset.id,
                    student_id=draft.student_id,
                    fit_score=score["fit_score"],
                    rationale=score["rationale"],
                    components=score["components"],
                )
            )
        else:
            existing_fit.fit_score = score["fit_score"]
            existing_fit.rationale = score["rationale"]
            existing_fit.components = score["components"]
        node = LessonPlanNode(
            draft_id=draft.id,
            asset_id=asset.id,
            order_index=index,
            label=asset.title,
            notes=score["rationale"],
            teacher_adjusted=False,
        )
        db.add(node)
        nodes.append(node)
    draft.status = "draft"
    draft.updated_at = datetime.now(UTC)
    await db.commit()
    return nodes


def _asset_rows(topic: str, generated: list[tuple[str, dict[str, Any], str | None, str]]) -> list[LessonAsset]:
    rows: list[LessonAsset] = []
    for kind, payload, external_url, generated_by in generated:
        title = str(payload.get("title") or f"{topic.title()} {kind}")
        rows.append(
            LessonAsset(
                kind=kind,
                topic=topic,
                title=title,
                payload=payload,
                external_url=external_url,
                generated_by=generated_by,
            )
        )
    return rows


async def _persist_assets(db: AsyncSession, assets: list[LessonAsset]) -> list[LessonAsset]:
    # Only embed LLM-generated candidates (those might be retrieved by vector
    # search later). Source-material assets are displayed in the builder and
    # never searched, so we skip the expensive per-asset embedding call.
    for asset in assets:
        if asset.generated_by == "source":
            asset.embedding = None
        else:
            asset.embedding = await embed_text(f"{asset.topic}\n{asset.title}")
        db.add(asset)
    await db.flush()
    return assets


async def generate_candidates(
    db: AsyncSession,
    draft: LessonPlanDraft,
) -> list[dict[str, Any]]:
    topic = draft.topic
    snapshot = await get_profile_snapshot(draft.student_id, db)
    style_vector = snapshot.get("style_vector") or {}

    reading = await asset_generation.generate_reading(topic, style_vector=style_vector)
    reading_review = await asset_generation.generate_reading(f"{topic} in review", style_vector=style_vector)
    quiz_core = await asset_generation.generate_quiz(topic, difficulty="core", style_vector=style_vector)
    quiz_challenge = await asset_generation.generate_quiz(topic, difficulty="challenge", style_vector=style_vector)
    practice = await asset_generation.generate_practice(topic, style_vector=style_vector)
    videos = await youtube.search_videos(topic, max_results=4)

    generated: list[tuple[str, dict[str, Any], str | None, str]] = [
        ("reading", reading, None, "llm"),
        ("reading", reading_review, None, "llm"),
        ("quiz", quiz_core, None, "llm"),
        ("quiz", quiz_challenge, None, "llm"),
        ("practice", practice, None, "llm"),
    ]
    for video in videos:
        generated.append(("video", video, video.get("url"), "youtube"))

    assets = await _persist_assets(db, _asset_rows(topic, generated))

    fit_scores: list[dict[str, Any]] = []
    for asset in assets:
        score = asset_scoring.score_asset_for_student(
            {"kind": asset.kind, "payload": asset.payload, "topic": asset.topic},
            snapshot,
        )
        existing = await db.scalar(
            select(AssetFitScore).where(
                AssetFitScore.asset_id == asset.id,
                AssetFitScore.student_id == draft.student_id,
            )
        )
        if existing is None:
            db.add(
                AssetFitScore(
                    asset_id=asset.id,
                    student_id=draft.student_id,
                    fit_score=score["fit_score"],
                    rationale=score["rationale"],
                    components=score["components"],
                )
            )
        else:
            existing.fit_score = score["fit_score"]
            existing.rationale = score["rationale"]
            existing.components = score["components"]
        fit_scores.append(
            {
                "asset": {
                    "id": asset.id,
                    "kind": asset.kind,
                    "title": asset.title,
                    "topic": asset.topic,
                    "payload": asset.payload,
                    "external_url": asset.external_url,
                    "generated_by": asset.generated_by,
                },
                "fit_score": score["fit_score"],
                "rationale": score["rationale"],
                "components": score["components"],
            }
        )
    await db.commit()
    return fit_scores


def _propose_order(candidates: list[dict[str, Any]], style_vector: dict[str, float]) -> list[dict[str, Any]]:
    visual = float(style_vector.get("visual_orientation", 0.5))
    attention = float(style_vector.get("attention_stability", 0.5))

    by_kind: dict[str, list[dict[str, Any]]] = {"video": [], "reading": [], "quiz": [], "practice": []}
    for cand in candidates:
        by_kind.setdefault(cand["asset"]["kind"], []).append(cand)
    for kind in by_kind:
        by_kind[kind].sort(key=lambda c: c["fit_score"], reverse=True)

    sequence: list[dict[str, Any]] = []
    readings = by_kind.get("reading", [])
    videos = by_kind.get("video", [])
    quizzes = by_kind.get("quiz", [])
    practices = by_kind.get("practice", [])

    if visual > 0.55 and videos:
        sequence.append(videos[0])
    if readings:
        sequence.append(readings[0])
    if visual <= 0.55 and videos:
        sequence.append(videos[0])
    if practices:
        sequence.append(practices[0])
    if quizzes:
        sequence.append(quizzes[0])
    if attention > 0.6 and readings and len(readings) > 1:
        sequence.append(readings[1])
    if quizzes and len(quizzes) > 1 and attention > 0.55:
        sequence.append(quizzes[1])

    seen: set[int] = set()
    deduped: list[dict[str, Any]] = []
    for item in sequence:
        aid = item["asset"]["id"]
        if aid in seen:
            continue
        seen.add(aid)
        deduped.append(item)
    return deduped


async def propose_sequence(
    db: AsyncSession,
    draft: LessonPlanDraft,
    candidates: list[dict[str, Any]],
) -> list[LessonPlanNode]:
    snapshot = await get_profile_snapshot(draft.student_id, db)
    ordered = _propose_order(candidates, snapshot.get("style_vector") or {})

    await db.execute(
        delete(LessonPlanNode).where(
            LessonPlanNode.draft_id == draft.id,
            LessonPlanNode.teacher_adjusted.is_(False),
        )
    )
    await db.flush()

    existing_adjusted = (
        await db.scalars(
            select(LessonPlanNode).where(
                LessonPlanNode.draft_id == draft.id,
                LessonPlanNode.teacher_adjusted.is_(True),
            )
        )
    ).all()
    adjusted_assets = {node.asset_id for node in existing_adjusted}

    start_index = len(existing_adjusted)
    nodes: list[LessonPlanNode] = []
    for offset, item in enumerate(ordered):
        asset_id = item["asset"]["id"]
        if asset_id in adjusted_assets:
            continue
        node = LessonPlanNode(
            draft_id=draft.id,
            asset_id=asset_id,
            order_index=start_index + offset,
            label=item["asset"].get("title"),
            notes=item.get("rationale"),
            teacher_adjusted=False,
        )
        db.add(node)
        nodes.append(node)

    draft.status = "ready"
    draft.updated_at = datetime.now(UTC)
    await db.commit()
    return nodes


async def get_draft_view(db: AsyncSession, draft_id: int) -> dict[str, Any]:
    draft = await db.scalar(select(LessonPlanDraft).where(LessonPlanDraft.id == draft_id))
    if draft is None:
        return {}
    nodes = (
        await db.scalars(
            select(LessonPlanNode)
            .where(LessonPlanNode.draft_id == draft_id)
            .order_by(LessonPlanNode.order_index.asc())
        )
    ).all()
    edges = (
        await db.scalars(
            select(LessonPlanEdge).where(LessonPlanEdge.draft_id == draft_id)
        )
    ).all()
    asset_ids = [node.asset_id for node in nodes]
    assets: dict[int, LessonAsset] = {}
    if asset_ids:
        for asset in (await db.scalars(select(LessonAsset).where(LessonAsset.id.in_(asset_ids)))).all():
            assets[asset.id] = asset

    fit_rows = (
        await db.scalars(
            select(AssetFitScore).where(
                AssetFitScore.student_id == draft.student_id,
                AssetFitScore.asset_id.in_(asset_ids or [0]),
            )
        )
    ).all() if asset_ids else []
    fit_map = {row.asset_id: row for row in fit_rows}

    candidate_rows = (
        await db.scalars(
            select(AssetFitScore).where(AssetFitScore.student_id == draft.student_id)
        )
    ).all()
    all_candidate_ids = [row.asset_id for row in candidate_rows]
    candidate_assets: dict[int, LessonAsset] = {}
    if all_candidate_ids:
        for asset in (await db.scalars(select(LessonAsset).where(LessonAsset.id.in_(all_candidate_ids)))).all():
            candidate_assets[asset.id] = asset

    return {
        "draft": {
            "id": draft.id,
            "educator_id": draft.educator_id,
            "student_id": draft.student_id,
            "class_id": draft.class_id,
            "topic": draft.topic,
            "description": draft.description,
            "status": draft.status,
            "created_at": draft.created_at,
            "updated_at": draft.updated_at,
        },
        "nodes": [
            {
                "id": node.id,
                "asset_id": node.asset_id,
                "order_index": node.order_index,
                "label": node.label,
                "notes": node.notes,
                "teacher_adjusted": node.teacher_adjusted,
                "asset": _serialize_asset(assets.get(node.asset_id)) if node.asset_id in assets else None,
                "fit_score": fit_map[node.asset_id].fit_score if node.asset_id in fit_map else None,
                "rationale": fit_map[node.asset_id].rationale if node.asset_id in fit_map else None,
            }
            for node in nodes
        ],
        "edges": [
            {
                "id": e.id,
                "from_node_id": e.from_node_id,
                "to_node_id": e.to_node_id,
                "condition": e.condition,
            }
            for e in edges
        ],
        "candidates": [
            {
                "asset": _serialize_asset(candidate_assets.get(row.asset_id)),
                "fit_score": row.fit_score,
                "rationale": row.rationale,
                "components": row.components,
            }
            for row in candidate_rows
            if row.asset_id in candidate_assets
        ],
    }


def _serialize_asset(asset: LessonAsset | None) -> dict[str, Any] | None:
    if asset is None:
        return None
    return {
        "id": asset.id,
        "kind": asset.kind,
        "topic": asset.topic,
        "title": asset.title,
        "payload": asset.payload,
        "external_url": asset.external_url,
        "generated_by": asset.generated_by,
    }


async def update_draft_nodes(
    db: AsyncSession,
    draft: LessonPlanDraft,
    nodes_patch: list[dict[str, Any]],
) -> None:
    """Replace the node sequence with teacher-provided order.

    Each item: {asset_id: int, order_index: int, label?, notes?, teacher_adjusted?}.
    """
    await db.execute(delete(LessonPlanNode).where(LessonPlanNode.draft_id == draft.id))
    await db.flush()
    for item in nodes_patch:
        asset_id = int(item["asset_id"])
        db.add(
            LessonPlanNode(
                draft_id=draft.id,
                asset_id=asset_id,
                order_index=int(item.get("order_index", 0)),
                label=item.get("label"),
                notes=item.get("notes"),
                teacher_adjusted=bool(item.get("teacher_adjusted", True)),
            )
        )
    draft.updated_at = datetime.now(UTC)
    await db.commit()


def _render_asset_section(asset: LessonAsset) -> tuple[str, str]:
    if asset.kind == "reading":
        content = asset.payload.get("content") or ""
        return asset.title, content
    if asset.kind == "video":
        video_id = asset.payload.get("video_id") or ""
        description = asset.payload.get("description") or ""
        if video_id:
            # Use the viewer-recognized YT:: marker so LessonViewer shows the embed.
            return asset.title, f"YT::{video_id}::{description}"
        url = asset.external_url or asset.payload.get("url") or ""
        return asset.title, f"[Watch: {asset.title}]({url})\n\n{description}"
    if asset.kind == "quiz":
        lines = [f"_{asset.title}_", ""]
        for q in asset.payload.get("questions") or []:
            lines.append(f"**{q.get('question', '')}**")
            for option in q.get("options") or []:
                lines.append(f"- {option}")
            lines.append("")
        return asset.title, "\n".join(lines)
    if asset.kind == "practice":
        lines = [f"_{asset.title}_", ""]
        for prob in asset.payload.get("problems") or []:
            lines.append(f"- {prob.get('prompt', '')}")
            hint = prob.get("hint")
            if hint:
                lines.append(f"  - hint: {hint}")
        return asset.title, "\n".join(lines)
    return asset.title, str(asset.payload)


async def publish_draft(
    db: AsyncSession,
    draft: LessonPlanDraft,
    *,
    target_material_id: int | None = None,
) -> Material:
    nodes = (
        await db.scalars(
            select(LessonPlanNode)
            .where(LessonPlanNode.draft_id == draft.id)
            .order_by(LessonPlanNode.order_index.asc())
        )
    ).all()
    if not nodes:
        raise ValueError("Draft has no nodes to publish")

    assets = {
        asset.id: asset
        for asset in (
            await db.scalars(
                select(LessonAsset).where(LessonAsset.id.in_([n.asset_id for n in nodes]))
            )
        ).all()
    }

    if target_material_id is not None:
        # Replace the existing material's sections + quiz.
        material = await db.scalar(
            select(Material)
            .where(Material.id == target_material_id)
            .options(selectinload(Material.sections), selectinload(Material.questions))
        )
        if material is None:
            raise ValueError(f"target material {target_material_id} not found")
        await db.execute(delete(MaterialSection).where(MaterialSection.material_id == material.id))
        # Rewrite quiz questions if the draft carries a quiz asset.
        quiz_asset = next(
            (assets[n.asset_id] for n in nodes if assets.get(n.asset_id) and assets[n.asset_id].kind == "quiz"),
            None,
        )
        if quiz_asset is not None:
            await db.execute(delete(QuizQuestion).where(QuizQuestion.material_id == material.id))
            for q in quiz_asset.payload.get("questions") or []:
                db.add(
                    QuizQuestion(
                        material_id=material.id,
                        question=str(q.get("question") or ""),
                        options=list(q.get("options") or []),
                        correct_answer=str(q.get("correct_answer") or ""),
                        points=float(q.get("points") or 1.0),
                    )
                )
        # Stale personalizations are no longer valid.
        await db.execute(
            delete(PersonalizedLesson).where(PersonalizedLesson.base_material_id == material.id)
        )
        material.published_at = datetime.now(UTC)
    else:
        if draft.class_id is None:
            raise ValueError("Cannot publish a brand-new material without a class_id")
        material = Material(
            class_id=draft.class_id,
            title=f"{draft.topic.title()} - personalized",
            type="lesson",
            order_index=0,
            published_at=datetime.now(UTC),
        )
        db.add(material)
    await db.flush()

    # Reading and video nodes become sections; the quiz node is not rendered as a
    # section (it powers the separate quiz flow).
    section_index = 0
    for node in nodes:
        asset = assets.get(node.asset_id)
        if asset is None or asset.kind == "quiz":
            continue
        title, content = _render_asset_section(asset)
        db.add(
            MaterialSection(
                material_id=material.id,
                title=title,
                content=content,
                order_index=section_index,
                word_count=len(content.split()),
            )
        )
        section_index += 1

    draft.status = "published"
    draft.updated_at = datetime.now(UTC)
    await db.commit()
    material = await db.scalar(
        select(Material)
        .where(Material.id == material.id)
        .options(selectinload(Material.sections))
    )
    return material
