import json
import re
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from api.auth import get_current_user
from core.config import settings
from worker.ml_model import predict
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
        model="llama-3.3-70b-versatile",
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


@router.post("/analyze/youtube")
def analyze_youtube(body: YouTubeRequest, user: str = Depends(get_current_user)):
    video_id = extract_video_id(body.url)
    comments = fetch_comments(video_id)

    if not comments:
        raise HTTPException(status_code=404, detail="No comments found for this video")

    results = [predict(c) for c in comments]

    toxic = [comments[i] for i, r in enumerate(results) if r["prediction"] == "toxic"]
    non_toxic = [comments[i] for i, r in enumerate(results) if r["prediction"] == "non-toxic"]
    avg_confidence = round(sum(r["confidence"] for r in results) / len(results), 4)
    toxicity_rate = round(len(toxic) / len(results) * 100, 1)

    if toxicity_rate < 20:
        rating = "Healthy"
    elif toxicity_rate < 50:
        rating = "Moderate"
    else:
        rating = "Toxic"

    insights = generate_insights(comments, toxic, non_toxic)

    if toxicity_rate < 10:
        insights["overall_sentiment"] = "Positive"
    elif toxicity_rate < 40:
        insights["overall_sentiment"] = "Mixed"
    else:
        insights["overall_sentiment"] = "Negative"

    return {
        "video_id": video_id,
        "comments_analyzed": len(results),
        "toxic_count": len(toxic),
        "non_toxic_count": len(non_toxic),
        "toxicity_rate_percent": toxicity_rate,
        "average_confidence": avg_confidence,
        "community_rating": rating,
        "insights": insights,
    }
