import hashlib
import json
import redis
from core.config import settings

client = redis.from_url(settings.redis_url)

def make_key(text: str) -> str:
    return "cache:" + hashlib.sha256(text.strip().lower().encode()).hexdigest()

def get_cached(text: str):
    value = client.get(make_key(text))
    if value:
        client.incr("metrics:cache_hits")   # track hits
        return json.loads(value)
    client.incr("metrics:cache_misses")     # track misses
    return None

def set_cached(text: str, result: dict):
    client.setex(make_key(text), settings.cache_ttl, json.dumps(result))
