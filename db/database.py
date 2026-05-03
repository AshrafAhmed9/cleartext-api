from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from db.models import Base
from core.config import settings

engine = create_engine(settings.database_url)

SessionLocal = sessionmaker(bind=engine)

def init_db():
    # Creates the predictions table if it doesn't exist yet
    Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
