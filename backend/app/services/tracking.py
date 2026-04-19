from __future__ import annotations

import json
from collections import Counter, defaultdict
from datetime import UTC, datetime, timedelta
from statistics import mean, variance
from typing import Any

from redis.asyncio import Redis
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import Material, SectionFocusScore, TrackingEvent, TrackingSession
from app.redis import get_redis
from app.services.focus import compute_focus_score, compute_section_focus
from app.services.gaze import extract_gaze_features


async def ingest_event(redis: Redis, session_id: int, event_type: str, data: dict[str, Any], client_ts: int) -> None:
    payload = {
        "event_type": event_type,
        "event_data": data,
        "client_ts": client_ts or int(datetime.now(UTC).timestamp() * 1000),
        "server_ts": datetime.now(UTC).isoformat(),
    }
    await redis.rpush(f"tracking:{session_id}", json.dumps(payload))


async def drain_buffered_events(redis: Redis, session_id: int) -> list[dict[str, Any]]:
    key = f"tracking:{session_id}"
    raw_events = await redis.lrange(key, 0, -1)
    if raw_events:
        await redis.delete(key)
    return [json.loads(item) for item in raw_events]


def _numeric(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _section_view_counts(events: list[dict[str, Any]]) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for event in events:
        if (event.get("event_type") or event.get("type")) != "section_view":
            continue
        data = event.get("event_data") or event.get("data") or {}
        sid = str(data.get("section_id") or data.get("sectionId") or "")
        if sid:
            counts[sid] += 1
    return dict(counts)


def compute_features(events: list[dict[str, Any]], material: Material, started_at: datetime, ended_at: datetime | None) -> dict[str, Any]:
    if ended_at is None:
        ended_at = datetime.now(UTC)
    # SQLite's func.now() returns naive datetimes; the API sets aware ones. Normalize.
    if started_at.tzinfo is None:
        started_at = started_at.replace(tzinfo=UTC)
    if ended_at.tzinfo is None:
        ended_at = ended_at.replace(tzinfo=UTC)
    duration_s = max((ended_at - started_at).total_seconds(), 0.0)
    if events:
        first_ts = min(_numeric(event.get("client_ts")) for event in events) / 1000
        last_ts = max(_numeric(event.get("client_ts")) for event in events) / 1000
        duration_s = max(duration_s, last_ts - first_ts)

    time_per_section: dict[str, float] = defaultdict(float)
    hover_durations: list[float] = []
    hover_per_section: Counter[str] = Counter()
    scroll_positions: list[float] = []
    scroll_velocities: list[float] = []
    mouse_velocities: list[float] = []
    idle_total_ms = 0.0
    idle_count = 0
    text_selection_count = 0
    section_views: Counter[str] = Counter()
    back_scroll_count = 0

    for event in events:
        event_type = event.get("event_type") or event.get("type")
        data = event.get("event_data") or event.get("data") or {}
        section_id = str(data.get("section_id") or data.get("sectionId") or "")
        if event_type == "section_view":
            if section_id:
                section_views[section_id] += 1
        elif event_type == "section_exit":
            if section_id:
                time_per_section[section_id] += _numeric(data.get("time_spent_ms")) / 1000
        elif event_type in {"hover_end", "hover"}:
            duration = _numeric(data.get("duration") or data.get("duration_ms"))
            if duration > 0:
                hover_durations.append(duration)
            if section_id:
                hover_per_section[section_id] += 1
        elif event_type == "scroll":
            scroll_positions.append(_numeric(data.get("position") or data.get("depth") or data.get("scroll_depth_pct")))
            scroll_velocities.append(abs(_numeric(data.get("velocity"))))
            if data.get("direction") == "up":
                back_scroll_count += 1
        elif event_type == "mouse_move":
            mouse_velocities.append(abs(_numeric(data.get("velocity"))))
        elif event_type == "idle_end":
            idle_count += 1
            idle_total_ms += _numeric(data.get("duration") or data.get("duration_ms"))
        elif event_type == "text_select":
            if _numeric(data.get("char_count")) > 0:
                text_selection_count += 1

    material_sections = list(material.sections)
    if not time_per_section and duration_s and material_sections:
        even_time = duration_s / len(material_sections)
        for section in material_sections:
            time_per_section[str(section.id)] = even_time

    total_words = sum(section.word_count for section in material_sections)
    section_time_minutes = max(sum(time_per_section.values()) / 60, 1 / 60)
    completed_sections = len(set(section_views.keys()) | set(time_per_section.keys()))
    section_count = max(len(material_sections), 1)

    features = {
        "total_time_s": round(duration_s, 3),
        "time_per_section": {key: round(value, 3) for key, value in time_per_section.items()},
        "hover_count": len(hover_durations),
        "avg_hover_duration_ms": round(mean(hover_durations), 3) if hover_durations else 0.0,
        "hover_per_section": dict(hover_per_section),
        "scroll_depth_pct": round(max(scroll_positions), 3) if scroll_positions else 0.0,
        "back_scroll_count": back_scroll_count,
        "scroll_velocity_avg": round(mean(scroll_velocities), 3) if scroll_velocities else 0.0,
        "mouse_velocity_avg": round(mean(mouse_velocities), 3) if mouse_velocities else 0.0,
        "mouse_velocity_variance": round(variance(mouse_velocities), 3) if len(mouse_velocities) > 1 else 0.0,
        "idle_total_s": round(idle_total_ms / 1000, 3),
        "idle_count": idle_count,
        "text_selection_count": text_selection_count,
        "re_read_sections": [section for section, count in section_views.items() if count > 1],
        "reading_speed_wpm": round(total_words / section_time_minutes, 3) if total_words else 0.0,
        "section_completion_rate": round(min(completed_sections / section_count, 1.0), 3),
    }

    gaze = extract_gaze_features(events, duration_s)
    if gaze:
        features.update(gaze)
        # Gaze reading time is more accurate than IntersectionObserver time;
        # prefer it where available so downstream signals see the true attention window.
        gaze_per_section = gaze.get("gaze_time_per_section") or {}
        if gaze_per_section:
            for key, value in gaze_per_section.items():
                if value and value > 0:
                    features["time_per_section"][key] = round(float(value), 3)

    return features


async def persist_and_compute_features(session_id: int, db: AsyncSession) -> dict[str, Any]:
    session = await db.scalar(
        select(TrackingSession)
        .where(TrackingSession.id == session_id)
        .options(selectinload(TrackingSession.material).selectinload(Material.sections))
    )
    if session is None:
        raise ValueError(f"Tracking session {session_id} not found")

    redis = get_redis()
    try:
        buffered_events = await drain_buffered_events(redis, session_id)
    finally:
        await redis.aclose()
    await ensure_weekly_tracking_partition(db)
    for event in buffered_events:
        db.add(
            TrackingEvent(
                session_id=session_id,
                event_type=event["event_type"],
                event_data=event["event_data"],
                client_ts=event["client_ts"],
            )
        )
    await db.flush()

    db_events = (
        await db.scalars(
            select(TrackingEvent)
            .where(TrackingEvent.session_id == session_id)
            .order_by(TrackingEvent.client_ts.asc(), TrackingEvent.id.asc())
        )
    ).all()
    normalized = [
        {"event_type": event.event_type, "event_data": event.event_data, "client_ts": event.client_ts}
        for event in db_events
    ]
    features = compute_features(normalized, session.material, session.started_at, session.ended_at)
    session.features = features

    focus = compute_focus_score(features)
    session.focus_score = focus["focus_score"]
    session.focus_breakdown = focus["breakdown"]
    session.focus_label = focus["label"]

    section_meta = [
        {"section_id": section.id, "word_count": section.word_count, "title": section.title}
        for section in session.material.sections
    ]
    section_times = {key: float(value) for key, value in (features.get("time_per_section") or {}).items()}
    view_counts = _section_view_counts(normalized)
    section_focus_rows = compute_section_focus(normalized, section_meta, section_times, view_counts)

    existing_rows = (
        await db.scalars(
            select(SectionFocusScore).where(SectionFocusScore.session_id == session_id)
        )
    ).all()
    existing_by_section = {row.section_id: row for row in existing_rows}
    for row in section_focus_rows:
        stored = existing_by_section.get(row["section_id"])
        if stored is None:
            db.add(
                SectionFocusScore(
                    session_id=session_id,
                    section_id=row["section_id"],
                    focus_score=row["focus_score"],
                    breakdown=row["breakdown"],
                    label=row["label"],
                )
            )
        else:
            stored.focus_score = row["focus_score"]
            stored.breakdown = row["breakdown"]
            stored.label = row["label"]

    await db.commit()
    return features


async def ensure_weekly_tracking_partition(db: AsyncSession) -> None:
    if not db.bind or db.bind.dialect.name != "postgresql":
        return
    now = datetime.now(UTC)
    start = (now - timedelta(days=now.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
    end = start + timedelta(days=7)
    partition_name = f"tracking_events_y{start:%Y}_w{start:%W}"
    await db.execute(
        text(
            f"""
            CREATE TABLE IF NOT EXISTS {partition_name}
            PARTITION OF tracking_events
            FOR VALUES FROM ('{start.isoformat()}') TO ('{end.isoformat()}')
            """
        )
    )
