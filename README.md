# ClearText — Asynchronous ML Serving Infrastructure

![CI](https://github.com/AshrafAhmed9/cleartext-api/actions/workflows/ci.yml/badge.svg)

**Live demo:** [frontend-ashraf-s-projects2.vercel.app](https://frontend-ashraf-s-projects2.vercel.app) · **API docs:** [cleartext-api-production-12ca.up.railway.app/docs](https://cleartext-api-production-12ca.up.railway.app/docs)

A production-grade asynchronous inference platform demonstrating how to serve a slow, expensive ML model to many concurrent users reliably — request batching, model-versioned caching, a circuit breaker, a dead-letter queue, and full Prometheus/Grafana observability, built around a BERT toxicity classifier as the example workload.

Built with FastAPI, Celery, Redis, PostgreSQL, and HuggingFace Transformers.

---

## Engineering Highlights

| Feature | What it does | Why it matters |
|---------|-------------|----------------|
| Request Batching | Merges concurrent inferences into one model forward pass | Real throughput gain — the canonical ML-serving optimization |
| Model-Versioned Cache | Cache key = `(model_version, text)` | A model swap can never serve stale answers |
| Dead-Letter Queue | Failed jobs pushed to inspectable Redis DLQ with replay | Failures don't vanish — reliability pattern |
| Circuit Breaker | 503 + Retry-After when worker is down or queue full | Graceful degradation vs silent queueing |
| Cache Eviction | Redis `maxmemory 256mb` + `allkeys-lru` | Cache can't grow unbounded |
| Prometheus Metrics | p50/p95/p99 latency, cache hit rate, queue depth, batch size | Discuss behavior under load with numbers |
| Grafana Dashboard | 8-panel dashboard: RPS, latency, cache, queue, batching, breaker | Portfolio screenshots backed by real data |
| Alembic Migrations | Reviewable, versioned schema changes | Production-readiness signal |
| Completion Webhook | Optional `callback_url` — push instead of poll | Modern async integration pattern |
| k6 Load Tests | Second load-testing tool alongside Locust | Quantified bullets for the resume |

---

## What It Does

| Feature | Description |
|---------|-------------|
| Comment Analysis | Submit any text → get toxic/non-toxic prediction with confidence score |
| YouTube Analysis | Submit a YouTube URL → analyze 100 comments → get AI-powered insights |
| Async Processing | Tasks queued via Redis + Celery, non-blocking API responses |
| Caching | Model-versioned cache — identical inputs served from Redis in <5ms |
| Batching | Concurrent requests merged into one forward pass for throughput |
| Reliability | Circuit breaker, dead-letter queue, 3x retry with exponential backoff |
| Security | JWT auth, rate limiting, brute force protection, XSS sanitization |
| Observability | Prometheus metrics, Grafana dashboard, structured JSON logs, request ID tracing |

---

## Request Flow

```
Client → POST /predict
           │
     ┌─────▼─────────────────────────────────┐
     │  FastAPI: Auth + Rate Limit + Sanitize  │
     └─────┬─────────────────────────────────┘
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
     │   → Webhook callback (if callback_url set)      │
     │   → On terminal failure → Dead-Letter Queue     │
     └────────────────────────────────────────────────┘
           │
     Client polls GET /result/{task_id}
     (or receives webhook POST to callback_url)
```

**Job lifecycle:** `QUEUED → PROCESSING → COMPLETED` (or `FAILED` after 3 retries → DLQ)

---

## Screenshots

### Login
![Login](screenshots/login.png)

### Comment Analysis — Toxic
![Comment Toxic](screenshots/comment-result.png)

### Comment Analysis — Non-Toxic
![Comment Non-Toxic](screenshots/comment-nontoxic.png)

### YouTube Analysis
![YouTube Analysis](screenshots/youtube-analysis.png)

### API Documentation (Swagger)
![Swagger](screenshots/swagger.png)

### Docker Containers
![Docker](screenshots/docker.png)

---

## Performance

| Users | Avg Latency | p95 Latency | RPS | Failures |
|-------|-------------|-------------|-----|----------|
| 100   | 52ms        | 85ms        | 44  | 0%       |
| 500   | 106ms       | 240ms       | 231 | 0%       |

Load tested with Locust + k6. Latency measured end-to-end including queue wait. Inference-only latency: ~140ms (GPU) / ~1600ms (CPU).

---

## Tech Stack

- **API:** FastAPI, Python 3.11
- **Queue:** Celery + Redis (thread pool for batching)
- **Database:** PostgreSQL + SQLAlchemy + Alembic migrations
- **ML Model:** `unitary/toxic-bert` (HuggingFace BERT) — the example workload; the serving infrastructure is model-agnostic
- **AI Insights:** Groq API (`openai/gpt-oss-120b`)
- **YouTube:** YouTube Data API v3
- **Observability:** Prometheus + Grafana, structured JSON logs
- **Security:** JWT, slowapi, OWASP headers
- **Testing:** pytest, pytest-mock (29 tests)
- **CI/CD:** GitHub Actions
- **Load Testing:** Locust + k6
- **Containerization:** Docker + docker-compose (6 services)
- **Deployment:** Railway

---

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/token` | Get JWT access token |
| POST | `/predict` | Submit comment for analysis (optional `callback_url`) |
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

The pre-built dashboard (`ops/grafana/dashboards/cleartext.json`) includes:

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

### Local Development

**Prerequisites:** Python 3.8+, Docker

1. Clone the repo:
```bash
git clone https://github.com/AshrafAhmed9/cleartext-api.git
cd cleartext-api
```

2. Create `.env`:
```env
DATABASE_URL=postgresql://postgres:postgres@127.0.0.1:5433/flagship
REDIS_URL=redis://localhost:6379/0
JWT_SECRET=your-secret-key
JWT_ALGORITHM=HS256
RATE_LIMIT=10/minute
CACHE_TTL=3600
YOUTUBE_API_KEY=your-youtube-api-key
GROQ_API_KEY=your-groq-api-key
```

3. Start dependencies:
```bash
docker compose up -d postgres redis
```

4. Install, migrate, and run:
```bash
pip install -r requirements.txt
alembic upgrade head
celery -A core.celery_app worker --loglevel=info --pool=threads   # Terminal 1
uvicorn api.main:app --reload                                      # Terminal 2
```

5. Open `http://localhost:8000/docs`

### Docker (Full Stack — 6 services)

```bash
docker compose up --build
```

Services: PostgreSQL, Redis (LRU), API, Worker, Prometheus, Grafana.

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

29 tests covering auth, predictions, cache versioning, circuit breaker, dead-letter queue, metrics (JSON + Prometheus), health checks, and worker tasks. All external dependencies mocked.

---

## Load Testing

### Locust
```bash
locust -f load_testing/locustfile.py --host http://localhost:8000
```
Open `http://localhost:8089` → set users → start.

### k6
```bash
k6 run load_testing/k6_predict.js
```

---

## Security Features

- JWT authentication (24hr expiry)
- Rate limiting: 10 requests/minute per IP
- Brute force protection: IP lockout after 5 failed login attempts (5 min)
- XSS input sanitization (strips HTML/scripts before inference)
- OWASP security headers (CSP, HSTS, X-Frame-Options, etc.)
- Structured JSON audit logging with request ID tracing
- Webhook callback URL validation (http/https only)

---

## Project Structure

```
├── api/
│   ├── main.py              # FastAPI app, middleware, routes
│   ├── auth.py              # JWT + brute force protection
│   ├── schemas.py           # Request/response models + sanitization
│   ├── middleware/
│   │   └── security.py      # Security headers + request ID middleware
│   └── routes/
│       ├── predict.py       # /predict + /result + circuit breaker
│       ├── health.py        # /health (Redis, DB, queue, DLQ, worker)
│       ├── metrics.py       # /metrics (JSON) + /metrics/prometheus
│       ├── dlq.py           # Dead-letter queue inspect + replay
│       └── youtube.py       # YouTube analysis endpoint
├── worker/
│   ├── tasks.py             # Celery task with DLQ + webhook
│   ├── ml_model.py          # toxic-bert inference (single + batch)
│   ├── batcher.py           # In-process micro-batcher
│   └── bootstrap.py         # Worker startup: metrics server + heartbeat
├── core/
│   ├── config.py            # Environment settings (batching, breaker, etc.)
│   ├── celery_app.py        # Celery configuration (thread pool)
│   ├── cache.py             # Model-versioned Redis cache
│   ├── breaker.py           # Circuit breaker (heartbeat + queue depth)
│   ├── metrics.py           # Prometheus metric definitions
│   └── logging_config.py    # Structured JSON audit logging
├── db/
│   ├── database.py          # SQLAlchemy engine + session
│   └── models.py            # Prediction table (with model_version)
├── migrations/              # Alembic migrations
│   └── versions/
│       ├── 001_initial_schema.py
│       └── 002_add_model_version.py
├── ops/
│   ├── prometheus/prometheus.yml
│   └── grafana/
│       ├── provisioning/    # Datasource + dashboard provisioning
│       └── dashboards/cleartext.json
├── tests/                   # pytest suite (29 tests)
├── frontend/                # React frontend (Vite)
├── load_testing/
│   ├── locustfile.py        # Locust load tests
│   └── k6_predict.js        # k6 load tests
├── .github/workflows/
│   └── ci.yml               # GitHub Actions CI (with migrations)
├── docker-compose.yml       # 6 services: postgres, redis, api, worker, prometheus, grafana
├── alembic.ini
└── ARCHITECTURE.md
```

---

## Frontend

React frontend built with Vite. Run separately:

```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173`
