"""Micro-batcher: groups requests that arrive close together into one model call.

Each Celery thread hands over one text and waits. A background thread collects
texts for a few milliseconds, runs them all through the model together, and
wakes each waiting thread with its own result. One call for 16 texts costs
barely more than one call for 1 text, so this raises throughput a lot.
It's safe because the model gives the same answer for a text either way.
"""
import queue
import threading
import time

from core.config import settings
from worker.model import predict_batch


class _Job:
    """One waiting request: its text, and where its result or error is delivered."""

    def __init__(self, text: str):
        self.text = text
        self.done = threading.Event()  # set once result or error is filled in
        self.result = None
        self.error = None


class MicroBatcher:
    def __init__(self):
        self._queue = queue.Queue()
        threading.Thread(target=self._run, daemon=True).start()

    def submit(self, text: str, timeout: float = 30.0) -> dict:
        """Add a text and block until the batch it joined has finished."""
        job = _Job(text)
        self._queue.put(job)
        if not job.done.wait(timeout):
            raise TimeoutError("Inference batch timed out")
        if job.error:
            raise job.error
        return job.result

    def _collect_batch(self):
        # Wait for the first job, then keep adding jobs until the batch is
        # full or the wait window runs out.
        batch = [self._queue.get()]
        deadline = time.monotonic() + settings.batch_max_wait_ms / 1000
        while len(batch) < settings.batch_max_size:
            time_left = deadline - time.monotonic()
            if time_left <= 0:
                break
            try:
                batch.append(self._queue.get(timeout=time_left))
            except queue.Empty:
                break
        return batch

    def _run(self):
        # Background loop: collect a batch, run the model once, hand back results.
        while True:
            batch = self._collect_batch()
            try:
                results = predict_batch([job.text for job in batch])
                for job, result in zip(batch, results):
                    job.result = result
            except Exception as exc:
                # If the model call fails, every request in the batch gets the error.
                for job in batch:
                    job.error = exc
            finally:
                for job in batch:
                    job.done.set()


_batcher = None
_lock = threading.Lock()


def get_batcher() -> MicroBatcher:
    """Return the one shared batcher, creating it on first use."""
    global _batcher
    with _lock:
        if _batcher is None:
            _batcher = MicroBatcher()
    return _batcher
