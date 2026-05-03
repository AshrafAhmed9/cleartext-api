from fastapi import FastAPI, Request, Depends, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.security import OAuth2PasswordRequestForm
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from api.routes import predict, health, youtube
from api.auth import create_token, check_brute_force, record_failed_attempt, clear_failed_attempts
from api.middleware.security import SecurityHeadersMiddleware, RequestIDMiddleware
from db.database import init_db
from core.config import settings
from fastapi.middleware.cors import CORSMiddleware


limiter = Limiter(key_func=get_remote_address, default_limits=[settings.rate_limit])

app = FastAPI(
    title="ClearText API",
    description="""
## Toxic Comment Detection & YouTube Analysis API

Detect toxic content in text and analyze YouTube video comment sections using ML.

### Features
- **Single comment analysis** — submit any text, get toxicity score
- **YouTube video analysis** — analyze 100 comments, get AI-powered insights
- **JWT authentication** — secure all endpoints
- **Rate limiting** — 10 requests/minute per IP

### Quick Start
1. POST `/token` with `username=admin` and `password=secret`
2. Use the token in the `Authorization: Bearer <token>` header
3. POST `/predict` with your text or POST `/analyze/youtube` with a YouTube URL
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
        <p>ML-powered toxic comment detection with YouTube video sentiment analysis. Built with FastAPI, Redis, PostgreSQL, and BERT.</p>
        <div class="links">
            <a href="/redoc" class="primary">Documentation</a>
            <a href="/docs" class="secondary">Swagger UI</a>
            <a href="/health" class="secondary">Health Check</a>
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
