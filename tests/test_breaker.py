def test_circuit_breaker_closed_when_worker_alive(client, auth_headers, mock_redis_client, mocker):
    """When worker heartbeat exists and queue is low, requests go through."""
    mock_redis_client.exists.return_value = True
    mock_redis_client.llen.return_value = 0
    mock_redis_client.get.return_value = None  # cache miss
    mocker.patch("api.predict.celery_app.send_task")
    mocker.patch("api.predict.SessionLocal")

    response = client.post("/predict", json={"text": "hello"}, headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "queued"


def test_circuit_breaker_open_when_worker_down(client, auth_headers, mock_redis_client):
    """When worker heartbeat is missing, return 503."""
    mock_redis_client.exists.return_value = False  # no heartbeat
    mock_redis_client.get.return_value = None  # cache miss

    response = client.post("/predict", json={"text": "hello"}, headers=auth_headers)
    assert response.status_code == 503
    assert "Retry-After" in response.headers


def test_circuit_breaker_open_when_queue_full(client, auth_headers, mock_redis_client):
    """When queue exceeds limit, return 503."""
    mock_redis_client.exists.return_value = True  # worker alive
    mock_redis_client.llen.return_value = 999  # queue way over limit
    mock_redis_client.get.return_value = None  # cache miss

    response = client.post("/predict", json={"text": "hello"}, headers=auth_headers)
    assert response.status_code == 503


def test_cache_hit_bypasses_breaker(client, auth_headers, mock_redis_client):
    """Cache hits should be served even if the breaker is open."""
    import json
    cached = json.dumps({"prediction": "non-toxic", "confidence": 0.12, "model_version": "v1"})
    mock_redis_client.exists.return_value = False  # worker down
    mock_redis_client.get.return_value = cached  # but cache hit

    response = client.post("/predict", json={"text": "hello"}, headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["prediction"] == "non-toxic"
