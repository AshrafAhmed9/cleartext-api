from unittest.mock import patch, MagicMock


def test_run_inference_success():
    mock_result = {"prediction": "toxic", "confidence": 0.93, "model_version": "toxic-bert-1"}
    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.first.return_value = None

    mock_batcher = MagicMock()
    mock_batcher.submit.return_value = mock_result

    with patch("worker.tasks.get_batcher", return_value=mock_batcher), \
         patch("worker.tasks.SessionLocal", return_value=mock_db), \
         patch("worker.tasks.set_cached"), \
         patch("worker.tasks.metrics"):

        from worker.tasks import run_inference
        result = run_inference("test-task-id", "I hate you")

        assert result["prediction"] == "toxic"
        assert result["confidence"] == 0.93
        assert "processing_time_ms" in result


def test_run_inference_saves_to_db():
    mock_result = {"prediction": "non-toxic", "confidence": 0.99, "model_version": "toxic-bert-1"}
    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.first.return_value = None

    mock_batcher = MagicMock()
    mock_batcher.submit.return_value = mock_result

    with patch("worker.tasks.get_batcher", return_value=mock_batcher), \
         patch("worker.tasks.SessionLocal", return_value=mock_db), \
         patch("worker.tasks.set_cached") as mock_cache, \
         patch("worker.tasks.metrics"):

        from worker.tasks import run_inference
        run_inference("task-id-456", "Hello world")

        mock_db.add.assert_called_once()
        mock_db.commit.assert_called()
        mock_cache.assert_called_once()
