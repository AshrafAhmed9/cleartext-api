import json


def test_request_queued_when_queue_is_short(client, mock_redis_client, mocker):
    mock_redis_client.llen.return_value = 0
    mocker.patch("api.predict.celery_app.send_task")
    mocker.patch("api.predict.SessionLocal")

    response = client.post("/predict", json={"text": "hello"})
    assert response.status_code == 200
    assert response.json()["status"] == "queued"


def test_request_rejected_when_queue_is_full(client, mock_redis_client):
    mock_redis_client.llen.return_value = 999  # well over the limit

    response = client.post("/predict", json={"text": "hello"})
    assert response.status_code == 503
    assert "Retry-After" in response.headers


def test_cache_hit_is_served_even_when_queue_is_full(client, mock_redis_client):
    cached = json.dumps({"prediction": "non-toxic", "confidence": 0.12, "model_version": "v1"})
    mock_redis_client.llen.return_value = 999
    mock_redis_client.get.return_value = cached

    response = client.post("/predict", json={"text": "hello"})
    assert response.status_code == 200
    assert response.json()["prediction"] == "non-toxic"
