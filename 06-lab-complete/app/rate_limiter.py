"""Redis-backed sliding-window rate limiting shared by every worker."""
import hashlib
import secrets
import time

from fastapi import HTTPException
from redis.exceptions import RedisError

from app.config import settings
from app.redis_client import r


_WINDOW_SECONDS = 60
_SLIDING_WINDOW_SCRIPT = """
local current_time = tonumber(ARGV[1])
local window_ms = tonumber(ARGV[2])
local limit = tonumber(ARGV[3])
local member = ARGV[4]

redis.call('ZREMRANGEBYSCORE', KEYS[1], '-inf', current_time - window_ms)
local count = redis.call('ZCARD', KEYS[1])
if count >= limit then
    return 0
end
redis.call('ZADD', KEYS[1], current_time, member)
redis.call('EXPIRE', KEYS[1], math.ceil(window_ms / 1000))
return 1
"""


def _redis_key(api_key: str) -> str:
    fingerprint = hashlib.sha256(api_key.encode("utf-8")).hexdigest()
    return f"rate_limit:{fingerprint}"


def check_rate_limit(key: str) -> None:
    """Allow at most ``RATE_LIMIT_PER_MINUTE`` requests per API key per 60 seconds."""
    now_ms = int(time.time() * 1000)
    member = f"{now_ms}:{secrets.token_hex(8)}"
    try:
        allowed = r.eval(
            _SLIDING_WINDOW_SCRIPT,
            1,
            _redis_key(key),
            now_ms,
            _WINDOW_SECONDS * 1000,
            settings.rate_limit_per_minute,
            member,
        )
    except (RedisError, OSError) as exc:
        raise HTTPException(status_code=503, detail="Rate limiter unavailable") from exc

    if not int(allowed):
        raise HTTPException(
            status_code=429,
            detail="Rate limit exceeded",
            headers={"Retry-After": str(_WINDOW_SECONDS)},
        )
