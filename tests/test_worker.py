from unittest.mock import patch, MagicMock

from db import Prediction


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


def test_run_inference_persists_to_real_db(db_session):
    """Same task, but SessionLocal is the real Postgres fixture — proves the
    row genuinely lands in the predictions table, not just a mock call."""
    mock_result = {"prediction": "non-toxic", "confidence": 0.99, "model_version": "toxic-bert-1"}
    mock_batcher = MagicMock()
    mock_batcher.submit.return_value = mock_result

    with patch("worker.tasks.get_batcher", return_value=mock_batcher), \
         patch("worker.tasks.SessionLocal", return_value=db_session), \
         patch("worker.tasks.set_cached"), \
         patch("worker.tasks.metrics"):

        from worker.tasks import run_inference
        run_inference("real-db-task-id", "Hello world")

    row = db_session.query(Prediction).filter(Prediction.request_id == "real-db-task-id").first()
    assert row is not None
    assert row.prediction == "non-toxic"
    assert row.status == "completed"

    db_session.delete(row)
    db_session.commit()
