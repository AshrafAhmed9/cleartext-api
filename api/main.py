"""Wires up the FastAPI app: CORS, routers, login, and startup DB setup."""
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.middleware.cors import CORSMiddleware

from api import predict, health, youtube, metrics, dlq
from api.auth import create_token, check_brute_force, record_failed_attempt, clear_failed_attempts
from db import init_db
from core.config import settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()  # no-op if Alembic already created the tables
    yield


app = FastAPI(title="ClearText — Async ML Inference Platform", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.cors_origins.split(",")],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(predict.router, tags=["Comment Analysis"])
app.include_router(health.router, tags=["System"])
app.include_router(youtube.router, tags=["YouTube Analysis"])
app.include_router(metrics.router, tags=["System"])
app.include_router(dlq.router, tags=["Reliability"])


@app.post("/token", tags=["Auth"], summary="Get access token")
def login(request: Request, form_data: OAuth2PasswordRequestForm = Depends()):
    ip = request.client.host
    check_brute_force(ip)
    if form_data.username != "admin" or form_data.password != "secret":
        record_failed_attempt(ip)
        raise HTTPException(status_code=401, detail="Wrong credentials")
    clear_failed_attempts(ip)
    return {"access_token": create_token(form_data.username), "token_type": "bearer"}
