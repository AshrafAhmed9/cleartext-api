"""Dead-letter queue inspection and replay endpoints.

Failed inference jobs are pushed to a Redis list (dlq:inference) by the worker.
These endpoints let an operator inspect and replay them.
"""
import json
from typing import List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException
import redis as redis_lib
from api.auth import get_current_user
from core.config import settings
from core.celery_app import celery_app

router = APIRouter(prefix="/dlq", tags=["Reliability"])
_redis = redis_lib.from_url(settings.redis_url)
DLQ_KEY = "dlq:inference"


@router.get("", response_model=Dict[str, Any])
def list_dlq(user: str = Depends(get_current_user)):
    """List all entries in the inference dead-letter queue."""
    raw_entries = _redis.lrange(DLQ_KEY, 0, -1)
    entries = [json.loads(e) for e in raw_entries]
    return {"depth": len(entries), "entries": entries}


@router.post("/{task_id}/replay")
def replay_dlq_entry(task_id: str, user: str = Depends(get_current_user)):
    """Re-enqueue a dead-lettered inference job."""
    raw_entries = _redis.lrange(DLQ_KEY, 0, -1)
    for raw in raw_entries:
        entry = json.loads(raw)
        if entry.get("task_id") == task_id:
            _redis.lrem(DLQ_KEY, 1, raw)
            celery_app.send_task("worker.tasks.run_inference", args=[task_id, entry["text"]], task_id=task_id)
            return {"status": "replayed", "task_id": task_id}
    raise HTTPException(status_code=404, detail="Task not found in DLQ")
