"""Circuit breaker: reject new work when the worker is down or overloaded.

Checks two signals:
  1. Worker heartbeat key missing → worker is down.
  2. Queue depth exceeds limit → worker can't keep up.

When either fires, the API returns 503 + Retry-After instead of silently
queueing work that can't be served.
"""
import redis as redis_lib
from core.config import settings, DLQ_KEY, HEARTBEAT_KEY
from core import metrics

_redis = redis_lib.from_url(settings.redis_url)


def is_open() -> bool:
    """Return True if the circuit is OPEN (unhealthy — reject work)."""
    metrics.DLQ_DEPTH.set(int(_redis.llen(DLQ_KEY) or 0))

    # Check 1: worker heartbeat
    if not _redis.exists(HEARTBEAT_KEY):
        metrics.CIRCUIT_BREAKER_TRIPS.inc()
        return True

    # Check 2: queue backlog
    queue_depth = int(_redis.llen("celery") or 0)
    metrics.QUEUE_DEPTH.set(queue_depth)
    if queue_depth > settings.queue_depth_limit:
        metrics.CIRCUIT_BREAKER_TRIPS.inc()
        return True

    return False
