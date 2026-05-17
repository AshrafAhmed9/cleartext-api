from unittest.mock import patch, MagicMock


def test_run_inference_success():
    mock_prediction = {"prediction": "toxic", "confidence": 0.93}
    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.first.return_value = None

    with patch("worker.tasks.predict", return_value=mock_prediction), \
         patch("worker.tasks.SessionLocal", return_value=mock_db), \
         patch("worker.tasks.set_cached"):

        from worker.tasks import run_inference
        result = run_inference.apply(args=["test-task-id", "I hate you"]).get()

        assert result["prediction"] == "toxic"
        assert result["confidence"] == 0.93
        assert "processing_time_ms" in result


def test_run_inference_saves_to_db():
    mock_prediction = {"prediction": "non-toxic", "confidence": 0.99}
    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.first.return_value = None

    with patch("worker.tasks.predict", return_value=mock_prediction), \
         patch("worker.tasks.SessionLocal", return_value=mock_db), \
         patch("worker.tasks.set_cached") as mock_cache:

        from worker.tasks import run_inference
        run_inference.apply(args=["task-id-456", "Hello world"]).get()

        mock_db.add.assert_called_once()
        mock_db.commit.assert_called()
        mock_cache.assert_called_once()
