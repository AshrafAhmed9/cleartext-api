from celery import Celery
from core.config import settings

celery_app = Celery(
    "flagship",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["worker.tasks"],       # ← add this line
)

celery_app.conf.update(
    task_serializer="json",
    result_expires=3600,
)
