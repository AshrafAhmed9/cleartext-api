# ClearText — Asynchronous ML Serving Infrastructure

![CI](https://github.com/AshrafAhmed9/cleartext-api/actions/workflows/ci.yml/badge.svg)

ClearText is an async inference platform that serves a slow ML model to many concurrent users without falling over. A BERT toxicity classifier is the example workload, but the actual project is the serving layer around it: request batching, model-versioned caching, a circuit breaker, a dead-letter queue, and Prometheus/Grafana observability.

Built with FastAPI, Celery, Redis, PostgreSQL, and HuggingFace Transformers.

---

## The problem

A BERT model takes 150–300ms to classify one comment on CPU. Fine for one request. Not fine for 500 concurrent ones: a web server has a fixed number of threads, and if each is blocked for 250ms waiting on inference, the whole API stops answering, including endpoints that have nothing to do with the model.

The fix is to stop making the caller wait. `POST /predict` never runs the model inline. It enqueues the job with Celery and returns a task ID in a couple of milliseconds. A separate worker process picks the job up, runs inference, and the caller polls `GET /result/{id}` for the answer. The API and the worker are two independent processes connected only through Redis, so the slow part can never block the fast part.

Everything else in this project, the batching, the caching, the circuit breaker, the dead-letter queue, exists to make that handoff hold up under real load and real failures.

---

## Request flow

```
Client → POST /predict
           │
     ┌─────▼──────┐   HIT    ┌────────────────────────────────┐
     │ Redis Cache │─────────▶│ Return result, <5ms             │
     │ (versioned) │          │ key = (model_version, text)     │
     └─────┬──────┘          └────────────────────────────────┘
           │ MISS
     ┌─────▼──────────────┐
     │ Circuit Breaker     │──── OPEN ──▶ 503 + Retry-After
     └─────┬──────────────┘
           │ CLOSED
     ┌─────▼───────────────────────────────────────────┐
     │ Celery Worker (thread pool)                      │
     │   → Micro-Batcher (collects requests, ≤8ms)      │
     │   → ONE classifier([t1, t2, ...]) forward pass   │
     │   → PostgreSQL (persist) + Redis (cache)         │
     │   → on 3rd failure → Dead-Letter Queue            │
     └───────────────────────────────────────────────────┘
           │
     Client polls GET /result/{task_id}
```

Job status moves `queued → processing → completed`, or `failed` after 3 retries with exponential backoff, at which point the job lands in the dead-letter queue instead of disappearing.

---

## Design decisions

**Request batching.** Multiple Celery threads can be classifying text at once. A background thread in the worker collects whatever requests arrive within an 8ms window (up to 16 of them) and runs them as a single model forward pass instead of one at a time. A batch of 16 costs barely more than a batch of 1, so this is close to free throughput. It's safe because the model is deterministic: a batched result is identical to running each input alone.

**Model-versioned cache.** The Redis cache key is a hash of `(model_version, text)`, not just the text. Swap the model version and every old cache entry becomes unreachable automatically. No manual flush, no risk of serving an answer from a model that's no longer running.

**Circuit breaker.** Before enqueueing a job, the API checks two signals: does the worker have a recent heartbeat, and is the queue backlog under a limit. If either check fails, `/predict` returns `503` with a `Retry-After` header instead of queueing work nothing is available to process.

**Dead-letter queue.** A job that fails 3 times (with 1s/2s/4s backoff between attempts) isn't dropped. The original text, the error, and the full traceback get pushed to a Redis list. `/dlq` lists them, `/dlq/{id}/replay` re-runs one.

---

## Performance

Load-tested with Locust at 500 concurrent users against the full local stack (API, worker, Postgres, Redis in Docker):

| Endpoint | Requests | Failures | Median | Req/s |
|---|---|---|---|---|
| POST /predict | 15,074 | 0 | 2ms | 169.1 |
| GET /health | 5,050 | 0 | 3ms | 56.7 |
| POST /token | 500 | 0 | 21ms | 5.6 |
| **Aggregated** | 20,624 | **0** | 2ms | **231.4** |

**231 req/s, zero failures at 500 concurrent users.**

One caveat worth stating plainly: `/predict`'s 2ms median is *enqueue* latency, not time-to-answer. The endpoint deliberately returns before the model runs. Real end-to-end latency (submit, then poll until the model finishes) is bounded by actual inference: ~150–300ms uncached on CPU, near-instant on a cache hit.

---

## Tech stack

- **API:** FastAPI, Python 3.11
- **Queue:** Celery + Redis
- **Database:** PostgreSQL, SQLAlchemy, Alembic migrations
- **Model:** `unitary/toxic-bert` (HuggingFace). The example workload; the serving layer itself is model-agnostic.
- **YouTube analysis:** YouTube Data API v3 + Groq (`openai/gpt-oss-120b`) for comment-section summaries
- **Observability:** Prometheus + Grafana
- **Auth:** JWT with brute-force lockout
- **Testing:** pytest, 29 tests, one against a real Postgres instance
- **CI/CD:** GitHub Actions
- **Load testing:** Locust
- **Containers:** Docker + docker-compose, 6 services

---

## API

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/token` | Get a JWT access token |
| POST | `/predict` | Submit text for toxicity analysis |
| GET | `/result/{task_id}` | Fetch a prediction result |
| POST | `/analyze/youtube` | Analyze a YouTube video's comments |
| GET | `/health` | Health check (Redis, DB, queue, DLQ, worker) |
| GET | `/metrics` | JSON metrics: jobs, cache, latency percentiles |
| GET | `/metrics/prometheus` | Prometheus exposition format |
| GET | `/dlq` | List dead-letter queue entries |
| POST | `/dlq/{task_id}/replay` | Re-enqueue a failed job |

---

## Observability

A Grafana dashboard (auto-provisioned from `ops/grafana/dashboards/cleartext.json`) tracks request rate, cache hit rate, queue and DLQ depth, inference and end-to-end latency (p50/p95/p99), realized batch sizes, worker load, and circuit breaker trips. Available at `http://localhost:3001` (`admin`/`admin`) after `docker compose up`.

Prometheus scrapes the API (`/metrics/prometheus`) and the worker (port `9100`) directly, so the same numbers are queryable outside Grafana too.

---

## Running it

**One command:**

```bash
./demo.sh
```

Builds and starts all 6 backend services plus the frontend, then opens `http://localhost:5173`. Log in with `admin` / `secret`.

**Docker, manually:**

```bash
docker compose up --build
```

| Service | URL |
|---------|-----|
| API docs | http://localhost:8000/docs |
| Grafana | http://localhost:3001 (admin/admin) |
| Prometheus | http://localhost:9090 |

**Without Docker** (Python 3.11+ required, Postgres/Redis still via Docker):

```bash
git clone https://github.com/AshrafAhmed9/cleartext-api.git
cd cleartext-api
cp .env.example .env                    # add YOUTUBE_API_KEY / GROQ_API_KEY to use those endpoints
docker compose up -d postgres redis
pip install -r requirements.txt
alembic upgrade head
celery -A core.celery_app worker --loglevel=info --pool=threads   # terminal 1
uvicorn api.main:app --reload                                      # terminal 2
```

Open `http://localhost:8000/docs`.

---

## Testing

```bash
pytest tests/ -v
```

29 tests covering auth, predictions, cache versioning, the circuit breaker, the micro-batcher, the dead-letter queue, metrics, health checks, and worker tasks. One test writes to and reads back from a real Postgres instance; the rest mock Redis. CI runs the same suite against Postgres in GitHub Actions.

Load testing: `locust --host http://localhost:8000`, then open `http://localhost:8089`. The Performance numbers above came from a 500-user run.

---

## Project structure

```
api/            FastAPI app: routes, auth, health, metrics, DLQ
worker/         Celery task, model inference, micro-batcher, startup hooks
core/           Shared config, Celery setup, cache, circuit breaker, metrics
db.py           Prediction model, engine, session
migrations/     Alembic, two revisions, honest schema history
ops/            Prometheus config + Grafana provisioning/dashboards
tests/          29 tests
frontend/       React (Vite): comment analysis + YouTube analysis
locustfile.py   Load test
.github/        CI workflow
```

---

## Frontend

A small React app (Vite): log in, then either analyze a single comment or a YouTube video's comment section.

```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173`.
