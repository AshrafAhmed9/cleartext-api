"""The Celery task that turns one comment into a stored prediction.

Flow: mark the row "processing" -> hand the text to the micro-batcher (which
does the actual model call) -> save the result -> cache it. If the model call
raises, retry with exponential backoff up to 3 times; on the final failure,
push the job to the dead-letter queue instead of losing it silently.
"""
import json
import time
import traceback
from datetime import datetime

import redis as redis_lib

from core.celery_app import celery_app
from core.cache import set_cached
from core.config import settings, DLQ_KEY
from core import metrics
from db import SessionLocal, Prediction
from worker.batcher import get_batcher
from worker import bootstrap  # noqa: F401  (registers worker_ready signal)

_redis = redis_lib.from_url(settings.redis_url)


def _mark_processing(db, task_id: str):
    row = db.query(Prediction).filter(Prediction.request_id == task_id).first()
    if row:
        row.status = "processing"
        row.started_at = datetime.utcnow()
        db.commit()
    return row


def _save_result(db, row, task_id: str, text: str, result: dict, processing_time_ms: float):
    if row is None:
        row = Prediction(request_id=task_id, input_text=text, started_at=datetime.utcnow())
        db.add(row)
    row.prediction = result["prediction"]
    row.confidence = result["confidence"]
    row.model_version = result["model_version"]
    row.processing_time_ms = processing_time_ms
    row.status = "completed"
    db.commit()


def _send_to_dlq(db, task_id: str, text: str, exc: Exception):
    row = db.query(Prediction).filter(Prediction.request_id == task_id).first()
    if row:
        row.status = "failed"
        db.commit()
    _redis.lpush(DLQ_KEY, json.dumps({
        "task_id": task_id,
        "text": text,
        "error": str(exc),
        "traceback": traceback.format_exc(),
        "model_version": settings.ml_model_version,
        "failed_at": datetime.utcnow().isoformat(),
    }))


@celery_app.task(bind=True, max_retries=3)
def run_inference(self, task_id: str, text: str):
    db = SessionLocal()
    metrics.WORKER_INFLIGHT.inc()
    try:
        row = _mark_processing(db, task_id)

        start = time.time()
        result = get_batcher().submit(text)
        processing_time_ms = round((time.time() - start) * 1000, 2)
        metrics.END_TO_END_LATENCY.observe(time.time() - start)
        metrics.PREDICTIONS_TOTAL.labels(result=result["prediction"]).inc()

        _save_result(db, row, task_id, text, result, processing_time_ms)
        set_cached(text, result)
        return {**result, "processing_time_ms": processing_time_ms}

    except Exception as exc:
        if self.request.retries >= self.max_retries:
            _send_to_dlq(db, task_id, text, exc)
            raise
        raise self.retry(exc=exc, countdown=2 ** self.request.retries)

    finally:
        metrics.WORKER_INFLIGHT.dec()
        db.close()
