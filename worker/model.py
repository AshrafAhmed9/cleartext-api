"""Loads toxic-bert once at import time; every call reuses the same model."""
from typing import Dict, List
from transformers import pipeline
import torch
from core.config import settings

device = 0 if torch.cuda.is_available() else -1

classifier = pipeline(
    "text-classification",
    model=settings.ml_model_name,
    device=device,
    top_k=None,
)

MODEL_VERSION = settings.ml_model_version


def _postprocess(label_scores: List[Dict]) -> Dict:
    max_score = max(r["score"] for r in label_scores)
    is_toxic = max_score > 0.5
    return {
        "prediction": "toxic" if is_toxic else "non-toxic",
        "confidence": round(max_score, 4),
        "model_version": MODEL_VERSION,
    }


def predict(text: str) -> Dict:
    results = classifier(text)
    return _postprocess(results[0])


def predict_batch(texts: List[str]) -> List[Dict]:
    """One batched forward pass for many texts. Order is preserved."""
    results = classifier(texts)
    return [_postprocess(label_scores) for label_scores in results]


if __name__ == "__main__":
    print(predict("I hate you so much"))
    print(predict_batch(["Have a great day!", "I will destroy you"]))
