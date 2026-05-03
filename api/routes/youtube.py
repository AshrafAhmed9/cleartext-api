from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from api.auth import get_current_user
from core.config import settings
from worker.ml_model import predict
from googleapiclient.discovery import build
import re

router = APIRouter()

class YouTubeRequest(BaseModel):
    url: str

def extract_video_id(url: str) -> str:
    patterns = [
        r"v=([a-zA-Z0-9_-]{11})",
        r"youtu\.be/([a-zA-Z0-9_-]{11})",
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    raise HTTPException(status_code=400, detail="Invalid YouTube URL")

def fetch_comments(video_id: str, max_comments: int = 100) -> list:
    youtube = build("youtube", "v3", developerKey=settings.youtube_api_key)
    comments = []
    request = youtube.commentThreads().list(
        part="snippet",
        videoId=video_id,
        maxResults=min(max_comments, 100),
        textFormat="plainText"
    )
    response = request.execute()
    for item in response.get("items", []):
        text = item["snippet"]["topLevelComment"]["snippet"]["textDisplay"]
        comments.append(text)
    return comments

@router.post("/analyze/youtube")
def analyze_youtube(body: YouTubeRequest, user: str = Depends(get_current_user)):
    video_id = extract_video_id(body.url)
    comments = fetch_comments(video_id)

    if not comments:
        raise HTTPException(status_code=404, detail="No comments found for this video")

    results = [predict(c) for c in comments]

    toxic = [r for r in results if r["prediction"] == "toxic"]
    non_toxic = [r for r in results if r["prediction"] == "non-toxic"]
    avg_confidence = round(sum(r["confidence"] for r in results) / len(results), 4)
    toxicity_rate = round(len(toxic) / len(results) * 100, 1)

    if toxicity_rate < 20:
        rating = "Healthy"
    elif toxicity_rate < 50:
        rating = "Moderate"
    else:
        rating = "Toxic"

    return {
        "video_id": video_id,
        "comments_analyzed": len(results),
        "toxic_count": len(toxic),
        "non_toxic_count": len(non_toxic),
        "toxicity_rate_percent": toxicity_rate,
        "average_confidence": avg_confidence,
        "community_rating": rating,
    }
