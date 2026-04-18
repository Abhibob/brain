from __future__ import annotations

import json
import re
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import Material, MaterialTopic
from app.services.llm import llm_client, llm_model
from app.settings import get_settings

STOPWORDS = {
    "the", "a", "an", "and", "or", "of", "to", "in", "on", "for", "with", "by",
    "is", "are", "was", "were", "be", "been", "being", "this", "that", "these",
    "those", "it", "its", "as", "at", "from", "but", "not", "no", "yes",
    "you", "your", "we", "our", "they", "their", "i", "me", "my", "he", "she",
    "how", "what", "when", "where", "why", "which", "who", "whose",
    "can", "will", "would", "should", "could", "may", "might", "do", "does",
    "did", "have", "has", "had", "into", "about", "then", "than", "so", "if",
    "lesson", "section", "chapter", "intro", "introduction", "summary",
}


def _tokenize(text: str) -> list[str]:
    return re.findall(r"[a-zA-Z][a-zA-Z\-']{2,}", text.lower())


def deterministic_topics(material: Material, *, max_topics: int = 5) -> list[str]:
    title_tokens = [tok for tok in _tokenize(material.title) if tok not in STOPWORDS]
    section_tokens: list[str] = []
    for section in material.sections:
        section_tokens.extend(tok for tok in _tokenize(section.title) if tok not in STOPWORDS)
    phrases: list[str] = []
    if len(title_tokens) >= 2:
        phrases.append(" ".join(title_tokens[:3]))
    phrases.extend(title_tokens)
    seen: set[str] = set()
    ordered: list[str] = []
    for phrase in phrases + section_tokens:
        normalized = phrase.strip().lower()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        ordered.append(normalized)
        if len(ordered) >= max_topics:
            break
    if not ordered:
        ordered = [material.title.strip().lower() or f"material-{material.id}"]
    return ordered


async def _llm_topics(material: Material, *, max_topics: int = 5) -> list[str]:
    client = llm_client()
    preview = "\n".join(f"- {s.title}: {s.content[:240]}" for s in list(material.sections)[:6])
    prompt = (
        "Extract 3 to 5 concise lowercase topic keywords or short phrases for this lesson. "
        "Return JSON: {\"topics\": [\"...\"]}.\n\n"
        f"Title: {material.title}\nSections:\n{preview}"
    )
    response = await client.chat.completions.create(
        model=llm_model(),
        messages=[{"role": "user", "content": prompt}],
    )
    raw = response.choices[0].message.content or "{}"
    try:
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        data = json.loads(match.group(0) if match else raw)
    except (json.JSONDecodeError, AttributeError):
        return deterministic_topics(material, max_topics=max_topics)
    topics = data.get("topics") or []
    cleaned: list[str] = []
    for topic in topics:
        if not isinstance(topic, str):
            continue
        norm = topic.strip().lower()
        if norm and norm not in cleaned:
            cleaned.append(norm)
    return cleaned[:max_topics] or deterministic_topics(material, max_topics=max_topics)


async def extract_topics_for_material(material_id: int, db: AsyncSession) -> list[str]:
    material = await db.scalar(
        select(Material).where(Material.id == material_id).options(selectinload(Material.sections))
    )
    if material is None:
        return []
    existing = (
        await db.scalars(select(MaterialTopic).where(MaterialTopic.material_id == material_id))
    ).all()
    if existing:
        return [row.topic for row in existing]

    settings = get_settings()
    if settings.resolved_llm_provider != "deterministic":
        topics = await _llm_topics(material)
    else:
        topics = deterministic_topics(material)

    for index, topic in enumerate(topics):
        weight = 1.0 - index * 0.1
        db.add(MaterialTopic(material_id=material_id, topic=topic, weight=max(weight, 0.4)))
    await db.commit()
    return topics


async def topics_for_materials(material_ids: list[int], db: AsyncSession) -> dict[int, list[str]]:
    if not material_ids:
        return {}
    rows = (
        await db.scalars(select(MaterialTopic).where(MaterialTopic.material_id.in_(material_ids)))
    ).all()
    result: dict[int, list[str]] = {mid: [] for mid in material_ids}
    for row in rows:
        result.setdefault(row.material_id, []).append(row.topic)
    return result
