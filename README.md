# ClearText — Asynchronous ML Serving Infrastructure

![CI](https://github.com/AshrafAhmed9/cleartext-api/actions/workflows/ci.yml/badge.svg)

A production-grade asynchronous inference platform demonstrating how to serve a slow, expensive ML model to many concurrent users reliably — request batching, model-versioned caching, a circuit breaker, a dead-letter queue, and full Prometheus/Grafana observability, built around a BERT toxicity classifier as the example workload.

Built with FastAPI, Celery, Redis, PostgreSQL, and HuggingFace Transformers.

---

## Engineering Highlights

| Feature | What it does | Why it matters |
|---------|-------------|----------------|
| Request Batching | Merges concurrent inferences into one model forward pass (`batch_max_size=16`) | Real throughput gain — the canonical ML-serving optimization |
| Model-Versioned Cache | Cache key = `(model_version, text)` | A model swap can never serve stale answers |
| Dead-Letter Queue | Failed jobs pushed to inspectable Redis DLQ with replay | Failures don't vanish — reliability pattern |
| Circuit Breaker | 503 + Retry-After when worker is down or queue full | Graceful degradation vs silent queueing |
| Prometheus Metrics | p50/p95/p99 latency, cache hit rate, queue depth, batch size | Discuss behavior under load with numbers |
| Grafana Dashboard | 8-panel dashboard: RPS, latency, cache, queue, batching, breaker | Real data, not a mockup |
| Alembic Migrations | Reviewable, versioned schema changes | Production-readiness signal |

---

## What It Does

| Feature | Description |
|---------|-------------|
| Comment Analysis | Submit any text → get toxic/non-toxic prediction with confidence score |
| YouTube Analysis | Submit a YouTube URL → analyze 100 comments → AI-generated insights (Groq) |
| Async Processing | Tasks queued via Redis + Celery, non-blocking API responses |
| Caching | Model-versioned cache — identical inputs served from Redis in <5ms |
| Batching | Concurrent requests merged into one forward pass for throughput |
| Reliability | Circuit breaker, dead-letter queue, 3x retry with exponential backoff |

---

## Request Flow

```
Client → POST /predict
           │
     ┌─────▼──────┐   HIT    ┌───────────────────────────────┐
     │ Redis Cache │─────────▶│ Return result <5ms             │
     │ (versioned) │          │ key = (model_version, text)    │
     └─────┬──────┘          └───────────────────────────────┘
           │ MISS
     ┌─────▼──────────────┐
     │ Circuit Breaker     │──── OPEN ──▶ 503 + Retry-After
     └─────┬──────────────┘
           │ CLOSED
     ┌─────▼──────────────────────────────────────────┐
     │ Redis Queue → Celery Worker (thread pool)       │
     │   → Micro-Batcher (collects N texts, ≤8ms)     │
     │   → ONE classifier([t1,t2,...]) forward pass    │
     │   → PostgreSQL (persist) + Redis Cache (store)  │
     │   → On terminal failure → Dead-Letter Queue     │
     └────────────────────────────────────────────────┘
           │
     Client polls GET /result/{task_id}
```

**Job lifecycle:** `QUEUED → PROCESSING → COMPLETED` (or `FAILED` after 3 retries → DLQ)

---

## Performance

Ramped to 500 concurrent users against a local API + worker (1 model instance, CPU inference, `batch_max_size=16`), Postgres and Redis in Docker:

| Endpoint | Requests | Failures | Median | Req/s |
|---|---|---|---|---|
| POST /predict | 15,074 | 0 | 2ms | 169.1 |
| GET /health | 5,050 | 0 | 3ms | 56.7 |
| POST /token | 500 | 0 | 21ms | 5.6 |
| **Aggregated** | 20,624 | **0** | 2ms | **231.4** |

**231 req/s, zero failures at 500 concurrent users.**

One honest caveat: `/predict` only *enqueues* the job onto Celery and returns immediately (that's the point of the async design) — its 2ms median is enqueue latency, not time-to-answer. True end-to-end latency (submit, then poll `/result` until the model actually finishes) means waiting on real BERT inference — ~150-300ms uncached on CPU, or near-instant on a cache hit (`core/cache.py`).

---

## Tech Stack

- **API:** FastAPI, Python 3.11
- **Queue:** Celery + Redis (thread pool for batching)
- **Database:** PostgreSQL + SQLAlchemy + Alembic migrations
- **ML Model:** `unitary/toxic-bert` (HuggingFace BERT) — the example workload; the serving infrastructure is model-agnostic
- **AI Insights:** Groq API (`openai/gpt-oss-120b`)
- **YouTube:** YouTube Data API v3
- **Observability:** Prometheus + Grafana
- **Security:** JWT auth, brute-force lockout
- **Testing:** pytest (29 tests, one against a real Postgres instance)
- **CI/CD:** GitHub Actions
- **Load Testing:** Locust
- **Containerization:** Docker + docker-compose (6 services)

---

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/token` | Get JWT access token |
| POST | `/predict` | Submit comment for analysis |
| GET | `/result/{task_id}` | Fetch prediction result |
| POST | `/analyze/youtube` | Analyze YouTube video comments |
| GET | `/health` | System health check (Redis, DB, queue, DLQ, worker) |
| GET | `/metrics` | Live JSON metrics (jobs, cache, latency p50/p95/p99, DLQ) |
| GET | `/metrics/prometheus` | Prometheus exposition format |
| GET | `/dlq` | List dead-letter queue entries |
| POST | `/dlq/{task_id}/replay` | Re-enqueue a failed job |

---

## Observability

### Grafana Dashboard

The pre-built dashboard (`ops/grafana/dashboards/cleartext.json`, loaded automatically) includes:

| Panel | Metric |
|-------|--------|
| Request Rate | `rate(predictions_total[1m])` by result label |
| Cache Hit Rate | hits / (hits + misses) as gauge |
| Queue Depth | Celery queue + DLQ depth |
| Inference Latency | p50/p95/p99 via `inference_latency_seconds` histogram |
| End-to-End Latency | p50/p95/p99 via `end_to_end_latency_seconds` histogram |
| Batch Size | p50/p95 realized batch sizes |
| Worker In-Flight | Active requests in the worker |
| Circuit Breaker Trips | 5-minute trip rate |

Access at `http://localhost:3001` (admin/admin) after `docker compose up`.

### Prometheus Metrics

Scraped from the API (`/metrics/prometheus`) and worker (`:9100`):

- `inference_latency_seconds` — model forward-pass latency (histogram)
- `end_to_end_latency_seconds` — batch wait + inference (histogram)
- `inference_batch_size` — requests per forward pass (histogram)
- `cache_hits_total` / `cache_misses_total` — cache counters
- `queue_depth` / `dlq_depth` — queue gauges
- `circuit_breaker_trips_total` — breaker trip counter
- `worker_inflight_requests` — current worker load

---

## Quick Start

### One-Command Demo

```bash
./demo.sh
```

Builds and starts all 6 backend services (API, worker, Postgres, Redis,
Prometheus, Grafana) plus the frontend, then opens
`http://localhost:5173` in your browser. Log in with `admin` / `secret`.

### Local Development

**Prerequisites:** Python 3.11+, Docker

1. Clone the repo and copy the env template:
```bash
git clone https://github.com/AshrafAhmed9/cleartext-api.git
cd cleartext-api
cp .env.example .env   # fill in YOUTUBE_API_KEY / GROQ_API_KEY if you want those endpoints
```

2. Start dependencies:
```bash
docker compose up -d postgres redis
```

3. Install, migrate, and run:
```bash
pip install -r requirements.txt
alembic upgrade head
celery -A core.celery_app worker --loglevel=info --pool=threads   # Terminal 1
uvicorn api.main:app --reload                                      # Terminal 2
```

4. Open `http://localhost:8000/docs`

### Docker (Full Stack — 6 services)

```bash
docker compose up --build
```

Services: PostgreSQL, Redis, API, Worker, Prometheus, Grafana.

| Service | URL |
|---------|-----|
| API docs | http://localhost:8000/docs |
| Grafana | http://localhost:3001 (admin/admin) |
| Prometheus | http://localhost:9090 |

---

## Testing

```bash
pytest tests/ -v
```

29 tests covering auth, predictions, cache versioning, circuit breaker, the micro-batcher, dead-letter queue, metrics, health checks, and worker tasks — one of them (`test_worker.py::test_run_inference_persists_to_real_db`) writes to and reads back from a real Postgres instance; everything else mocks Redis.

---

## Load Testing

```bash
locust --host http://localhost:8000
```
Open `http://localhost:8089` → set users → start. `locustfile.py` sits at the repo root, so Locust finds it with no `-f` flag. See [Performance](#performance) above for a captured 500-user run.

---

## Security

- JWT authentication (24hr expiry)
- Brute-force protection: IP lockout after 5 failed login attempts (5 min)

---

## Project Structure

```
├── api/
│   ├── main.py        # FastAPI app, CORS, routers, login
│   ├── auth.py         # JWT + brute force protection
│   ├── predict.py       # /predict + /result + circuit breaker
│   ├── health.py        # /health (Redis, DB, queue, DLQ, worker)
│   ├── metrics.py        # /metrics (JSON) + /metrics/prometheus
│   ├── dlq.py            # Dead-letter queue inspect + replay
│   └── youtube.py        # YouTube analysis endpoint
├── worker/
│   ├── tasks.py          # Celery task: predict, persist, cache, retry/DLQ
│   ├── model.py           # toxic-bert inference (single + batch)
│   ├── batcher.py          # In-process micro-batcher
│   └── bootstrap.py        # Worker startup: metrics server + heartbeat
├── core/
│   ├── config.py          # All settings (batching, breaker, cache TTLs)
│   ├── celery_app.py       # Celery configuration (thread pool)
│   ├── cache.py             # Model-versioned Redis cache
│   ├── breaker.py            # Circuit breaker (heartbeat + queue depth)
│   └── metrics.py             # Prometheus metric definitions
├── db.py                       # Prediction model + engine/session
├── migrations/versions/
│   ├── 001_initial_schema.py
│   └── 002_add_model_version.py
├── ops/
│   ├── prometheus.yml
│   └── grafana/            # Provisioning + dashboards/cleartext.json
├── tests/                   # pytest suite (29 tests)
├── frontend/                 # React frontend (Vite) — one page
├── locustfile.py               # Locust load test (root, so `locust` needs no -f flag)
├── .github/workflows/ci.yml     # CI: Postgres + Alembic + pytest
├── docker-compose.yml             # 6 services
└── alembic.ini
```

---

## Frontend

React frontend built with Vite: log in, then two tabs — analyze a single comment, or analyze a YouTube video's comments.

```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173`
