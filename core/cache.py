"""Redis cache keyed on (model_version, text) — swap models without serving stale answers."""
import hashlib
import json
from typing import Optional
import redis
from core.config import settings
from core import metrics

client = redis.from_url(settings.redis_url)


def make_key(text: str, model_version: Optional[str] = None) -> str:
    version = model_version or settings.ml_model_version
    raw = "{0}:{1}".format(version, text.strip().lower())
    return "cache:" + hashlib.sha256(raw.encode()).hexdigest()


def get_cached(text: str):
    value = client.get(make_key(text))
    if value:
        client.incr("metrics:cache_hits")
        metrics.CACHE_HITS.inc()
        return json.loads(value)
    client.incr("metrics:cache_misses")
    metrics.CACHE_MISSES.inc()
    return None


def set_cached(text: str, result: dict):
    client.setex(make_key(text), settings.cache_ttl, json.dumps(result))
