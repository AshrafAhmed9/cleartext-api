import sys
from unittest.mock import MagicMock

# Replace the redis library with a fake before anything imports it, so tests
# never need a running Redis. Every module's redis client is this same fake.
mock_redis = MagicMock()
mock_redis_module = MagicMock()
mock_redis_module.from_url.return_value = mock_redis
sys.modules.setdefault("redis", mock_redis_module)

import pytest
from fastapi.testclient import TestClient
from api.main import app


def _reset_mock_redis():
    mock_redis.reset_mock()
    mock_redis.get.return_value = None      # cache miss
    mock_redis.llen.return_value = 0        # empty queue
    mock_redis.lrange.return_value = []     # empty DLQ


_reset_mock_redis()


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def mock_redis_client():
    _reset_mock_redis()
    return mock_redis


@pytest.fixture
def db_session():
    """A real Postgres session (Redis stays mocked). Rolls back anything left uncommitted."""
    from db import SessionLocal, init_db

    init_db()
    session = SessionLocal()
    yield session
    session.rollback()
    session.close()
