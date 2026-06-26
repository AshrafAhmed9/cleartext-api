from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from celery.result import AsyncResult
from api.schemas import PredictRequest, PredictQueued, PredictResult
from api.auth import get_current_user
from core.cache import get_cached
from core.celery_app import celery_app
from core.breaker import is_open
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

    # Circuit breaker: fail fast when the worker is down or overloaded.
    if is_open():
        return JSONResponse(
            status_code=503,
            headers={"Retry-After": "10"},
            content={"detail": "Service temporarily unavailable — worker is down or queue is full."},
        )

    task_id = str(uuid.uuid4())
    kwargs = {}
    if body.callback_url:
        kwargs["callback_url"] = body.callback_url
    celery_app.send_task(
        "worker.tasks.run_inference",
        args=[task_id, body.text],
        kwargs=kwargs,
        task_id=task_id,
    )

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
