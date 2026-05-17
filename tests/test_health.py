def test_health_returns_ok(client, mock_redis):
    mock_redis.ping.return_value = True
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert "services" in data
    assert "redis" in data["services"]
    assert "database" in data["services"]
    assert "queue" in data["services"]

def test_health_redis_down(client, mock_redis):
    mock_redis.ping.side_effect = Exception("Connection refused")
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["services"]["redis"] == "error"
    assert response.json()["status"] == "degraded"
    mock_redis.ping.side_effect = None  # reset
