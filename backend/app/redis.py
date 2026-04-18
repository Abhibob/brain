from __future__ import annotations

from redis.asyncio import Redis

from app.settings import get_settings

def get_redis() -> Redis:
    return Redis.from_url(get_settings().redis_url, decode_responses=True)


async def close_redis() -> None:
    return None
