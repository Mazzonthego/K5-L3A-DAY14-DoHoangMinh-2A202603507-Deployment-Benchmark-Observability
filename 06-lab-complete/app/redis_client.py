"""Shared Redis client used by readiness, rate limiting, and cost accounting."""
import redis
from redis.exceptions import RedisError

from app.config import settings


# ``from_url`` creates the client lazily; it does not connect during import.
r = redis.Redis.from_url(
    settings.redis_url,
    decode_responses=True,
    socket_connect_timeout=0.5,
    socket_timeout=0.5,
    retry_on_timeout=False,
    health_check_interval=30,
)


def redis_healthy() -> bool:
    """Return whether Redis currently responds to PING."""
    try:
        return bool(r.ping())
    except (RedisError, OSError):
        return False


def close_redis() -> None:
    """Close the client during graceful shutdown without deleting stored state."""
    try:
        r.close()
    except (RedisError, OSError):
        pass
