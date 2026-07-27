def test_health_returns_ok(client, mock_redis_client):
    mock_redis_client.ping.return_value = True
    mock_redis_client.exists.return_value = True  # worker heartbeat
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert "services" in data
    assert "redis" in data["services"]
    assert "database" in data["services"]
    assert "queue" in data["services"]
    assert "dlq" in data["services"]
    assert "worker" in data["services"]

def test_health_redis_down(client, mock_redis_client):
    """A real outage fails EVERY Redis call, not just ping — /health still has
    to answer, since reporting the outage is the whole point of the endpoint."""
    outage = Exception("Connection refused")
    mock_redis_client.ping.side_effect = outage
    mock_redis_client.llen.side_effect = outage
    mock_redis_client.exists.side_effect = outage

    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "degraded"
    assert data["services"]["redis"] == "error"
    assert data["services"]["queue"]["depth"] == -1
    assert data["services"]["worker"]["alive"] is False

    mock_redis_client.ping.side_effect = None
    mock_redis_client.llen.side_effect = None
    mock_redis_client.exists.side_effect = None
