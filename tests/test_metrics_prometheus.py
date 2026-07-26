def test_prometheus_endpoint(client):
    """The Prometheus exposition endpoint should return text metrics."""
    response = client.get("/metrics/prometheus")
    assert response.status_code == 200
    assert "text/plain" in response.headers["content-type"]


def test_json_metrics_requires_auth(client):
    """The JSON /metrics endpoint requires authentication."""
    response = client.get("/metrics")
    assert response.status_code in (401, 403)
