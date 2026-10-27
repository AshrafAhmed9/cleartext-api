"""Redis cache for finished predictions.

The cache key includes the model version, so changing the model makes every
old entry unreachable. No manual flush, and no stale answers from an old model.
"""
import hashlib
import json
from typing import Optional

import redis

from core.config import settings

client = redis.from_url(settings.redis_url)


def make_key(text: str, model_version: Optional[str] = None) -> str:
    version = model_version or settings.ml_model_version
    # Lowercase and trim so "Hello " and "hello" share one cache entry.
    raw = "{0}:{1}".format(version, text.strip().lower())
    return "cache:" + hashlib.sha256(raw.encode()).hexdigest()


def get_cached(text: str):
    """Return the saved result for this text, or None if there isn't one."""
    value = client.get(make_key(text))
    return json.loads(value) if value else None


def set_cached(text: str, result: dict):
    """Save a result; Redis drops it automatically after cache_ttl seconds."""
    client.setex(make_key(text), settings.cache_ttl, json.dumps(result))
