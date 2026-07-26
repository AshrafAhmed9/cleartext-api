"""The one Prediction row per inference request, and how we talk to Postgres."""
import uuid
from datetime import datetime

from sqlalchemy import Column, String, Float, DateTime, Text, create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from core.config import settings


class Base(DeclarativeBase):
    pass


class Prediction(Base):
    __tablename__ = "predictions"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    request_id = Column(String, index=True)   # maps to Celery task_id
    input_text = Column(Text)
    prediction = Column(String)               # "toxic" or "non-toxic"
    confidence = Column(Float)
    model_version = Column(String, nullable=True)
    processing_time_ms = Column(Float)
    status = Column(String, default="queued")  # queued|processing|completed|failed
    queued_at = Column(DateTime, default=datetime.utcnow)
    started_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


engine = create_engine(settings.database_url)
SessionLocal = sessionmaker(bind=engine)


def init_db():
    Base.metadata.create_all(bind=engine)
