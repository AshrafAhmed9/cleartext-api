"""Prometheus metrics shared by the API and worker processes.

Each process imports this module and registers its own instances against the
default registry. The API serves them at GET /metrics/prometheus; the worker
serves them via prometheus_client.start_http_server(worker_metrics_port).
"""
from prometheus_client import Counter, Gauge, Histogram

# --- Inference (worker process) ---
INFERENCE_LATENCY = Histogram(
    "inference_latency_seconds",
    "Model forward-pass latency per request (after batching)",
    buckets=(0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.0, 5.0),
)
END_TO_END_LATENCY = Histogram(
    "end_to_end_latency_seconds",
    "Batch wait + inference latency per request",
    buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.0, 5.0, 10.0),
)
BATCH_SIZE = Histogram(
    "inference_batch_size",
    "Requests merged into a single forward pass",
    buckets=(1, 2, 4, 8, 12, 16, 24, 32),
)
BATCH_WAIT = Histogram(
    "inference_batch_wait_seconds",
    "Time a batch spent collecting before flush",
    buckets=(0.001, 0.002, 0.004, 0.008, 0.016, 0.032, 0.064),
)

# --- Predictions / cache (API + worker) ---
PREDICTIONS_TOTAL = Counter("predictions_total", "Completed predictions", ["result"])
CACHE_HITS = Counter("cache_hits_total", "Cache hits")
CACHE_MISSES = Counter("cache_misses_total", "Cache misses")

# --- Queue / reliability ---
QUEUE_DEPTH = Gauge("queue_depth", "Pending tasks in the Celery queue")
DLQ_DEPTH = Gauge("dlq_depth", "Entries in the inference dead-letter queue")
WORKER_INFLIGHT = Gauge("worker_inflight_requests", "Requests currently being processed")
CIRCUIT_BREAKER_TRIPS = Counter("circuit_breaker_trips_total", "Requests rejected by the breaker")
