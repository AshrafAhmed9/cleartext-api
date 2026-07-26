"""Two ways to read the same numbers: JSON for a human, text for Prometheus."""
from fastapi import APIRouter, Depends, Response
from sqlalchemy import func
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
from db import SessionLocal, Prediction
import redis as redis_lib
from core.config import settings, DLQ_KEY
from api.auth import get_current_user

router = APIRouter()
_redis = redis_lib.from_url(settings.redis_url)


def _count(db, **filters) -> int:
    query = db.query(func.count(Prediction.id))
    for column, value in filters.items():
        query = query.filter(getattr(Prediction, column) == value)
    return query.scalar() or 0


def _percentile(sorted_values: list, pct: float) -> float:
    """pct is 0-1. Nearest-rank method: no interpolation, good enough for a metrics endpoint."""
    if not sorted_values:
        return 0.0
    index = max(0, int(len(sorted_values) * pct) - 1)
    return sorted_values[index]


def _job_counts(db) -> dict:
    return {
        "total": _count(db),
        "completed": _count(db, status="completed"),
        "failed": _count(db, status="failed"),
        "queued": _count(db, status="queued"),
    }


def _latency_stats(db) -> dict:
    latencies = [
        row[0] for row in db.query(Prediction.processing_time_ms)
        .filter(Prediction.processing_time_ms.isnot(None))
        .order_by(Prediction.processing_time_ms)
        .all()
    ]
    avg = (sum(latencies) / len(latencies)) if latencies else 0.0
    return {
        "avg_inference_ms": round(avg, 2),
        "p50_inference_ms": round(_percentile(latencies, 0.50), 2),
        "p95_inference_ms": round(_percentile(latencies, 0.95), 2),
        "p99_inference_ms": round(_percentile(latencies, 0.99), 2),
        "max_inference_ms": round(max(latencies, default=0.0), 2),
    }


def _cache_stats() -> dict:
    hits = int(_redis.get("metrics:cache_hits") or 0)
    misses = int(_redis.get("metrics:cache_misses") or 0)
    total = hits + misses
    return {"hits": hits, "misses": misses, "hit_rate": round(hits / total, 3) if total else 0.0}


@router.get("/metrics", tags=["System"])
def get_metrics(user: str = Depends(get_current_user)):
    db = SessionLocal()
    try:
        jobs = _job_counts(db)
        latency = _latency_stats(db)
    finally:
        db.close()

    return {
        "jobs": jobs,
        "cache": _cache_stats(),
        "queue": {"depth": int(_redis.llen("celery") or 0)},
        "dlq": {"depth": int(_redis.llen(DLQ_KEY) or 0)},
        "latency": latency,
    }


@router.get("/metrics/prometheus", tags=["System"], include_in_schema=False)
def prometheus_metrics():
    """Prometheus text exposition format — scrapeable at /metrics/prometheus."""
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)
