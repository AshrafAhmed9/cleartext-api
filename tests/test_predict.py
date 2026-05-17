import json
from unittest.mock import patch, MagicMock


def test_predict_cache_hit(client, auth_headers, mock_redis):
    cached = {"prediction": "non-toxic", "confidence": 0.99}
    mock_redis.get.return_value = json.dumps(cached).encode()

    response = client.post("/predict", json={"text": "hello world"}, headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "completed"
    assert data["cached"] is True
    assert data["prediction"] == "non-toxic"
    mock_redis.get.return_value = None


def test_predict_queues_task_on_cache_miss(client, auth_headers, mock_redis):
    mock_redis.get.return_value = None

    with patch("api.routes.predict.celery_app.send_task") as mock_send:
        mock_task = MagicMock()
        mock_task.id = "test-task-123"
        mock_send.return_value = mock_task

        response = client.post("/predict", json={"text": "I hate you"}, headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "queued"
        assert "task_id" in data
        mock_send.assert_called_once()


def test_get_result_pending(client, auth_headers):
    with patch("api.routes.predict.AsyncResult") as MockResult:
        mock_result = MagicMock()
        mock_result.state = "PENDING"
        MockResult.return_value = mock_result

        response = client.get("/result/fake-task-id", headers=auth_headers)
        assert response.status_code == 200
        assert response.json()["status"] == "pending"


def test_get_result_completed(client, auth_headers):
    with patch("api.routes.predict.AsyncResult") as MockResult:
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
