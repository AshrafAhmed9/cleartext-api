"""Endpoints for submitting a comment and checking its result.

POST /predict never runs the model itself. It does one of three things:
  1. The answer is already cached -> return it right away.
  2. The queue is too long -> reject with 503.
  3. Otherwise -> put the job on the queue and return a task_id.
GET /result/{task_id} is how the caller picks up the answer later.
"""
import uuid
from typing import Optional

from celery.result import AsyncResult
from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, field_validator

from core.breaker import is_open
from core.cache import get_cached
from core.celery_app import celery_app
from db import SessionLocal, Prediction

router = APIRouter()


class PredictRequest(BaseModel):
    text: str = Field(min_length=1, max_length=5000)

    @field_validator("text")
    @classmethod
    def clean_text(cls, v):
        # Collapse extra spaces and newlines, and refuse text that is only whitespace.
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
def predict(body: PredictRequest):
    # 1. Cache hit: answer immediately, no queue needed.
    cached = get_cached(body.text)
    if cached:
        return PredictResult(status="completed", cached=True, **cached)

    # 2. Queue too long: tell the caller to come back later.
    if is_open():
        return JSONResponse(
            status_code=503,
            headers={"Retry-After": "10"},
            content={"detail": "Queue is full, try again shortly."},
        )

    # 3. Record the job in Postgres, then hand it to the worker.
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
def get_result(task_id: str):
    task = AsyncResult(task_id, app=celery_app)

    if task.state == "PENDING":
        return PredictResult(task_id=task_id, status="pending")
    if task.state == "FAILURE":
        return PredictResult(task_id=task_id, status="failed")

    return PredictResult(task_id=task_id, status="completed", **task.result)
