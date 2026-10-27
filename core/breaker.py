"""Circuit breaker: stop accepting new work when the queue is backed up.

If the worker can't keep up, jobs pile up in the queue. Past a limit, the API
answers 503 + Retry-After instead of making the line even longer.
"""
import redis as redis_lib

from core.config import settings

_redis = redis_lib.from_url(settings.redis_url)

# "celery" is the name of Celery's default queue (a Redis list).
QUEUE_NAME = "celery"


def is_open() -> bool:
    """True if the queue is too long and new work should be rejected."""
    return _redis.llen(QUEUE_NAME) > settings.queue_depth_limit
