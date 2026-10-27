"""Loads the toxicity model once, when the worker starts, and reuses it for every call."""
from typing import Dict, List

import torch
from transformers import pipeline

from core.config import settings

# Use the GPU if there is one (device 0), otherwise the CPU (-1).
device = 0 if torch.cuda.is_available() else -1

classifier = pipeline(
    "text-classification",
    model=settings.ml_model_name,
    device=device,
    top_k=None,  # return the score for every label, not just the best one
)


def _to_result(label_scores: List[Dict]) -> Dict:
    # The comment counts as toxic if any label scores above 0.5.
    top_score = max(r["score"] for r in label_scores)
    return {
        "prediction": "toxic" if top_score > 0.5 else "non-toxic",
        "confidence": round(top_score, 4),
        "model_version": settings.ml_model_version,
    }


def predict_batch(texts: List[str]) -> List[Dict]:
    """Classify many texts in one model call. Results come back in the same order."""
    return [_to_result(label_scores) for label_scores in classifier(texts)]
