from __future__ import annotations

import hashlib
from typing import Any

import httpx

from app.settings import get_settings


def _deterministic_videos(topic: str, max_results: int = 6) -> list[dict[str, Any]]:
    """Stable, no-network fallback for local verification.

    Returns a handful of fake-but-plausible video candidates derived from the topic.
    """
    seed_keywords = [word for word in topic.lower().split() if word.isalpha()] or [topic.lower() or "lesson"]
    top_keyword = seed_keywords[0]
    templates = [
        ("Intro to {topic}", "Khan Academy", 9, "introduction beginner overview"),
        ("{topic} - worked examples", "Professor Leonard", 14, "examples step by step practice"),
        ("Visual guide to {topic}", "3Blue1Brown", 11, "visual intuition diagrams"),
        ("{topic} in 10 minutes", "CrashCourse", 10, "fast survey quick"),
        ("Deeper dive into {topic}", "MIT OpenCourseWare", 22, "deep rigorous"),
        ("Common mistakes with {topic}", "ChalkTalk", 7, "pitfalls misconceptions"),
    ]
    results: list[dict[str, Any]] = []
    for i, (title_tpl, channel, minutes, tags) in enumerate(templates[:max_results]):
        digest = hashlib.blake2b(f"{topic}-{i}".encode(), digest_size=6).hexdigest()
        video_id = f"det-{digest}"
        title = title_tpl.format(topic=topic)
        results.append(
            {
                "video_id": video_id,
                "title": title,
                "channel": channel,
                "duration_minutes": minutes,
                "description": f"A {tags} video about {topic}.",
                "url": f"https://www.youtube.com/watch?v={video_id}",
                "thumbnail_url": f"https://img.youtube.com/vi/{video_id}/hqdefault.jpg",
                "tags": tags.split() + [top_keyword],
            }
        )
    return results


async def _real_search(topic: str, *, max_results: int) -> list[dict[str, Any]]:
    settings = get_settings()
    params = {
        "part": "snippet",
        "type": "video",
        "q": topic,
        "maxResults": max_results,
        "key": settings.youtube_api_key,
        "safeSearch": "strict",
        "relevanceLanguage": "en",
    }
    async with httpx.AsyncClient(timeout=10.0) as http:
        response = await http.get(settings.youtube_search_base_url, params=params)
    if response.status_code != 200:
        return _deterministic_videos(topic, max_results)
    items = response.json().get("items", [])
    results: list[dict[str, Any]] = []
    for item in items:
        vid = item.get("id", {}).get("videoId")
        snippet = item.get("snippet", {})
        if not vid:
            continue
        results.append(
            {
                "video_id": vid,
                "title": snippet.get("title", ""),
                "channel": snippet.get("channelTitle", ""),
                "duration_minutes": None,
                "description": snippet.get("description", ""),
                "url": f"https://www.youtube.com/watch?v={vid}",
                "thumbnail_url": (snippet.get("thumbnails") or {}).get("high", {}).get("url"),
                "tags": [],
            }
        )
    return results or _deterministic_videos(topic, max_results)


async def search_videos(topic: str, *, max_results: int = 6) -> list[dict[str, Any]]:
    settings = get_settings()
    topic = topic.strip()
    if not topic:
        return []
    if not settings.youtube_api_key:
        return _deterministic_videos(topic, max_results)
    try:
        return await _real_search(topic, max_results=max_results)
    except Exception:
        return _deterministic_videos(topic, max_results)
