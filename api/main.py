from fastapi import FastAPI, Request
from fastapi.security import OAuth2PasswordRequestForm
from fastapi import Depends
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from api.routes import predict, health
from api.auth import create_token
from db.database import init_db
from core.config import settings

limiter = Limiter(key_func=get_remote_address, default_limits=[settings.rate_limit])

app = FastAPI(title="Toxic Comment Detection API")
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.include_router(predict.router)
app.include_router(health.router)

@app.on_event("startup")
def startup():
    init_db()

@app.post("/token")
def login(form_data: OAuth2PasswordRequestForm = Depends()):
    if form_data.username != "admin" or form_data.password != "secret":
        from fastapi import HTTPException
        raise HTTPException(status_code=401, detail="Wrong credentials")
    return {"access_token": create_token(form_data.username), "token_type": "bearer"}
