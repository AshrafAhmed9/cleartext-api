from sqlalchemy import Column, String, Float, DateTime, Text
from sqlalchemy.orm import DeclarativeBase
from datetime import datetime
import uuid

class Base(DeclarativeBase):
    pass

class Prediction(Base):
    __tablename__ = "predictions"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    request_id = Column(String, index=True)   # maps to Celery task_id
    input_text = Column(Text)
    prediction = Column(String)               # "toxic" or "non-toxic"
    confidence = Column(Float)
    model_version = Column(String, nullable=True)  # model that produced this row
    processing_time_ms = Column(Float)        # worker duration (batch wait + inference)
    status = Column(String, default="queued") # queued|processing|completed|failed
    queued_at = Column(DateTime, default=datetime.utcnow)
    started_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
