"""Fixed-window rate limiting backed by Redis. Used to throttle
verification submissions (abuse/score-manipulation prevention) and, via
middleware, general API traffic (API4 hardening for the main app)."""
from redis.asyncio import Redis

from app.core.config import settings

_redis: Redis | None = None


def get_redis() -> Redis:
    global _redis
    if _redis is None:
        _redis = Redis.from_url(settings.redis_url, decode_responses=True)
    return _redis


async def check_rate_limit(key: str, max_requests: int, window_seconds: int) -> bool:
    """Returns True if the request is allowed, False if the limit is exceeded."""
    r = get_redis()
    current = await r.incr(key)
    if current == 1:
        await r.expire(key, window_seconds)
    return current <= max_requests
