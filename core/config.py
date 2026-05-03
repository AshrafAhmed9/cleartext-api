from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    database_url: str
    redis_url: str
    jwt_secret: str
    jwt_algorithm: str = "HS256"
    rate_limit: str = "10/minute"
    cache_ttl: int = 3600
    youtube_api_key: str = ""
    groq_api_key: str = ""

    class Config:
        env_file = ".env"

settings = Settings()
