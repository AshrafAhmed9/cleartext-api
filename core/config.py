"""All settings in one place. Values come from environment variables or the .env file."""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str
    redis_url: str
    cache_ttl: int = 3600  # seconds a cached result lives

    # Which model serves predictions. The version is part of every cache key.
    ml_model_name: str = "unitary/toxic-bert"
    ml_model_version: str = "toxic-bert-1"

    # Micro-batcher: group up to batch_max_size requests into one model call,
    # waiting at most batch_max_wait_ms for the group to fill up.
    batch_max_size: int = 16
    batch_max_wait_ms: int = 8
    worker_concurrency: int = 8

    # Circuit breaker: reject new work once the queue is longer than this.
    queue_depth_limit: int = 100

    # Ignore unrelated variables that may be in the .env file.
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()

# Redis list where jobs that failed all their retries are kept.
DLQ_KEY = "dlq:inference"
