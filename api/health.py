"""One endpoint that pings every dependency the API relies on.

Every check is wrapped: a health endpoint that throws when a dependency is
down is useless, because that's exactly when you need it to answer.
"""
from fastapi import APIRouter
from sqlalchemy import text
import redis as redis_lib
from db import SessionLocal
from core.config import settings, DLQ_KEY, HEARTBEAT_KEY

router = APIRouter()
_redis = redis_lib.from_url(settings.redis_url)


def _status_of(check) -> str:
    """"ok" if the check runs without raising, "error" if it doesn't."""
    try:
        check()
        return "ok"
    except Exception:
        return "error"


def _list_length(key: str) -> int:
    """How many items are in a Redis list; -1 means we couldn't ask."""
    try:
        return int(_redis.llen(key) or 0)
    except Exception:
        return -1


def _key_exists(key: str) -> bool:
    """Whether a Redis key is set; False if Redis can't be reached."""
    try:
        return bool(_redis.exists(key))
    except Exception:
        return False


def _ping_database():
    db = SessionLocal()
    try:
        db.execute(text("SELECT 1"))
    finally:
        db.close()


@router.get("/health", tags=["System"])
def health():
    redis_status = _status_of(_redis.ping)
    db_status = _status_of(_ping_database)
    queue_depth = _list_length("celery")
    dlq_depth = _list_length(DLQ_KEY)
    worker_alive = _key_exists(HEARTBEAT_KEY)

    healthy = redis_status == "ok" and db_status == "ok" and queue_depth >= 0 and worker_alive
    return {
        "status": "ok" if healthy else "degraded",
        "services": {
            "redis": redis_status,
            "database": db_status,
            "queue": {"status": "ok" if queue_depth >= 0 else "error", "depth": queue_depth},
            "dlq": {"depth": dlq_depth},
            "worker": {"alive": worker_alive},
        },
    }
