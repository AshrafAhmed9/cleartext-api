from celery import Celery
from core.config import settings

celery_app = Celery(
    "flagship",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["worker.tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    result_expires=3600,
    # Thread pool so multiple tasks run concurrently in one process and can be
    # merged by the in-process micro-batcher.
    worker_concurrency=settings.worker_concurrency,
)
