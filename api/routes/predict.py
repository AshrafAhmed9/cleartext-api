from fastapi import APIRouter, Depends, Request
from celery.result import AsyncResult
from api.schemas import PredictRequest, PredictQueued, PredictResult
from api.auth import get_current_user
from core.cache import get_cached
from core.celery_app import celery_app
from core.logging_config import get_logger
import uuid

router = APIRouter()
logger = get_logger("audit")

@router.post("/predict", response_model=PredictResult)
def predict(request: Request, body: PredictRequest, user: str = Depends(get_current_user)):
    ip = request.client.host
    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))

    cached = get_cached(body.text)
    if cached:
        logger.info("cache hit", extra={
            "request_id": request_id,
            "ip": ip,
            "user": user,
            "prediction": cached["prediction"],
            "confidence": cached["confidence"],
        })
        return PredictResult(status="completed", cached=True, **cached)

    task_id = str(uuid.uuid4())
    celery_app.send_task("worker.tasks.run_inference", args=[task_id, body.text], task_id=task_id)

    logger.info("task queued", extra={
        "request_id": request_id,
        "ip": ip,
        "user": user,
    })

    return PredictQueued(task_id=task_id)

@router.get("/result/{task_id}", response_model=PredictResult)
def get_result(task_id: str, request: Request, user: str = Depends(get_current_user)):
    task = AsyncResult(task_id, app=celery_app)

    if task.state == "PENDING":
        return PredictResult(task_id=task_id, status="pending")

    if task.state == "FAILURE":
        return PredictResult(task_id=task_id, status="failed")

    result = task.result
    logger.info("result fetched", extra={
        "request_id": getattr(request.state, "request_id", task_id),
        "ip": request.client.host,
        "user": user,
        "prediction": result.get("prediction"),
        "confidence": result.get("confidence"),
        "processing_time_ms": result.get("processing_time_ms"),
    })
    return PredictResult(task_id=task_id, status="completed", **result)
