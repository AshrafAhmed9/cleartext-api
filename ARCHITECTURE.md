# ClearText v2 — Architecture Documentation

> **Branch note:** This is `v2`. The original version lives on `main` and is unchanged.

## What It Does

A production-grade ML inference platform that:
1. Detects toxic comments via REST API (single text analysis) with request batching
2. Analyzes YouTube video comment sections and generates AI-powered insights
3. Provides full observability via Prometheus metrics and Grafana dashboards

---

## System Architecture (v2)

```
Client
  │
  ▼
┌─────────────────────────────────────────────────┐
│              FastAPI (API Layer)                  │
│  JWT auth │ Rate limiting │ Security headers      │
│  Brute force protection │ XSS sanitization       │
├─────────────────────────────────────────────────┤
│  POST /predict         → single comment (+ webhook) │
│  GET  /result/{id}     → fetch result               │
│  POST /analyze/youtube → video analysis              │
│  GET  /health          → system status               │
│  GET  /metrics         → JSON metrics                │
│  GET  /metrics/prometheus → Prometheus exposition     │
│  GET  /dlq             → dead-letter queue            │
│  POST /dlq/{id}/replay → re-enqueue failed job       │
└──────────┬──────────────────────────────────────┘
           │
     ┌─────▼──────────────┐
     │  Circuit Breaker    │──── OPEN ──▶ 503 + Retry-After
     │  (heartbeat +       │
     │   queue depth)      │
     └─────┬──────────────┘
           │ CLOSED
     ┌─────▼──────┐     ┌──────────────────────────────┐
     │   Redis     │────▶│  Celery Worker (thread pool)  │
     │ Queue+Cache │     │  └── Micro-Batcher            │
     │ (LRU 256mb) │     │      └── classifier([batch])  │
     └─────────────┘     └──────┬───────────────────────┘
                                │
                    ┌───────────▼──────────────────┐
                    │      PostgreSQL               │
                    │  stores predictions +          │
                    │  model_version traceability    │
                    └──────────────────────────────┘
                                │
                    On terminal failure (3 retries exhausted):
                    └──▶ Dead-Letter Queue (Redis list)

Observability:
  Worker :9100 ──▶ Prometheus ──▶ Grafana Dashboard
  API /metrics/prometheus ──▶ Prometheus ──▶ Grafana Dashboard
```

---

## Request Batching (v2)

The highest-ROI optimization in this system. Multiple Celery worker threads submit texts to a shared micro-batcher, which:

1. Collects up to 16 texts (or waits up to 8ms, whichever comes first)
2. Runs ONE `classifier([t1, t2, ...])` forward pass for the entire batch
3. Fans results back to each waiting thread

**Why it works:** `transformers` pipelines natively accept lists. A single batched call shares GPU/CPU overhead across all items — matrix operations are parallelized, model weights are loaded once.

**Why it's safe:** toxic-bert is deterministic (no sampling/temperature). `classifier(["hello"])` and the "hello" slice from `classifier(["hello", "world"])` produce identical results.

**Latency/throughput tradeoff:** Each individual request pays up to 8ms of queue wait so the system gains a multi-x throughput increase at concurrency. At low concurrency, batch size = 1 and there's no penalty.

---

## Model-Versioned Cache (v2)

**Problem:** v1 cached on `SHA256(text)` alone. If you swap the model, the old cache serves stale answers from the previous model — silently wrong.

**Fix:** Cache key = `SHA256(model_version + ":" + text.lower().strip())`. A model version bump instantly partitions the namespace. Old keys age out via TTL.

**When is returning a cached inference safe?** Only when:
1. The model is deterministic (no sampling) — same input always produces same output
2. The cache key captures everything that affects the output — both the input text AND the model version

toxic-bert satisfies both conditions.

---

## Dead-Letter Queue (v2)

Failed jobs (after 3 retries with exponential backoff) are:
1. Marked `status=failed` in PostgreSQL (existing behavior)
2. Pushed to `dlq:inference` Redis list with full context: task_id, text, error, traceback, model_version, timestamp

Operators can:
- `GET /dlq` — list all dead-lettered entries
- `POST /dlq/{task_id}/replay` — re-enqueue a specific job

DLQ depth is exposed in `/health`, `/metrics`, and Prometheus (`dlq_depth` gauge).

---

## Circuit Breaker (v2)

**Problem:** Without a breaker, the API silently accepts requests even when no worker is consuming them. The queue grows unbounded, and every queued request eventually times out.

**Fix:** Before enqueueing on a cache miss, the API checks two signals:
1. **Worker heartbeat** — worker writes a Redis key with short TTL every 5 seconds. Missing = worker is down.
2. **Queue depth** — if backlog exceeds `QUEUE_DEPTH_LIMIT` (default 100), the worker can't keep up.

If either fires: return **503 Service Unavailable** with a `Retry-After: 10` header. The client knows to back off.

Cache hits bypass the breaker entirely — they don't need the worker.

---

## Cache Eviction Strategy (v2)

Two complementary mechanisms:
- **Per-key TTL** (1 hour default) — ensures staleness is bounded
- **Redis `maxmemory 256mb` + `allkeys-lru`** — ensures memory is bounded

Why both: TTL prevents serving stale results. LRU prevents the cache from consuming unbounded memory. Without LRU, a high-traffic deployment could exhaust Redis memory even with TTL (keys accumulate faster than they expire).

---

## Completion Webhook (v2)

`POST /predict` accepts an optional `callback_url`. On completion (or failure), the worker POSTs the result to that URL:

```json
{"task_id": "...", "status": "completed", "prediction": "toxic", "confidence": 0.93, "model_version": "toxic-bert-1"}
```

Webhook delivery failures are pushed to `dlq:webhook` (same pattern as inference DLQ). Polling remains the default — the webhook is opt-in.

---

## Security Features

| Feature | Implementation | Purpose |
|---------|---------------|---------|
| JWT Authentication | python-jose HS256 | Stateless auth, 24hr expiry |
| Rate Limiting | slowapi, 10 req/min per IP | Prevents API abuse |
| Brute Force Protection | Redis counter, lockout after 5 fails | Prevents credential stuffing |
| Input Sanitization | Regex strip HTML/scripts | Prevents XSS/injection |
| Security Headers | Custom middleware | OWASP hardening |
| Audit Logging | JSON structured logs | Compliance + traceability |
| Request ID Tracking | UUID per request, X-Request-ID header | End-to-end traceability |
| Callback Validation | http/https scheme check | Prevents SSRF via webhook |

---

## Database Schema

Table: `predictions`

| Column | Type | Purpose |
|--------|------|---------|
| id | UUID | Unique row identifier |
| request_id | String (indexed) | Maps to Celery task ID |
| input_text | Text | The submitted comment |
| prediction | String | "toxic" or "non-toxic" |
| confidence | Float | Model confidence (0-1) |
| model_version | String | Model that produced this prediction |
| processing_time_ms | Float | Batch wait + inference latency |
| status | String | queued / processing / completed / failed |
| queued_at | DateTime | When the API enqueued the task |
| started_at | DateTime | When the worker picked it up |
| created_at | DateTime | Row creation timestamp |

Schema managed by Alembic migrations (`migrations/versions/`).

---

## ML Model

Model: `unitary/toxic-bert` (HuggingFace)
- BERT fine-tuned on Jigsaw Toxic Comments dataset
- Multi-label: toxic, severe_toxic, obscene, threat, insult, identity_hate
- Aggregation: max score across all labels
- Threshold: score > 0.5 = "toxic"
- Deterministic: no sampling, no temperature — identical input always produces identical output
- Local GPU: ~140ms | Docker CPU: ~1600ms
- Batched: `classifier([t1, t2, ...])` processes N texts in one forward pass

---

## YouTube Analysis Pipeline

1. Extract video ID from URL
2. Fetch up to 100 comments via YouTube Data API v3
3. Run each comment through toxic-bert
4. Aggregate: toxic count, non-toxic count, toxicity rate, community rating
5. Send sample comments to Groq (llama-3.3-70b-versatile) for AI insights
6. Return structured report with summary, themes, improvements, sentiment

---

## Load Test Results

| Users | Avg Latency | p95 Latency | RPS | Failures |
|-------|-------------|-------------|-----|----------|
| 100   | 52ms        | 85ms        | 44  | 0%       |
| 500   | 106ms       | 240ms       | 231 | 0%       |

Tested with Locust and k6. Bottleneck: single Celery worker. Fix: horizontal scaling (add workers) or GPU for faster inference.

---

## Failure Handling

| Failure | Handling |
|---------|----------|
| Worker crash | Celery retries 3x, exponential backoff (2s, 4s, 8s) |
| Retries exhausted | Job marked failed in DB + pushed to Dead-Letter Queue |
| Worker down | Circuit breaker returns 503 + Retry-After |
| Queue overloaded | Circuit breaker returns 503 + Retry-After |
| Redis down | API returns 500; /health reports degraded |
| Invalid JWT | 401 immediately |
| Rate limit hit | 429 Too Many Requests |
| 5 failed logins | IP locked out for 5 minutes |
| XSS in input | Stripped before model sees it |
| Text > 5000 chars | 422 Validation Error |
| Webhook delivery fail | Pushed to dlq:webhook |

---

## Retry Strategy

```
max_retries = 3
backoff:     2s → 4s → 8s (exponential)
exhausted:   status = "failed" + pushed to dlq:inference
```

---

## Scaling Strategy

- **Horizontal:** Add Celery workers — Redis distributes tasks automatically. Each worker runs its own micro-batcher.
- **Vertical:** GPU worker reduces inference from 1600ms to 140ms
- **Batching:** Micro-batcher amortizes per-request overhead at concurrency
- **Database:** Read replicas for GET /result, PgBouncer for connection pooling
- **Cache:** LRU eviction + TTL ensures bounded memory under any load

---

## Design Decisions / Tradeoffs

| Decision | Why | Alternative considered |
|----------|-----|----------------------|
| Celery over Kafka | Simpler ops, sufficient for current scale | Kafka for >10K msg/sec |
| Redis for queue + cache | Single infra, already deployed | RabbitMQ for complex routing |
| Async processing | Prevents API blocking during 300-1600ms inference | Sync only viable for <50ms models |
| BERT (unitary/toxic-bert) | Open-source, no API cost, runs locally | GPT API for higher accuracy |
| FastAPI over Flask | Native async support, auto OpenAPI docs | Flask for simpler single-threaded apps |
| Thread pool (not solo) | Enables in-process batching across concurrent tasks | Solo pool = no batching possible |
| Micro-batch (not dedicated service) | Self-contained, no network hop, no extra container | Triton/TorchServe for multi-model serving |
| 8ms batch window | Bounded latency penalty; 16-item cap prevents memory spikes | Larger window = more throughput, more latency |
| Model version in cache key | Prevents stale answers after model swap | Flush entire cache on deploy (data loss, thundering herd) |
| Dead-letter queue (Redis list) | Simple, inspectable, replayable; matches existing Redis infra | PostgreSQL DLQ table (more durable, more complex) |
| Circuit breaker (heartbeat + depth) | Fails fast and honestly; client gets 503 + Retry-After | Queue-and-hope (silent failure, unbounded backlog) |
| LRU + TTL eviction | TTL for staleness, LRU for capacity — complementary | TTL-only (unbounded memory) or LRU-only (stale results) |
| Alembic over create_all | Reviewable diffs, rollback support, production standard | create_all (no history, no rollback, no column adds) |
| Polling + optional webhook | Backwards compatible; webhook is opt-in for advanced clients | WebSocket (connection overhead, stateful) |
| Prometheus + Grafana | Industry standard, free, screenshots for portfolio | Custom dashboard (non-standard, more work) |

---

## Current Limitations

- Single Celery worker — horizontal scaling not configured in compose
- Redis is a single point of failure (no Sentinel/Cluster)
- Auth uses hardcoded credentials — no user management system
- YouTube analysis is synchronous — 100 comments x inference time blocks the worker
- Webhook delivery is best-effort (no retry, failures go to DLQ)
- No GPU support in Docker by default (CPU inference only)
