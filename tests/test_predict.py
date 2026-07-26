import json
from unittest.mock import patch, MagicMock


def test_predict_cache_hit(client, auth_headers, mock_redis_client):
    cached = {"prediction": "non-toxic", "confidence": 0.99, "model_version": "toxic-bert-1"}
    mock_redis_client.get.return_value = json.dumps(cached).encode()

    response = client.post("/predict", json={"text": "hello world"}, headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "completed"
    assert data["cached"] is True
    assert data["prediction"] == "non-toxic"
    mock_redis_client.get.return_value = None


def test_predict_queues_task_on_cache_miss(client, auth_headers, mock_redis_client, mocker):
    mock_redis_client.get.return_value = None
    mock_redis_client.exists.return_value = True  # worker alive
    mock_redis_client.llen.return_value = 0  # queue not full
    mocker.patch("api.predict.celery_app.send_task")

    response = client.post("/predict", json={"text": "I hate you"}, headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "queued"
    assert "task_id" in data


def test_get_result_pending(client, auth_headers):
    with patch("api.predict.AsyncResult") as MockResult:
        mock_result = MagicMock()
        mock_result.state = "PENDING"
        MockResult.return_value = mock_result

        response = client.get("/result/fake-task-id", headers=auth_headers)
        assert response.status_code == 200
        assert response.json()["status"] == "pending"


def test_get_result_completed(client, auth_headers):
    with patch("api.predict.AsyncResult") as MockResult:
        mock_result = MagicMock()
        mock_result.state = "SUCCESS"
        mock_result.result = {
            "prediction": "toxic",
            "confidence": 0.93,
            "processing_time_ms": 312.0
        }
        MockResult.return_value = mock_result

        response = client.get("/result/fake-task-id", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "completed"
        assert data["prediction"] == "toxic"
        assert data["confidence"] == 0.93
