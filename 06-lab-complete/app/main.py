"""Production-ready FastAPI application for the Day 14 lab."""
import json
import logging
import sys
import time
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import Depends, FastAPI, HTTPException, Request
from pydantic import BaseModel, Field

from app.auth import verify_api_key
from app.config import settings
from app.cost_guard import check_budget, estimate_tokens, record_cost
from app.rate_limiter import check_rate_limit
from app.redis_client import close_redis, redis_healthy
from utils.mock_llm import ask as llm_ask


class JsonFormatter(logging.Formatter):
    """Serialize every application log record as one JSON object."""

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for field in ("event", "method", "path", "status_code", "duration_ms"):
            if hasattr(record, field):
                payload[field] = getattr(record, field)
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


handler = logging.StreamHandler(sys.stdout)
handler.setFormatter(JsonFormatter())
root_logger = logging.getLogger()
root_logger.handlers.clear()
root_logger.addHandler(handler)
root_logger.setLevel(settings.log_level.upper())
logger = logging.getLogger("app.main")


@asynccontextmanager
async def lifespan(_: FastAPI):
    """Close shared resources after uvicorn finishes in-flight requests."""
    logger.info("agent_started", extra={"event": "startup"})
    yield
    close_redis()
    logger.info("agent_stopped", extra={"event": "shutdown"})


app = FastAPI(title="Production AI Agent", lifespan=lifespan)


class AskRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=2000)
    user_id: str | None = Field(default=None, max_length=200)


@app.middleware("http")
async def request_logging(request: Request, call_next):
    started = time.perf_counter()
    response = await call_next(request)
    duration_ms = round((time.perf_counter() - started) * 1000, 2)
    logger.info(
        "request_completed",
        extra={
            "event": "request",
            "method": request.method,
            "path": request.url.path,
            "status_code": response.status_code,
            "duration_ms": duration_ms,
        },
    )
    return response


@app.get("/health")
def health():
    """Liveness probe: the process is healthy even when Redis is unavailable."""
    return {"status": "ok"}


@app.get("/ready")
def ready():
    """Readiness probe: accept traffic only when Redis is reachable."""
    if not redis_healthy():
        raise HTTPException(status_code=503, detail="Redis is not ready")
    return {"status": "ready", "redis": "ok"}


@app.post("/ask")
def ask(body: AskRequest, api_key: str = Depends(verify_api_key)):
    """Authenticate, enforce shared limits, call the LLM, then record its cost."""
    check_rate_limit(api_key)
    check_budget(api_key)

    answer = llm_ask(body.question)
    input_tokens = estimate_tokens(body.question)
    output_tokens = estimate_tokens(answer)
    request_cost = record_cost(input_tokens, output_tokens, api_key)

    return {
        "question": body.question,
        "answer": answer,
        "usage": {
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "cost_usd": request_cost,
        },
    }
