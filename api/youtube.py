"""Pull a video's comments, score each for toxicity, and ask Groq to summarize."""
import json
import re
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from api.auth import get_current_user
from core.config import settings
from googleapiclient.discovery import build
from groq import Groq

router = APIRouter()
groq_client = Groq(api_key=settings.groq_api_key)

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

def generate_insights(comments: list, toxic_comments: list, non_toxic_comments: list) -> dict:
    sample_toxic = toxic_comments[:10]
    sample_non_toxic = non_toxic_comments[:10]

    prompt = f"""You are analyzing YouTube comments for a video.

Total comments analyzed: {len(comments)}
Toxic comments ({len(toxic_comments)}): {sample_toxic}
Non-toxic comments ({len(non_toxic_comments)} total, showing 10): {sample_non_toxic}

Respond with ONLY a valid JSON object, no markdown, no code blocks, no extra text.
Use exactly these keys:
- "summary": 2-3 sentence summary of the overall comment section
- "positive_themes": list of 3 positive themes from non-toxic comments
- "negative_themes": list of 3 negative themes from toxic comments (or [] if none)
- "improvements": list of 3 specific actionable improvements the creator can make
- "overall_sentiment": one word (Positive/Negative/Mixed)"""

    response = groq_client.chat.completions.create(
        model="openai/gpt-oss-120b",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3,
        response_format={"type": "json_object"},
    )

    try:
        return json.loads(response.choices[0].message.content)
    except Exception:
        return {
            "summary": response.choices[0].message.content,
            "positive_themes": [],
            "negative_themes": [],
            "improvements": [],
            "overall_sentiment": "Mixed"
        }


def _split_by_toxicity(comments: list, results: list) -> tuple:
    toxic = [c for c, r in zip(comments, results) if r["prediction"] == "toxic"]
    non_toxic = [c for c, r in zip(comments, results) if r["prediction"] == "non-toxic"]
    return toxic, non_toxic


def _community_rating(toxicity_rate: float) -> str:
    if toxicity_rate < 20:
        return "Healthy"
    if toxicity_rate < 50:
        return "Moderate"
    return "Toxic"


def _sentiment_label(toxicity_rate: float) -> str:
    if toxicity_rate < 10:
        return "Positive"
    if toxicity_rate < 40:
        return "Mixed"
    return "Negative"


@router.post("/analyze/youtube")
def analyze_youtube(body: YouTubeRequest, user: str = Depends(get_current_user)):
    from worker.model import predict

    video_id = extract_video_id(body.url)
    comments = fetch_comments(video_id)
    if not comments:
        raise HTTPException(status_code=404, detail="No comments found for this video")

    results = [predict(c) for c in comments]
    toxic, non_toxic = _split_by_toxicity(comments, results)
    toxicity_rate = round(len(toxic) / len(results) * 100, 1)

    insights = generate_insights(comments, toxic, non_toxic)
    insights["overall_sentiment"] = _sentiment_label(toxicity_rate)

    return {
        "video_id": video_id,
        "comments_analyzed": len(results),
        "toxic_count": len(toxic),
        "non_toxic_count": len(non_toxic),
        "toxicity_rate_percent": toxicity_rate,
        "average_confidence": round(sum(r["confidence"] for r in results) / len(results), 4),
        "community_rating": _community_rating(toxicity_rate),
        "insights": insights,
    }
