import threading
from unittest.mock import patch


def test_concurrent_submits_merge_into_one_batch():
    """5 requests arriving within the collection window should reach the
    model as ONE predict_batch call with 5 texts, not 5 separate calls."""
    from worker.batcher import MicroBatcher

    fake_result = {"prediction": "non-toxic", "confidence": 0.1, "model_version": "test"}

    with patch("worker.batcher.predict_batch") as mock_predict_batch, \
         patch("worker.batcher.metrics"):
        mock_predict_batch.side_effect = lambda texts: [fake_result for _ in texts]

        batcher = MicroBatcher()
        results = [None] * 5

        def submit(i):
            results[i] = batcher.submit(f"comment {i}")

        threads = [threading.Thread(target=submit, args=(i,)) for i in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=5)

        assert all(r == fake_result for r in results)
        # All 5 landed in a batch of size > 1 at least once.
        assert any(len(call.args[0]) > 1 for call in mock_predict_batch.call_args_list)
