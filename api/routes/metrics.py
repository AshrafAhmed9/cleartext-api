from fastapi import APIRouter, Depends
from sqlalchemy import func, text
from db.database import SessionLocal
from db.models import Prediction
import redis as redis_lib
from core.config import settings
from api.auth import get_current_user

router = APIRouter()
_redis = redis_lib.from_url(settings.redis_url)

@router.get("/metrics", tags=["System"])
def get_metrics(user: str = Depends(get_current_user)):
    db = SessionLocal()
    try:
        total = db.query(func.count(Prediction.id)).scalar() or 0
        completed = db.query(func.count(Prediction.id)).filter(Prediction.status == "completed").scalar() or 0
        failed = db.query(func.count(Prediction.id)).filter(Prediction.status == "failed").scalar() or 0
        queued = db.query(func.count(Prediction.id)).filter(Prediction.status == "queued").scalar() or 0

        avg_inference = db.query(func.avg(Prediction.processing_time_ms)).scalar() or 0.0
        max_inference = db.query(func.max(Prediction.processing_time_ms)).scalar() or 0.0

        # p95 — get top 5% of latencies
        all_latencies = [
            r[0] for r in db.query(Prediction.processing_time_ms)
            .filter(Prediction.processing_time_ms != None)
            .order_by(Prediction.processing_time_ms)
            .all()
        ]
        if all_latencies:
            p95_index = max(0, int(len(all_latencies) * 0.95) - 1)
            p95_inference = all_latencies[p95_index]
        else:
            p95_inference = 0.0

    finally:
        db.close()

    # Cache metrics from Redis
    hits = int(_redis.get("metrics:cache_hits") or 0)
    misses = int(_redis.get("metrics:cache_misses") or 0)
    total_cache = hits + misses
    hit_rate = round(hits / total_cache, 3) if total_cache > 0 else 0.0

    queue_depth = int(_redis.llen("celery") or 0)

    return {
        "jobs": {
            "total": total,
            "completed": completed,
            "failed": failed,
            "queued": queued,
        },
        "cache": {
            "hits": hits,
            "misses": misses,
            "hit_rate": hit_rate,
        },
        "queue": {
            "depth": queue_depth,
        },
        "latency": {
            "avg_inference_ms": round(float(avg_inference), 2),
            "p95_inference_ms": round(float(p95_inference), 2),
            "max_inference_ms": round(float(max_inference), 2),
        }
    }
