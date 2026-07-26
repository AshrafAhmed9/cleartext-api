"""Worker-only startup hooks: Prometheus metrics server + liveness heartbeat.

Imported by worker.tasks, which only loads inside the Celery worker — so the
model, metrics server, and heartbeat never start in the API process.
"""
import threading
import time

from celery.signals import worker_ready
from prometheus_client import start_http_server
import redis as redis_lib

from core.config import settings, HEARTBEAT_KEY

_redis = redis_lib.from_url(settings.redis_url)


def _heartbeat_loop():
    while True:
        try:
            _redis.set(HEARTBEAT_KEY, int(time.time()), ex=settings.worker_heartbeat_ttl)
        except Exception:
            pass
        time.sleep(max(1, settings.worker_heartbeat_ttl // 3))


@worker_ready.connect
def on_worker_ready(**kwargs):
    start_http_server(settings.worker_metrics_port)   # worker-side metrics
    from worker.batcher import get_batcher
    get_batcher()                                     # warm model + batch thread
    threading.Thread(target=_heartbeat_loop, daemon=True).start()
