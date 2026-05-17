from fastapi import APIRouter
from sqlalchemy import text
import redis as redis_lib
from db.database import SessionLocal
from core.config import settings

router = APIRouter()
_redis = redis_lib.from_url(settings.redis_url)

@router.get("/health", tags=["System"])
def health():
    # Check Redis
    try:
        _redis.ping()
        redis_status = "ok"
    except Exception:
        redis_status = "error"

    # Check PostgreSQL
    try:
        db = SessionLocal()
        db.execute(text("SELECT 1"))
        db.close()
        db_status = "ok"
    except Exception:
        db_status = "error"

    # Queue depth
    try:
        queue_depth = int(_redis.llen("celery") or 0)
        queue_status = "ok"
    except Exception:
        queue_depth = -1
        queue_status = "error"

    overall = "ok" if all(s == "ok" for s in [redis_status, db_status, queue_status]) else "degraded"

    return {
        "status": overall,
        "version": "1.0.0",
        "services": {
            "redis": redis_status,
            "database": db_status,
            "queue": {"status": queue_status, "depth": queue_depth}
        }
    }
