import json


def test_dlq_list_empty(client, auth_headers, mock_redis_client):
    mock_redis_client.lrange.return_value = []
    response = client.get("/dlq", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["depth"] == 0
    assert data["entries"] == []


def test_dlq_list_with_entries(client, auth_headers, mock_redis_client):
    entry = json.dumps({
        "task_id": "abc-123",
        "text": "test input",
        "error": "model exploded",
        "traceback": "...",
        "model_version": "v1",
        "callback_url": None,
        "failed_at": "2026-06-26T12:00:00",
    })
    mock_redis_client.lrange.return_value = [entry]
    response = client.get("/dlq", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["depth"] == 1
    assert data["entries"][0]["task_id"] == "abc-123"


def test_dlq_replay_not_found(client, auth_headers, mock_redis_client):
    mock_redis_client.lrange.return_value = []
    response = client.post("/dlq/nonexistent/replay", headers=auth_headers)
    assert response.status_code == 404


def test_dlq_replay_success(client, auth_headers, mock_redis_client, mocker):
    entry = json.dumps({
        "task_id": "abc-123",
        "text": "test input",
        "error": "boom",
        "model_version": "v1",
        "callback_url": None,
        "failed_at": "2026-06-26T12:00:00",
    })
    mock_redis_client.lrange.return_value = [entry]
    mocker.patch("api.routes.dlq.celery_app.send_task")

    response = client.post("/dlq/abc-123/replay", headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["status"] == "replayed"
