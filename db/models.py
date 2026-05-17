from sqlalchemy import Column, String, Float, DateTime, Text
from sqlalchemy.orm import DeclarativeBase
from datetime import datetime
import uuid

class Base(DeclarativeBase):
    pass

class Prediction(Base):
    __tablename__ = "predictions"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    request_id = Column(String, index=True)
    input_text = Column(Text)
    prediction = Column(String)               # "toxic" or "non-toxic"
    confidence = Column(Float)
    processing_time_ms = Column(Float)        # worker inference duration only (excludes queue wait)
    status = Column(String, default="queued") # queued|processing|completed|failed
    queued_at = Column(DateTime, default=datetime.utcnow)
    started_at = Column(DateTime, nullable=True)  # set when worker picks up task
    created_at = Column(DateTime, default=datetime.utcnow)
