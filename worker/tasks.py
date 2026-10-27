"""The Celery task that classifies one comment and stores the result.

Steps: mark the Postgres row "processing" -> run the model through the
micro-batcher -> save the result in Postgres and the cache. If the model
fails, retry up to 3 times, waiting 1s, 2s, then 4s. After the last failure,
save the job in the dead-letter queue so it isn't lost.
"""
import json
import time
import traceback
from datetime import datetime

import redis as redis_lib

from core.cache import set_cached
from core.celery_app import celery_app
from core.config import settings, DLQ_KEY
from db import SessionLocal, Prediction
from worker.batcher import get_batcher

_redis = redis_lib.from_url(settings.redis_url)


def _mark_processing(db, task_id: str):
    """Set the row's status to "processing" and return the row (None if missing)."""
    row = db.query(Prediction).filter(Prediction.request_id == task_id).first()
    if row:
        row.status = "processing"
        row.started_at = datetime.utcnow()
        db.commit()
    return row


def _save_result(db, row, task_id: str, text: str, result: dict, processing_time_ms: float):
    """Write the finished prediction to Postgres, creating the row if it was missing."""
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
    """Mark the row "failed" and save the job, error and traceback in the DLQ."""
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
    try:
        row = _mark_processing(db, task_id)

        start = time.time()
        result = get_batcher().submit(text)
        processing_time_ms = round((time.time() - start) * 1000, 2)

        _save_result(db, row, task_id, text, result, processing_time_ms)
        set_cached(text, result)
        return {**result, "processing_time_ms": processing_time_ms}

    except Exception as exc:
        # Out of retries: park the job in the DLQ. Otherwise retry after 1s, 2s, 4s.
        if self.request.retries >= self.max_retries:
            _send_to_dlq(db, task_id, text, exc)
            raise
        raise self.retry(exc=exc, countdown=2 ** self.request.retries)

    finally:
        db.close()
