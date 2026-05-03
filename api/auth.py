from datetime import datetime, timedelta
from jose import jwt, JWTError
from fastapi import HTTPException, Depends
from fastapi.security import OAuth2PasswordBearer
from core.config import settings
import redis
from core.config import settings

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/token")

# Redis client for tracking failed attempts
_redis = redis.from_url(settings.redis_url)

MAX_ATTEMPTS = 5
LOCKOUT_SECONDS = 300  # 5 minutes

def check_brute_force(ip: str):
    key = f"failed_login:{ip}"
    attempts = _redis.get(key)
    if attempts and int(attempts) >= MAX_ATTEMPTS:
        raise HTTPException(
            status_code=429,
            detail="Too many failed login attempts. Try again in 5 minutes."
        )

def record_failed_attempt(ip: str):
    key = f"failed_login:{ip}"
    _redis.incr(key)
    _redis.expire(key, LOCKOUT_SECONDS)

def clear_failed_attempts(ip: str):
    _redis.delete(f"failed_login:{ip}")

def create_token(username: str) -> str:
    payload = {
        "sub": username,
        "exp": datetime.utcnow() + timedelta(hours=24)
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)

def get_current_user(token: str = Depends(oauth2_scheme)) -> str:
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        return payload["sub"]
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")
