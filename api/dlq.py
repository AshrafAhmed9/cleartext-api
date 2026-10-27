"""Endpoints for looking at and replaying failed jobs.

When a job fails all its retries, the worker saves it in a Redis list called
the dead-letter queue (DLQ). These endpoints let you see that list and retry a job.
"""
import json

import redis as redis_lib
from fastapi import APIRouter, HTTPException

from core.celery_app import celery_app
from core.config import settings, DLQ_KEY

router = APIRouter(prefix="/dlq")
_redis = redis_lib.from_url(settings.redis_url)


@router.get("")
def list_dlq():
    """Show every failed job."""
    entries = [json.loads(raw) for raw in _redis.lrange(DLQ_KEY, 0, -1)]
    return {"depth": len(entries), "entries": entries}


@router.post("/{task_id}/replay")
def replay_dlq_entry(task_id: str):
    """Take one failed job out of the DLQ and put it back on the queue."""
    for raw in _redis.lrange(DLQ_KEY, 0, -1):
        entry = json.loads(raw)
        if entry["task_id"] == task_id:
            _redis.lrem(DLQ_KEY, 1, raw)
            celery_app.send_task("worker.tasks.run_inference", args=[task_id, entry["text"]], task_id=task_id)
            return {"status": "replayed", "task_id": task_id}
    raise HTTPException(status_code=404, detail="Task not found in DLQ")
