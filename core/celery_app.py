"""The Celery app. The API uses it to send jobs, the worker uses it to receive them."""
from celery import Celery

from core.config import settings

celery_app = Celery(
    "cleartext",
    broker=settings.redis_url,    # where queued jobs wait
    backend=settings.redis_url,   # where finished results are stored
    include=["worker.tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    result_expires=3600,  # forget results after an hour
    # Run several jobs at once in one process so the micro-batcher can group them.
    worker_concurrency=settings.worker_concurrency,
)
