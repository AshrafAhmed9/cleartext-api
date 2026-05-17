from unittest.mock import patch, MagicMock


def test_metrics_has_required_fields(client, auth_headers, mock_redis):
    mock_redis.get.side_effect = lambda key: b"10" if "hits" in key else b"5"
    mock_redis.llen.return_value = 2

    with patch("api.routes.metrics.SessionLocal") as MockSession:
        mock_db = MagicMock()
        mock_db.query.return_value.scalar.return_value = 42
        mock_db.query.return_value.filter.return_value.scalar.return_value = 38
        mock_db.query.return_value.filter.return_value.filter.return_value.scalar.return_value = 2
        mock_db.query.return_value.order_by.return_value.all.return_value = [(100.0,), (200.0,), (300.0,)]
        MockSession.return_value = mock_db

        response = client.get("/metrics", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()

        assert "jobs" in data
        assert "cache" in data
        assert "queue" in data
        assert "latency" in data
        assert "total" in data["jobs"]
        assert "hit_rate" in data["cache"]
        assert "depth" in data["queue"]
        assert "avg_inference_ms" in data["latency"]
        assert "p95_inference_ms" in data["latency"]

    mock_redis.get.side_effect = None
    mock_redis.get.return_value = None


def test_metrics_hit_rate_is_float(client, auth_headers, mock_redis):
    mock_redis.get.side_effect = lambda key: b"8" if "hits" in key else b"2"

    with patch("api.routes.metrics.SessionLocal") as MockSession:
        mock_db = MagicMock()
        mock_db.query.return_value.scalar.return_value = 0
        mock_db.query.return_value.filter.return_value.scalar.return_value = 0
        mock_db.query.return_value.order_by.return_value.all.return_value = []
        MockSession.return_value = mock_db

        response = client.get("/metrics", headers=auth_headers)
        assert response.status_code == 200
        hit_rate = response.json()["cache"]["hit_rate"]
        assert isinstance(hit_rate, float)
        assert 0.0 <= hit_rate <= 1.0

    mock_redis.get.side_effect = None
    mock_redis.get.return_value = None
