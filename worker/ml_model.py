from transformers import pipeline
import torch

# Load the model once when this file is imported.
# Loading takes ~5 seconds — we never want to do it per request.
device = 0 if torch.cuda.is_available() else -1  # 0 = GPU, -1 = CPU

classifier = pipeline(
    "text-classification",
    model="unitary/toxic-bert",
    device=device,
    top_k=None  # return scores for ALL labels, not just the top one
)

def predict(text: str) -> dict:
    results = classifier(text)  # returns list of {label, score} dicts

    # toxic-bert has 6 labels: toxic, severe_toxic, obscene, threat, insult, identity_hate
    # We take the max score across all labels as the overall toxicity confidence
    max_score = max(r["score"] for r in results[0])
    is_toxic = max_score > 0.5

    return {
        "prediction": "toxic" if is_toxic else "non-toxic",
        "confidence": round(max_score, 4)
    }


# Quick test when you run this file directly
if __name__ == "__main__":
    print(predict("I hate you so much"))
    print(predict("Have a great day!"))
