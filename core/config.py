"""All tunable values in one place, loaded from environment variables / .env."""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str
    redis_url: str
    jwt_secret: str
    jwt_algorithm: str = "HS256"
    cache_ttl: int = 3600
    youtube_api_key: str = ""
    groq_api_key: str = ""
    cors_origins: str = "http://localhost:5173"

    # Which model is serving predictions, and its version tag for cache keys.
    ml_model_name: str = "unitary/toxic-bert"
    ml_model_version: str = "toxic-bert-1"

    # Micro-batcher: merge up to this many requests into one forward pass,
    # waiting at most this long to fill the batch.
    batch_max_size: int = 16
    batch_max_wait_ms: int = 8
    worker_concurrency: int = 8

    # Circuit breaker: reject new work above this queue depth, or if the
    # worker hasn't sent a heartbeat within this many seconds.
    queue_depth_limit: int = 100
    worker_heartbeat_ttl: int = 15

    worker_metrics_port: int = 9100

    model_config = SettingsConfigDict(env_file=".env")


settings = Settings()
