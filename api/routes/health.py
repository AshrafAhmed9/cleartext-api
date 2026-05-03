from fastapi import APIRouter
import redis as redis_lib
from core.config import settings

router = APIRouter()

@router.get("/health")
def health():
    try:
        r = redis_lib.from_url(settings.redis_url)
        r.ping()
        redis_status = "ok"
    except Exception:
        redis_status = "error"

    return {"status": "ok", "redis": redis_status}
