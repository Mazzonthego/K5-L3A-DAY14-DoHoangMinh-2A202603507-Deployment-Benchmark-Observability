"""API-key authentication for the agent endpoint."""
import secrets

from fastapi import HTTPException, Security
from fastapi.security import APIKeyHeader

from app.config import settings


api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def verify_api_key(x_api_key: str | None = Security(api_key_header)) -> str:
    """Validate ``X-API-Key`` and return the key used for rate-limit identity."""
    expected = settings.agent_api_key
    if not expected or not x_api_key:
        raise HTTPException(status_code=401, detail="Invalid or missing API key")
    if not secrets.compare_digest(x_api_key, expected):
        raise HTTPException(status_code=401, detail="Invalid or missing API key")
    return x_api_key
