from fastapi import FastAPI, Request, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from api.routes import predict, health
from api.auth import create_token, check_brute_force, record_failed_attempt, clear_failed_attempts
from api.middleware.security import SecurityHeadersMiddleware, RequestIDMiddleware
from db.database import init_db
from core.config import settings

limiter = Limiter(key_func=get_remote_address, default_limits=[settings.rate_limit])

app = FastAPI(title="Toxic Comment Detection API")
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(RequestIDMiddleware)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.include_router(predict.router)
app.include_router(health.router)

@app.on_event("startup")
def startup():
    init_db()

@app.post("/token")
def login(request: Request, form_data: OAuth2PasswordRequestForm = Depends()):
    ip = request.client.host
    check_brute_force(ip)

    if form_data.username != "admin" or form_data.password != "secret":
        record_failed_attempt(ip)
        raise HTTPException(status_code=401, detail="Wrong credentials")

    clear_failed_attempts(ip)
    return {"access_token": create_token(form_data.username), "token_type": "bearer"}
