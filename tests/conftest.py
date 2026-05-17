import os
import pytest
from unittest.mock import MagicMock, patch

# Set env vars BEFORE any app imports
os.environ["DATABASE_URL"] = "postgresql://postgres:postgres@localhost/flagship"
os.environ["REDIS_URL"] = "redis://localhost:6379/0"
os.environ["JWT_SECRET"] = "test-secret-key-for-testing-only"
os.environ["JWT_ALGORITHM"] = "HS256"
os.environ["RATE_LIMIT"] = "1000/minute"
os.environ["CACHE_TTL"] = "3600"
os.environ["YOUTUBE_API_KEY"] = "fake-key"
os.environ["GROQ_API_KEY"] = "fake-key"

# Mock Redis before any app code imports it
_mock_redis = MagicMock()
_mock_redis.get.return_value = None
_mock_redis.ping.return_value = True
_mock_redis.incr.return_value = 1
_mock_redis.expire.return_value = True
_mock_redis.delete.return_value = True
_mock_redis.setex.return_value = True
_mock_redis.llen.return_value = 2

import redis as _redis_lib
_redis_lib.from_url = lambda *args, **kwargs: _mock_redis


@pytest.fixture(scope="session")
def mock_redis():
    _mock_redis.get.return_value = None
    return _mock_redis


@pytest.fixture(scope="session")
def client():
    with patch("db.database.init_db"):
        from fastapi.testclient import TestClient
        from api.main import app
        return TestClient(app)


@pytest.fixture(scope="session")
def auth_headers(client):
    _mock_redis.get.return_value = None
    response = client.post("/token", data={"username": "admin", "password": "secret"})
    assert response.status_code == 200, f"Login failed: {response.text}"
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}
