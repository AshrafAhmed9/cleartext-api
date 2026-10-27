"""Creates the FastAPI app and plugs in the two groups of endpoints."""
from contextlib import asynccontextmanager

from fastapi import FastAPI

from api import predict, dlq
from db import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Runs once at startup: create the predictions table if it isn't there yet.
    init_db()
    yield


app = FastAPI(title="ClearText — Async ML Inference Platform", version="1.0.0", lifespan=lifespan)

app.include_router(predict.router, tags=["Comment Analysis"])
app.include_router(dlq.router, tags=["Reliability"])
