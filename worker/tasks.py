import time
from datetime import datetime
from core.celery_app import celery_app
from core.cache import set_cached
from db.database import SessionLocal
from db.models import Prediction
from worker.ml_model import predict

@celery_app.task(bind=True, max_retries=3)
def run_inference(self, task_id: str, text: str):
    db = SessionLocal()
    try:
        # Mark as processing and record when worker picked up the task
        row = db.query(Prediction).filter(Prediction.request_id == task_id).first()
        if row:
            row.status = "processing"
            row.started_at = datetime.utcnow()
            db.commit()

        start = time.time()
        result = predict(text)
        processing_time = round((time.time() - start) * 1000, 2)

        if row:
            row.prediction = result["prediction"]
            row.confidence = result["confidence"]
            row.processing_time_ms = processing_time
            row.status = "completed"
            db.commit()
        else:
            # Row doesn't exist yet — create it
            db.add(Prediction(
                request_id=task_id,
                input_text=text,
                prediction=result["prediction"],
                confidence=result["confidence"],
                processing_time_ms=processing_time,
                status="completed",
                started_at=datetime.utcnow(),
            ))
            db.commit()

        set_cached(text, result)
        return {**result, "processing_time_ms": processing_time}

    except Exception as exc:
        if self.request.retries >= self.max_retries:
            # Poison job: max retries exhausted, mark as permanently failed
            row = db.query(Prediction).filter(Prediction.request_id == task_id).first()
            if row:
                row.status = "failed"
                db.commit()
            db.close()
            raise

        db.close()
        # Exponential backoff: 2s, 4s, 8s
        raise self.retry(exc=exc, countdown=2 ** self.request.retries)

    finally:
        db.close()
