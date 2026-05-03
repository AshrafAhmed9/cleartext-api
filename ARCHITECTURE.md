# ClearText API — Architecture Documentation

## What It Does
Accepts a text comment via REST API and returns whether it is toxic or non-toxic,
along with a confidence score. Built to handle concurrent traffic safely using
async task processing.

---

## System Architecture

Client
│
▼
┌─────────────────────────────┐
│        FastAPI (API)         │  ← JWT auth, rate limiting, input validation
│     POST /predict            │
│     GET  /result/{id}        │
└──────────┬──────────────────┘
│
┌─────▼──────┐     ┌──────────────┐
│   Redis     │────▶│ Celery Worker │  ← runs ML model
│  (Queue +   │     │              │
│   Cache)    │     └──────┬───────┘
└─────────────┘            │
▼
┌──────────────────┐
│   PostgreSQL      │  ← stores every prediction
└──────────────────┘



---

## Why a Queue?

Without a queue, the API would block for 300–1600ms per request while the ML
model runs. Under concurrent load, this causes request timeouts and thread
exhaustion.

With Redis + Celery:
- API receives request → drops task in queue → responds in <5ms with a task_id
- Worker picks up task independently → runs model → stores result
- Client polls GET /result/{id} when ready

This decoupling means the API can accept thousands of requests without waiting
for inference to complete.

---

## Why Caching?

Toxic comments tend to repeat — spam, hate speech, and bot traffic often send
identical or near-identical text. Caching identical requests in Redis means:
- Second request for same text: returned in <5ms (no model inference)
- Reduced worker load under repeated traffic
- In load testing, cached responses averaged ~5ms vs ~1600ms uncached

Cache key: SHA256 hash of the lowercased, stripped input text.
Cache TTL: 1 hour.

---

## Database Schema

Table: `predictions`

| Column             | Type      | Purpose                        |
|--------------------|-----------|--------------------------------|
| id                 | UUID      | Unique row identifier          |
| request_id         | String    | Maps to Celery task ID         |
| input_text         | Text      | The submitted comment          |
| prediction         | String    | "toxic" or "non-toxic"         |
| confidence         | Float     | Model confidence score (0–1)   |
| processing_time_ms | Float     | Worker inference latency       |
| created_at         | DateTime  | Timestamp                      |

---

## ML Model

Model: `unitary/toxic-bert` (HuggingFace)
- BERT fine-tuned on the Jigsaw Toxic Comments dataset
- Multi-label: toxic, severe_toxic, obscene, threat, insult, identity_hate
- Aggregation: max score across all labels → overall toxicity confidence
- Threshold: score > 0.5 → "toxic"
- Local (GPU): ~140ms inference
- Cloud (CPU): ~1600ms inference

---

## Failure Handling

| Failure | Handling |
|---------|----------|
| Worker crashes mid-task | Celery retries 3x with exponential backoff (2s, 4s, 8s) |
| Redis unavailable | API returns 500; worker retries connection on startup |
| PostgreSQL unavailable | Worker task fails → Celery retry |
| Invalid JWT | 401 Unauthorized returned immediately |
| Rate limit exceeded | 429 Too Many Requests (10 req/min per IP) |
| Text too long (>5000 chars) | 422 Validation Error |

---

## Load Test Results

| Users | Avg Latency | RPS | Failures |
|-------|-------------|-----|----------|
| 100   | 52ms        | 44  | 0%       |
| 500   | 106ms       | 231 | 0%       |

Bottleneck: single Celery worker running ML inference on CPU.

---

## Scaling Strategy

**Horizontal (recommended):**
- Add more Celery workers — each independently pulls from Redis queue
- No code changes required; Redis distributes tasks automatically

**Vertical:**
- Upgrade worker instance to GPU — reduces inference from 1600ms to 140ms

**Database:**
- Add read replicas for GET /result queries
- Connection pooling via PgBouncer for high concurrency

**Cache:**
- Increase Redis memory for larger cache hit rate
- Tune TTL based on observed repeat request patterns

---

## Bottlenecks

1. **ML Inference (primary):** Single CPU worker limits throughput. Fix: scale workers horizontally.
2. **Cold start:** Model loads once at worker startup (~5s). Subsequent requests are fast.
3. **PostgreSQL writes:** Every prediction writes to DB. Fix: batch writes or async writes.
4. **Redis memory:** Cache eviction under high unique-text volume. Fix: increase instance size.

---

## Tradeoffs

| Decision | Tradeoff |
|----------|----------|
| Async queue (Celery) | Client must poll for result vs simpler sync response |
| Pre-trained model | No custom training data needed vs less control over accuracy |
| Redis for both queue and cache | Simpler ops vs single point of failure for both |
| PostgreSQL | ACID guarantees vs slower than NoSQL for high write throughput |

---

## Future Improvements

- **Kafka** instead of Redis queue for higher throughput and message durability
- **Model versioning** — A/B test multiple models, route traffic by percentage
- **Prometheus + Grafana** — real-time latency and throughput dashboards
- **Batch inference** — group multiple requests and run model once
- **WebSocket** — push result to client instead of polling GET /result
- **User accounts** — per-user API keys, usage tracking, billing
