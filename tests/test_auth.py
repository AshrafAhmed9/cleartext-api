def test_login_success(client, mock_redis):
    mock_redis.get.return_value = None
    response = client.post("/token", data={"username": "admin", "password": "secret"})
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"

def test_login_wrong_password(client, mock_redis):
    mock_redis.get.return_value = None
    response = client.post("/token", data={"username": "admin", "password": "wrong"})
    assert response.status_code == 401
    assert response.json()["detail"] == "Wrong credentials"

def test_brute_force_lockout(client, mock_redis):
    mock_redis.get.return_value = b"6"
    response = client.post("/token", data={"username": "admin", "password": "wrong"})
    assert response.status_code == 429
    mock_redis.get.return_value = None  # reset

def test_jwt_required_for_predict(client):
    response = client.post("/predict", json={"text": "hello"})
    assert response.status_code == 401
