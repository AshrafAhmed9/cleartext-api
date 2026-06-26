def test_prometheus_endpoint(client):
    """The Prometheus exposition endpoint should return text metrics."""
    response = client.get("/metrics/prometheus")
    assert response.status_code == 200
    assert "text/plain" in response.headers["content-type"]


def test_json_metrics_requires_auth(client):
    """The JSON /metrics endpoint requires authentication."""
    response = client.get("/metrics")
    assert response.status_code in (401, 403)


def test_json_metrics_returns_dlq(client, auth_headers, mock_redis_client):
    mock_redis_client.llen.return_value = 3
    mock_redis_client.get.return_value = 0
    response = client.get("/metrics", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert "dlq" in data
    assert "latency" in data
    assert "p50_inference_ms" in data["latency"]
    assert "p99_inference_ms" in data["latency"]
