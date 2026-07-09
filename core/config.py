from pydantic_settings import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    database_url: str
    redis_url: str
    jwt_secret: str
    jwt_algorithm: str = "HS256"
    rate_limit: str = "10/minute"
    cache_ttl: int = 3600
    youtube_api_key: str = ""
    groq_api_key: str = ""
    cors_origins: str = "http://localhost:5173"

    # --- Model / cache versioning (v2) ---
    ml_model_name: str = "unitary/toxic-bert"
    ml_model_version: str = "toxic-bert-1"

    # --- Micro-batching (v2) ---
    batch_max_size: int = 16
    batch_max_wait_ms: int = 8
    worker_concurrency: int = 8

    # --- Circuit breaker (v2) ---
    queue_depth_limit: int = 100
    worker_heartbeat_ttl: int = 15

    # --- Worker metrics server (v2) ---
    worker_metrics_port: int = 9100

    class Config:
        env_file = ".env"

settings = Settings()
