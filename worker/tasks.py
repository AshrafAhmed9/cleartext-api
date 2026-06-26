import time
import json
import traceback
from typing import Optional
from datetime import datetime

import httpx
import redis as redis_lib

from core.celery_app import celery_app
from core.cache import set_cached
from core.config import settings
from core import metrics
from db.database import SessionLocal
from db.models import Prediction
from worker.batcher import get_batcher
from worker import bootstrap  # noqa: F401  (registers worker_ready signal)

_redis = redis_lib.from_url(settings.redis_url)
DLQ_KEY = "dlq:inference"


def _send_webhook(callback_url: str, payload: dict):
    try:
        with httpx.Client(timeout=5.0) as client:
            client.post(callback_url, json=payload)
    except Exception:
        _redis.lpush("dlq:webhook", json.dumps({
            "callback_url": callback_url,
            "payload": payload,
            "failed_at": datetime.utcnow().isoformat(),
        }))


@celery_app.task(bind=True, max_retries=3)
def run_inference(self, task_id: str, text: str, callback_url: Optional[str] = None):
    db = SessionLocal()
    metrics.WORKER_INFLIGHT.inc()
    try:
        row = db.query(Prediction).filter(Prediction.request_id == task_id).first()
        if row:
            row.status = "processing"
            row.started_at = datetime.utcnow()
            db.commit()

        start = time.time()
        result = get_batcher().submit(text)
        processing_time = round((time.time() - start) * 1000, 2)
        metrics.END_TO_END_LATENCY.observe(time.time() - start)
        metrics.PREDICTIONS_TOTAL.labels(result=result["prediction"]).inc()

        if row:
            row.prediction = result["prediction"]
            row.confidence = result["confidence"]
            row.model_version = result["model_version"]
            row.processing_time_ms = processing_time
            row.status = "completed"
            db.commit()
        else:
            db.add(Prediction(
                request_id=task_id,
                input_text=text,
                prediction=result["prediction"],
                confidence=result["confidence"],
                model_version=result["model_version"],
                processing_time_ms=processing_time,
                status="completed",
                started_at=datetime.utcnow(),
            ))
            db.commit()

        set_cached(text, result)
        payload = dict(result)
        payload["processing_time_ms"] = processing_time
        if callback_url:
            _send_webhook(callback_url, {"task_id": task_id, "status": "completed", **payload})
        return payload

    except Exception as exc:
        if self.request.retries >= self.max_retries:
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
                "callback_url": callback_url,
                "failed_at": datetime.utcnow().isoformat(),
            }))
            if callback_url:
                _send_webhook(callback_url, {"task_id": task_id, "status": "failed", "error": str(exc)})
            db.close()
            raise

        db.close()
        raise self.retry(exc=exc, countdown=2 ** self.request.retries)

    finally:
        metrics.WORKER_INFLIGHT.dec()
        db.close()
