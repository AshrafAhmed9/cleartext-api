"""Two ways to read the same numbers: JSON for a human, text for Prometheus."""
from fastapi import APIRouter, Depends, Response
from sqlalchemy import func
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
from db import SessionLocal, Prediction
import redis as redis_lib
from core.config import settings
from api.auth import get_current_user

router = APIRouter()
_redis = redis_lib.from_url(settings.redis_url)

DLQ_KEY = "dlq:inference"


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

        all_latencies = [
            r[0] for r in db.query(Prediction.processing_time_ms)
            .filter(Prediction.processing_time_ms != None)
            .order_by(Prediction.processing_time_ms)
            .all()
        ]
        if all_latencies:
            p50_index = max(0, int(len(all_latencies) * 0.50) - 1)
            p95_index = max(0, int(len(all_latencies) * 0.95) - 1)
            p99_index = max(0, int(len(all_latencies) * 0.99) - 1)
            p50_inference = all_latencies[p50_index]
            p95_inference = all_latencies[p95_index]
            p99_inference = all_latencies[p99_index]
        else:
            p50_inference = 0.0
            p95_inference = 0.0
            p99_inference = 0.0

    finally:
        db.close()

    hits = int(_redis.get("metrics:cache_hits") or 0)
    misses = int(_redis.get("metrics:cache_misses") or 0)
    total_cache = hits + misses
    hit_rate = round(hits / total_cache, 3) if total_cache > 0 else 0.0

    queue_depth = int(_redis.llen("celery") or 0)
    dlq_depth = int(_redis.llen(DLQ_KEY) or 0)

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
        "dlq": {
            "depth": dlq_depth,
        },
        "latency": {
            "avg_inference_ms": round(float(avg_inference), 2),
            "p50_inference_ms": round(float(p50_inference), 2),
            "p95_inference_ms": round(float(p95_inference), 2),
            "p99_inference_ms": round(float(p99_inference), 2),
            "max_inference_ms": round(float(max_inference), 2),
        }
    }


@router.get("/metrics/prometheus", tags=["System"], include_in_schema=False)
def prometheus_metrics():
    """Prometheus text exposition format — scrapeable at /metrics/prometheus."""
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)
