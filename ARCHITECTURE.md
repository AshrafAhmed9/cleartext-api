# ClearText API — Architecture Documentation

## What It Does
A production-ready ML inference platform that:
1. Detects toxic comments via REST API (single text analysis)
2. Analyzes YouTube video comment sections and generates AI-powered insights

---

## System Architecture

Client
│
▼
┌─────────────────────────────────────────┐
│           FastAPI (API Layer)            │
│  JWT auth │ Rate limiting │ Security     │
│  headers  │ Brute force   │ Audit logs   │
├─────────────────────────────────────────┤
│  POST /predict       → single comment   │
│  GET  /result/{id}   → fetch result     │
│  POST /analyze/youtube → video analysis │
│  GET  /health        → system status    │
└──────────┬──────────────────────────────┘
│
┌─────▼──────┐     ┌──────────────────┐
│   Redis     │────▶│  Celery Worker   │
│ Queue+Cache │     │  toxic-bert GPU  │
└─────────────┘     └──────┬───────────┘
│
┌───────────▼──────────┐
│      PostgreSQL       │
│  stores predictions  │
└──────────────────────┘

YouTube Flow:
YouTube Data API → 100 comments → toxic-bert (each comment)
→ aggregated stats → Groq LLM (llama-3.3-70b) → AI insights



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

---

## Why a Queue?

Without a queue, the API blocks for 140–1600ms per request during ML inference.
With Redis + Celery: API responds in <5ms with task_id, worker processes independently.
This decoupling means 500 concurrent users can submit requests simultaneously without timeouts.

---

## Why Caching?

Repeated identical comments (spam, bots) skip inference entirely.
Cache key: SHA256 hash of lowercased input. TTL: 1 hour.
Result: cached requests return in <5ms vs 140-1600ms uncached.

---

## YouTube Analysis Pipeline

1. Extract video ID from URL
2. Fetch up to 100 comments via YouTube Data API v3
3. Run each comment through toxic-bert (GPU locally, CPU in Docker)
4. Aggregate: toxic count, non-toxic count, toxicity rate, community rating
5. Send sample comments to Groq (llama-3.3-70b-versatile) for AI insights
6. Return structured report with summary, themes, improvements, sentiment

---

## Database Schema

Table: `predictions`

| Column | Type | Purpose |
|--------|------|---------|
| id | UUID | Unique row identifier |
| request_id | String | Maps to Celery task ID |
| input_text | Text | The submitted comment |
| prediction | String | "toxic" or "non-toxic" |
| confidence | Float | Model confidence (0–1) |
| processing_time_ms | Float | Worker inference latency |
| created_at | DateTime | Timestamp |

---

## ML Model

Model: `unitary/toxic-bert` (HuggingFace)
- BERT fine-tuned on Jigsaw Toxic Comments dataset
- Multi-label: toxic, severe_toxic, obscene, threat, insult, identity_hate
- Aggregation: max score across all labels
- Threshold: score > 0.5 → "toxic"
- Local GPU: ~140ms | Docker CPU: ~1600ms

---

## Load Test Results

| Users | Avg Latency | RPS | Failures |
|-------|-------------|-----|----------|
| 100 | 52ms | 44 | 0% |
| 500 | 106ms | 231 | 0% |

Bottleneck: single Celery worker. Fix: horizontal scaling (add workers).

---

## Failure Handling

| Failure | Handling |
|---------|----------|
| Worker crash | Celery retries 3x, exponential backoff (2s, 4s, 8s) |
| Redis down | API returns 500; worker reconnects on startup |
| Invalid JWT | 401 immediately |
| Rate limit hit | 429 Too Many Requests |
| 5 failed logins | IP locked out for 5 minutes |
| XSS in input | Stripped before model sees it |
| Text > 5000 chars | 422 Validation Error |

---

## Scaling Strategy

- **Horizontal:** Add Celery workers — Redis distributes tasks automatically
- **Vertical:** GPU worker reduces inference from 1600ms to 140ms
- **Database:** Read replicas for GET /result, PgBouncer for connection pooling
- **YouTube:** Batch inference — run model on all 100 comments in parallel

---

## Tradeoffs

| Decision | Tradeoff |
|----------|----------|
| Async queue | Client must poll vs simpler sync |
| Pre-trained model | No training needed vs less control |
| Redis for queue + cache | Simpler ops vs single point of failure |
| Groq for insights | Free + fast vs external dependency |

---

## Future Improvements

- Kafka instead of Redis for durability
- Model versioning + A/B testing
- Prometheus + Grafana dashboards
- WebSocket push instead of polling
- Amazon product review analysis
- Batch YouTube comment inference (parallel workers)
