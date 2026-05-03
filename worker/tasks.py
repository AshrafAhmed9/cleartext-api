import time
from core.celery_app import celery_app
from core.cache import set_cached
from db.database import SessionLocal
from db.models import Prediction
from worker.ml_model import predict

@celery_app.task(bind=True, max_retries=3)
def run_inference(self, task_id: str, text: str):
    try:
        start = time.time()

        result = predict(text)

        processing_time = round((time.time() - start) * 1000, 2)

        # Save to PostgreSQL
        db = SessionLocal()
        db.add(Prediction(
            request_id=task_id,
            input_text=text,
            prediction=result["prediction"],
            confidence=result["confidence"],
            processing_time_ms=processing_time,
        ))
        db.commit()
        db.close()

        # Cache the result so identical requests skip the queue
        set_cached(text, result)

        return {**result, "processing_time_ms": processing_time}

    except Exception as exc:
        # Retry with exponential backoff: 2s, 4s, 8s
        raise self.retry(exc=exc, countdown=2 ** self.request.retries)
