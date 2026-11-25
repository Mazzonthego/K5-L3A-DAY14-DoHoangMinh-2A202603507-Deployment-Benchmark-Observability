"""Redis-backed daily and monthly LLM cost guard."""
import hashlib
import math
from datetime import datetime, timezone

from fastapi import HTTPException
from redis.exceptions import RedisError

from app.config import settings
from app.redis_client import r


# USD per 1K tokens (reference pricing for a small production model).
PRICE_INPUT_PER_1K = 0.00015
PRICE_OUTPUT_PER_1K = 0.0006

_DAY_SECONDS = 2 * 24 * 60 * 60
_MONTH_SECONDS = 35 * 24 * 60 * 60


def _user_fingerprint(user_id: str) -> str:
    return hashlib.sha256(user_id.encode("utf-8")).hexdigest()[:24]


def _usage_keys(user_id: str) -> tuple[str, str]:
    now = datetime.now(timezone.utc)
    fingerprint = _user_fingerprint(user_id)
    daily = f"cost:daily:{fingerprint}:{now:%Y-%m-%d}"
    monthly = f"cost:monthly:{fingerprint}:{now:%Y-%m}"
    return daily, monthly


def check_budget(user_id: str = "global") -> None:
    """Reject the request before calling the LLM when a budget is exhausted."""
    daily_key, monthly_key = _usage_keys(user_id)
    try:
        daily_cost = float(r.get(daily_key) or 0.0)
        monthly_cost = float(r.get(monthly_key) or 0.0)
    except (RedisError, OSError) as exc:
        raise HTTPException(status_code=503, detail="Cost guard unavailable") from exc

    if (
        daily_cost >= settings.daily_budget_usd
        or monthly_cost >= settings.monthly_budget_usd
    ):
        raise HTTPException(status_code=402, detail="LLM budget exhausted")


def record_cost(input_tokens: int, output_tokens: int, user_id: str = "global") -> float:
    """Record this request's cost in Redis and return the request cost in USD."""
    request_cost = (
        max(0, input_tokens) / 1000 * PRICE_INPUT_PER_1K
        + max(0, output_tokens) / 1000 * PRICE_OUTPUT_PER_1K
    )
    daily_key, monthly_key = _usage_keys(user_id)
    try:
        pipe = r.pipeline(transaction=True)
        pipe.incrbyfloat(daily_key, request_cost)
        pipe.expire(daily_key, _DAY_SECONDS)
        pipe.incrbyfloat(monthly_key, request_cost)
        pipe.expire(monthly_key, _MONTH_SECONDS)
        pipe.execute()
    except (RedisError, OSError) as exc:
        raise HTTPException(status_code=503, detail="Cost guard unavailable") from exc
    return request_cost


def estimate_tokens(text: str) -> int:
    """Return a conservative, non-zero token estimate for the mock LLM."""
    return max(1, math.ceil(len(text) / 4))
