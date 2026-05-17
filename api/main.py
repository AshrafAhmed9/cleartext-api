from fastapi import FastAPI, Request, Depends, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from api.routes import predict, health, youtube, metrics
from api.auth import create_token, check_brute_force, record_failed_attempt, clear_failed_attempts
from api.middleware.security import SecurityHeadersMiddleware, RequestIDMiddleware
from db.database import init_db
from core.config import settings

limiter = Limiter(key_func=get_remote_address, default_limits=[settings.rate_limit])

app = FastAPI(
    title="ClearText — AI Inference Backend",
    description="""
## Asynchronous AI Inference & Processing Backend

A production-inspired backend platform for scalable ML inference.
Accepts text or YouTube URLs, processes via async worker pipeline,
and returns structured AI analysis with full observability.

### Architecture
- **Async queue** (Celery + Redis) — non-blocking inference, API responds in <5ms
- **Worker pipeline** — BERT model inference, max 3 retries with exponential backoff
- **Caching layer** — identical inputs served from Redis in <5ms
- **Observability** — `/metrics` endpoint, structured JSON logs, request ID tracing
- **Security** — JWT auth, rate limiting, brute force protection, XSS sanitization

### Use Cases
- Single comment toxicity classification (POST /predict)
- YouTube video comment sentiment analysis (POST /analyze/youtube)
    """,
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(RequestIDMiddleware)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.include_router(predict.router, tags=["Comment Analysis"])
app.include_router(health.router, tags=["System"])
app.include_router(youtube.router, tags=["YouTube Analysis"])
app.include_router(metrics.router, tags=["System"])

@app.on_event("startup")
def startup():
    init_db()

@app.get("/", response_class=HTMLResponse, include_in_schema=False)
def landing():
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>ClearText API</title>
        <style>
            body { font-family: -apple-system, sans-serif; max-width: 600px; margin: 80px auto; padding: 0 20px; color: #333; }
            h1 { font-size: 2rem; margin-bottom: 0.5rem; }
            p { color: #666; line-height: 1.6; }
            .links { margin-top: 2rem; display: flex; gap: 1rem; }
            a { padding: 10px 20px; border-radius: 6px; text-decoration: none; font-weight: 500; }
            .primary { background: #2563eb; color: white; }
            .secondary { border: 1px solid #ddd; color: #333; }
            .badge { display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 0.75rem; background: #dcfce7; color: #166534; margin-left: 8px; }
        </style>
    </head>
    <body>
        <h1>ClearText API <span class="badge">v1.0.0</span></h1>
        <p>Production-inspired asynchronous AI inference backend. Built with FastAPI, Celery, Redis, PostgreSQL, and BERT.</p>
        <div class="links">
            <a href="/redoc" class="primary">Documentation</a>
            <a href="/docs" class="secondary">Swagger UI</a>
            <a href="/health" class="secondary">Health Check</a>
            <a href="/metrics" class="secondary">Metrics</a>
        </div>
    </body>
    </html>
    """

@app.post("/token", tags=["Auth"], summary="Get access token")
def login(request: Request, form_data: OAuth2PasswordRequestForm = Depends()):
    ip = request.client.host
    check_brute_force(ip)
    if form_data.username != "admin" or form_data.password != "secret":
        record_failed_attempt(ip)
        raise HTTPException(status_code=401, detail="Wrong credentials")
    clear_failed_attempts(ip)
    return {"access_token": create_token(form_data.username), "token_type": "bearer"}
