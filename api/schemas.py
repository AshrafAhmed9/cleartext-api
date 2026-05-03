from pydantic import BaseModel, Field, field_validator
from typing import Optional
import re

class PredictRequest(BaseModel):
    text: str = Field(min_length=1, max_length=5000)

    @field_validator("text")
    @classmethod
    def sanitize_text(cls, v):
        # Strip HTML tags
        v = re.sub(r"<[^>]+>", "", v)
        # Strip script injections
        v = re.sub(r"(javascript|onclick|onerror)\s*:", "", v, flags=re.IGNORECASE)
        # Collapse whitespace
        v = " ".join(v.split())
        if not v:
            raise ValueError("Text is empty after sanitization")
        return v

class PredictQueued(BaseModel):
    task_id: str
    status: str = "queued"

class PredictResult(BaseModel):
    task_id: Optional[str] = None
    status: str
    prediction: Optional[str] = None
    confidence: Optional[float] = None
    cached: bool = False
    processing_time_ms: Optional[float] = None
