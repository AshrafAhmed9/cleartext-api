"""Submit a comment for toxicity scoring, and check on the result.

POST /predict never runs the model inline. It either serves a cached answer,
rejects fast if the worker looks unhealthy, or hands the text to Celery and
returns immediately with a task_id. GET /result/{task_id} is how the caller
finds out what happened.
"""
import uuid
from typing import Optional

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, field_validator
from celery.result import AsyncResult

from api.auth import get_current_user
from core.cache import get_cached
from core.celery_app import celery_app
from core.breaker import is_open
from db import SessionLocal, Prediction

router = APIRouter()


class PredictRequest(BaseModel):
    text: str = Field(min_length=1, max_length=5000)

    @field_validator("text")
    @classmethod
    def strip_and_require_nonempty(cls, v):
        v = " ".join(v.split())
        if not v:
            raise ValueError("Text is empty")
        return v


class PredictQueued(BaseModel):
    task_id: str
    status: str = "queued"


class PredictResult(BaseModel):
    task_id: Optional[str] = None
    status: str
    prediction: Optional[str] = None
    confidence: Optional[float] = None
    model_version: Optional[str] = None
    cached: bool = False
    processing_time_ms: Optional[float] = None


@router.post("/predict", response_model=PredictResult)
def predict(body: PredictRequest, user: str = Depends(get_current_user)):
    cached = get_cached(body.text)
    if cached:
        return PredictResult(status="completed", cached=True, **cached)

    if is_open():
        return JSONResponse(
            status_code=503,
            headers={"Retry-After": "10"},
            content={"detail": "Service temporarily unavailable — worker is down or queue is full."},
        )

    task_id = str(uuid.uuid4())

    db = SessionLocal()
    try:
        db.add(Prediction(request_id=task_id, input_text=body.text))
        db.commit()
    finally:
        db.close()

    celery_app.send_task("worker.tasks.run_inference", args=[task_id, body.text], task_id=task_id)
    return PredictQueued(task_id=task_id)


@router.get("/result/{task_id}", response_model=PredictResult)
def get_result(task_id: str, user: str = Depends(get_current_user)):
    task = AsyncResult(task_id, app=celery_app)

    if task.state == "PENDING":
        return PredictResult(task_id=task_id, status="pending")
    if task.state == "FAILURE":
        return PredictResult(task_id=task_id, status="failed")

    return PredictResult(task_id=task_id, status="completed", **task.result)
