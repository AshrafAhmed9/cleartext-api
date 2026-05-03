from pydantic import BaseModel, Field
from typing import Optional

class PredictRequest(BaseModel):
    text: str = Field(min_length=1, max_length=5000)

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
