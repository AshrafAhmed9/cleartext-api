from fastapi import APIRouter, Depends
from celery.result import AsyncResult
from api.schemas import PredictRequest, PredictQueued, PredictResult
from api.auth import get_current_user
from core.cache import get_cached
from core.celery_app import celery_app   # ← only import celery_app, not the task
import uuid

router = APIRouter()

@router.post("/predict", response_model=PredictResult)
def predict(request: PredictRequest, user: str = Depends(get_current_user)):
    cached = get_cached(request.text)
    if cached:
        return PredictResult(status="completed", cached=True, **cached)

    task_id = str(uuid.uuid4())
    # Send by name — API doesn't need to import or load the model
    celery_app.send_task("worker.tasks.run_inference", args=[task_id, request.text], task_id=task_id)

    return PredictQueued(task_id=task_id)

@router.get("/result/{task_id}", response_model=PredictResult)
def get_result(task_id: str, user: str = Depends(get_current_user)):
    task = AsyncResult(task_id, app=celery_app)

    if task.state == "PENDING":
        return PredictResult(task_id=task_id, status="pending")

    if task.state == "FAILURE":
        return PredictResult(task_id=task_id, status="failed")

    result = task.result
    return PredictResult(task_id=task_id, status="completed", **result)
