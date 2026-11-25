"""Application configuration loaded from environment variables."""
import os
from dataclasses import dataclass, field


def _int_env(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None or value.strip() == "":
        return default
    try:
        return int(value)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer") from exc


def _float_env(name: str, default: float) -> float:
    value = os.getenv(name)
    if value is None or value.strip() == "":
        return default
    try:
        return float(value)
    except ValueError as exc:
        raise ValueError(f"{name} must be a number") from exc


@dataclass(frozen=True)
class Settings:
    port: int = field(default_factory=lambda: _int_env("PORT", 8000))
    environment: str = field(default_factory=lambda: os.getenv("ENVIRONMENT", "development"))
    agent_api_key: str = field(default_factory=lambda: os.getenv("AGENT_API_KEY", ""))
    redis_url: str = field(
        default_factory=lambda: os.getenv("REDIS_URL", "redis://localhost:6379/0")
    )
    rate_limit_per_minute: int = field(
        default_factory=lambda: _int_env("RATE_LIMIT_PER_MINUTE", 10)
    )
    daily_budget_usd: float = field(
        default_factory=lambda: _float_env("DAILY_BUDGET_USD", 1.0)
    )
    monthly_budget_usd: float = field(
        default_factory=lambda: _float_env("MONTHLY_BUDGET_USD", 10.0)
    )
    log_level: str = field(default_factory=lambda: os.getenv("LOG_LEVEL", "INFO"))


settings = Settings()
