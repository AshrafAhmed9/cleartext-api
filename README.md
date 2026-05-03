# ClearText API

A production-ready ML inference platform for toxic comment detection and YouTube video sentiment analysis.

Built with FastAPI, Celery, Redis, PostgreSQL, and BERT — containerized with Docker and deployed on Railway.

**Live API:** https://cleartext-api-production-12ca.up.railway.app/docs

---

## What It Does

| Feature | Description |
|---------|-------------|
| Comment Analysis | Submit any text → get toxic/non-toxic prediction with confidence score |
| YouTube Analysis | Submit a YouTube URL → analyze 100 comments → get AI-powered insights |
| Async Processing | Tasks queued via Redis + Celery, non-blocking API responses |
| Caching | Identical requests served from Redis cache in <5ms |
| Security | JWT auth, rate limiting, brute force protection, XSS sanitization, audit logs |

---

## Architecture

```
Client
  │
  ▼
FastAPI (JWT auth, rate limiting, security headers)
  │
  ├── Cache HIT  →  return instantly from Redis (<5ms)
  │
  └── Cache MISS →  enqueue Celery task
                        │
                    Redis Queue
                        │
                    Celery Worker
                        │
                    toxic-bert (GPU)
                        │
                    PostgreSQL + Redis Cache
```

---

## Performance

| Users | Avg Latency | RPS | Failures |
|-------|-------------|-----|----------|
| 100 | 52ms | 44 | 0% |
| 500 | 106ms | 231 | 0% |

---

## Tech Stack

- **API:** FastAPI, Python
- **Queue:** Celery + Redis
- **Database:** PostgreSQL + SQLAlchemy
- **ML Model:** `unitary/toxic-bert` (HuggingFace BERT)
- **AI Insights:** Groq API (Llama 3.3 70B)
- **YouTube:** YouTube Data API v3
- **Security:** JWT, slowapi, bcrypt, OWASP headers
- **Load Testing:** Locust
- **Containerization:** Docker + docker-compose
- **Deployment:** Railway

---

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/token` | Get JWT access token |
| POST | `/predict` | Submit comment for analysis |
| GET | `/result/{task_id}` | Fetch prediction result |
| POST | `/analyze/youtube` | Analyze YouTube video comments |
| GET | `/health` | System health check |

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
docker run --name pg -e POSTGRES_PASSWORD=postgres -e POSTGRES_DB=flagship -p 5433:5432 -d postgres:16-alpine
docker run --name redis -p 6379:6379 -d redis:7-alpine
```

4. Install and run:
```bash
pip install -r requirements.txt
celery -A core.celery_app worker --loglevel=info --pool=solo   # Terminal 1
uvicorn api.main:app --reload                                   # Terminal 2
```

5. Open `http://localhost:8000/docs`

### Docker (Full Stack)

```bash
docker-compose up --build
```

All 4 services start automatically. Open `http://localhost:8000/docs`.

---

## Security Features

- JWT authentication (24hr expiry)
- Rate limiting: 10 requests/minute per IP
- Brute force protection: IP lockout after 5 failed login attempts
- XSS input sanitization (strips HTML/scripts before inference)
- OWASP security headers (CSP, HSTS, X-Frame-Options, etc.)
- Structured JSON audit logging with request ID tracing

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
│       ├── predict.py       # /predict + /result endpoints
│       ├── health.py        # /health endpoint
│       └── youtube.py       # YouTube analysis endpoint
├── worker/
│   ├── tasks.py             # Celery task definitions
│   └── ml_model.py          # toxic-bert inference wrapper
├── core/
│   ├── config.py            # Environment settings
│   ├── celery_app.py        # Celery configuration
│   └── cache.py             # Redis cache helpers
├── db/
│   ├── database.py          # SQLAlchemy engine + session
│   └── models.py            # Prediction table schema
├── frontend/frontend2/      # React frontend (Vite)
├── load_testing/
│   └── locustfile.py        # Locust load test scenarios
├── docker-compose.yml
└── ARCHITECTURE.md          # Full system documentation
```

---

## Frontend

React frontend built with Vite. Run separately:

```bash
cd frontend/frontend2
npm install
npm run dev
```

Open `http://localhost:5173`

---

## Load Testing

```bash
locust -f load_testing/locustfile.py --host http://localhost:8000
```

Open `http://localhost:8089` → set users → start.
