"""In-process micro-batcher.

Multiple Celery worker threads submit a single text each and block. A
background thread collects concurrent submissions for a few milliseconds and
runs them as ONE batched forward pass — real throughput at the cost of a tiny,
bounded queue wait per request. Safe here because the model is deterministic,
so a batched result is identical to the per-request result.
"""
import threading
import queue
import time

from core.config import settings
from core import metrics
from worker.ml_model import predict_batch


class _Job:
    __slots__ = ("text", "event", "result", "error")

    def __init__(self, text: str):
        self.text = text
        self.event = threading.Event()
        self.result = None
        self.error = None


class MicroBatcher:
    def __init__(self):
        self._q: "queue.Queue[_Job]" = queue.Queue()
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def submit(self, text: str, timeout: float = 30.0) -> dict:
        job = _Job(text)
        self._q.put(job)
        if not job.event.wait(timeout):
            raise TimeoutError("Inference batch timed out")
        if job.error:
            raise job.error
        return job.result

    def _collect(self):
        # Block for the first job, then drain up to batch_max_size within the window.
        first = self._q.get()
        start = time.monotonic()
        batch = [first]
        deadline = start + settings.batch_max_wait_ms / 1000.0
        while len(batch) < settings.batch_max_size:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            try:
                batch.append(self._q.get(timeout=remaining))
            except queue.Empty:
                break
        return batch, time.monotonic() - start

    def _loop(self):
        while True:
            batch, collect_seconds = self._collect()
            metrics.BATCH_SIZE.observe(len(batch))
            metrics.BATCH_WAIT.observe(collect_seconds)
            t0 = time.monotonic()
            try:
                results = predict_batch([j.text for j in batch])
                for job, result in zip(batch, results):
                    job.result = result
            except Exception as exc:  # propagate to every waiter in the batch
                for job in batch:
                    job.error = exc
            finally:
                forward_seconds = time.monotonic() - t0
                for job in batch:
                    metrics.INFERENCE_LATENCY.observe(forward_seconds)
                    job.event.set()


_batcher = None
_lock = threading.Lock()


def get_batcher() -> MicroBatcher:
    global _batcher
    if _batcher is None:
        with _lock:
            if _batcher is None:
                _batcher = MicroBatcher()
    return _batcher
