import sys
from unittest.mock import MagicMock

# Mock Redis before anything imports it
mock_redis = MagicMock()
mock_redis.get.return_value = None
mock_redis.llen.return_value = 0
mock_redis.lrange.return_value = []
mock_redis.exists.return_value = True
mock_redis.incr.return_value = 1
mock_redis_module = MagicMock()
mock_redis_module.from_url.return_value = mock_redis
sys.modules.setdefault("redis", mock_redis_module)

# Mock prometheus_client to avoid registry collisions in tests
mock_prom = MagicMock()
for cls_name in ["Counter", "Gauge", "Histogram", "Summary"]:
    mock_cls = MagicMock()
    mock_instance = MagicMock()
    mock_cls.return_value = mock_instance
    mock_instance.labels.return_value = mock_instance
    setattr(mock_prom, cls_name, mock_cls)
mock_prom.generate_latest.return_value = b"# HELP fake_metric\n# TYPE fake_metric gauge\nfake_metric 1\n"
mock_prom.CONTENT_TYPE_LATEST = "text/plain; version=0.0.4; charset=utf-8"
sys.modules.setdefault("prometheus_client", mock_prom)

import pytest
from fastapi.testclient import TestClient
from api.main import app
from api.auth import create_token

@pytest.fixture
def client():
    return TestClient(app)

@pytest.fixture
def auth_headers():
    token = create_token("admin")
    return {"Authorization": f"Bearer {token}"}

@pytest.fixture
def mock_redis_client():
    mock_redis.reset_mock()
    mock_redis.get.return_value = None
    mock_redis.llen.return_value = 0
    mock_redis.lrange.return_value = []
    mock_redis.exists.return_value = True
    mock_redis.incr.return_value = 1
    return mock_redis
