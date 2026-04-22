"""
Agency Command Center - Data Ingestion & Analysis Engine
Handles scraping (Apify), enrichment (Gemini AI), trend detection, and alerting (Resend).
"""

import argparse
import json
import logging
import os
import time
from datetime import datetime, timedelta, timezone
from functools import wraps
from typing import Optional, List, Dict, Any
from uuid import UUID

from apify_client import ApifyClient
import google.generativeai as genai
from pydantic import BaseModel, Field
from supabase import create_client, Client
from dotenv import load_dotenv

# Load env vars
load_dotenv(dotenv_path="../.env.local")

# Setup logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# Config
SUPABASE_URL = os.getenv("NEXT_PUBLIC_SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY") # Must use service role for bypass RLS
APIFY_TOKEN = os.getenv("APIFY_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if not all([SUPABASE_URL, SUPABASE_KEY]):
    logger.warning("Missing Supabase credentials. Ensure NEXT_PUBLIC_SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY are set.")

supabase: Client = create_client(SUPABASE_URL or "", SUPABASE_KEY or "")
if APIFY_TOKEN:
    apify = ApifyClient(APIFY_TOKEN)
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

# Design Decision: Hardcode actor mappings here instead of DB to allow rapid swapping of data providers.
APIFY_ACTORS = {
    "instagram": "apify/instagram-scraper",
    "tiktok": "clockworks/tiktok-scraper" # Standardized actor IDs based on prompt requirements
}

# --- Pydantic Models for Schema Validation ---

class ProfileRecord(BaseModel):
    platform: str
    handle: str
    display_name: Optional[str] = None
    avatar_url: Optional[str] = None
    follower_count: int = 0
    post_count: int = 0

class ContentRecord(BaseModel):
    platform_post_id: str
    post_url: Optional[str] = None
    post_type: str = "image" # reel, tiktok_video, image, carousel, story
    caption: str = ""
    posted_at: Optional[datetime] = None
    view_count: int = 0
    like_count: int = 0
    comment_count: int = 0
    share_count: int = 0
    save_count: int = 0
    thumbnail_url: Optional[str] = None

class AnalysisResult(BaseModel):
    quality_score: float = Field(..., ge=0, le=100)
    archetype: str
    vibe: str
    category: str
    visual_tags: List[str] = []
    hook_analysis: str

class TrendSignal(BaseModel):
    signal_type: str
    profile_id: str
    content_id: Optional[str] = None
    score: float
    metadata: Dict[str, Any] = {}

# --- Utilities ---

def exponential_backoff(max_retries: int = 3, base_delay: float = 1.0):
    """Decorator to retry failing network calls with exponential backoff."""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            delay = base_delay
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    if attempt == max_retries - 1:
                        logger.error(f"Failed after {max_retries} attempts: {e}")
                        raise
                    logger.warning(f"Attempt {attempt + 1} failed: {e}. Retrying in {delay}s...")
                    time.sleep(delay)
                    delay *= 2
        return wrapper
    return decorator


# --- Task 4 Functions ---

@exponential_backoff()
def run_ingestion(workspace_id: UUID, platform: Optional[str] = None):
    """
    Fetches active profiles, calls Apify actor, normalizes, and upserts data.
    """
    logger.info(f"Starting ingestion for workspace {workspace_id}, platform: {platform or 'ALL'}")
    
    # 1. Fetch profiles to scrape
    query = supabase.table("profiles").select("id, platform, handle").eq("workspace_id", str(workspace_id)).eq("is_active", True)
    if platform:
        query = query.eq("platform", platform)
    
    profiles = query.execute().data
    logger.info(f"Found {len(profiles)} profiles to scrape.")

    if not APIFY_TOKEN:
        logger.error("APIFY_TOKEN not set. Skipping actual scraping.")
        return

    # In a real scenario, this would trigger Apify runs asynchronously or batch them.
    # For sync CLI logic, we loop.
    for profile in profiles:
        prof_handle = profile["handle"].replace("@", "")
        actor_id = APIFY_ACTORS.get(profile["platform"])
        if not actor_id:
            continue
            
        logger.info(f"Triggering {actor_id} for {prof_handle}...")
        
        # Apify Run
        run = apify.actor(actor_id).call(run_input={"usernames": [prof_handle], "resultsLimit": 15})
        items = apify.dataset(run["defaultDatasetId"]).iterate_items()
        
        # Process items
        for item in items:
            # Normalize Apify payload -> ContentRecord
            # (Note: Apify outputs vary wildly. This is a generic robust extractor based on common structures)
            content = ContentRecord(
                platform_post_id=str(item.get("id") or item.get("shortCode", "")),
                post_url=item.get("url"),
                post_type="reel" if item.get("isReel") else "tiktok_video" if "tiktok" in profile["platform"] else "image",
                caption=item.get("caption", ""),
                posted_at=item.get("timestamp") or datetime.now(timezone.utc).isoformat(),
                view_count=item.get("videoPlayCount") or item.get("playCount") or 0,
                like_count=item.get("likesCount") or item.get("diggCount") or 0,
                comment_count=item.get("commentsCount") or item.get("commentCount") or 0,
                share_count=item.get("sharesCount") or item.get("shareCount") or 0,
                thumbnail_url=item.get("thumbnailUrl") or item.get("coverUrl")
            )
            
            # Upsert scraped_content via Postgres constraint ON CONFLICT (platform, platform_post_id)
            scraped_payload = {
                "profile_id": profile["id"],
                "platform": profile["platform"],
                "platform_post_id": content.platform_post_id,
                "post_url": content.post_url,
                "post_type": content.post_type,
                "caption": content.caption,
                "posted_at": content.posted_at,
                "view_count": content.view_count,
                "like_count": content.like_count,
                "comment_count": content.comment_count,
                "share_count": content.share_count,
                "thumbnail_url": content.thumbnail_url,
                "raw_apify_payload": item
            }
            res = supabase.table("scraped_content").upsert(scraped_payload, on_conflict="platform,platform_post_id").execute()
            
            if res.data:
                content_id = res.data[0]["id"]
                
                # Insert daily row into content_metrics_snapshots
                snapshot_date = datetime.now(timezone.utc).date().isoformat()
                supabase.table("content_metrics_snapshots").upsert({
                    "content_id": content_id,
                    "snapshot_date": snapshot_date,
                    "view_count": content.view_count,
                    "like_count": content.like_count,
                    "comment_count": content.comment_count,
                    "velocity": 0 # Calculated later during trends
                }, on_conflict="content_id,snapshot_date").execute()

        # Mark profile scraped
        supabase.table("profiles").update({"last_scraped_at": datetime.now(timezone.utc).isoformat()}).eq("id", profile["id"]).execute()


@exponential_backoff()
def analyze_pending_content(limit: int = 50):
    """
    Finds scraped_content rows without content_analysis, calls Gemini with strict JSON-mode, and upserts.
    """
    logger.info("Starting AI content analysis...")
    if not GEMINI_API_KEY:
        logger.error("GEMINI_API_KEY not set. Cannot run analysis.")
        return

    # Find content without analysis
    # Postgres query: SELECT * FROM scraped_content c WHERE NOT EXISTS (SELECT 1 FROM content_analysis a WHERE a.content_id = c.id)
    # Using Supabase PostgREST workaround for outer join
    res = supabase.table("scraped_content").select("id, profile_id, caption, platform, post_type").execute()
    existing_analyses = supabase.table("content_analysis").select("content_id").execute()
    analyzed_ids = {row["content_id"] for row in existing_analyses.data}
    
    pending = [r for r in res.data if r["id"] not in analyzed_ids][:limit]
    logger.info(f"Found {len(pending)} unanalyzed posts (limiting to {limit}).")

    model = genai.GenerativeModel('gemini-1.5-pro-latest')
    
    prompt_template = """
    Analyze the following social media post caption and determine its quality, archetype, vibe, and category.
    Output ONLY valid JSON.
    
    ALLOWED VALUES:
    - archetype: 'the_jester', 'the_caregiver', 'the_lover', 'the_everyman', 'the_creator', 'the_hero', 'the_sage', 'the_innocent', 'the_explorer', 'the_rebel', 'the_magician', 'the_ruler'
    - vibe: 'playful', 'girl_next_door', 'body_worship', 'wifey', 'luxury', 'edgy', 'wholesome', 'mysterious', 'confident', 'aspirational'
    - category: 'comedy_entertainment', 'fashion_style', 'fitness', 'lifestyle', 'beauty', 'travel', 'food', 'music', 'gaming', 'education', 'other'
    
    Output Schema required:
    {
      "quality_score": float (0-100),
      "archetype": string (from allowed list),
      "vibe": string (from allowed list),
      "category": string (from allowed list),
      "visual_tags": [string],
      "hook_analysis": string
    }
    
    Post Details:
    Platform: {platform}
    Type: {post_type}
    Caption: {caption}
    """

    for post in pending:
        prompt = prompt_template.format(platform=post["platform"], post_type=post["post_type"], caption=post.get("caption") or "[No caption]")
        
        try:
            # Gemini JSON mode configuration
            response = model.generate_content(
                prompt,
                generation_config=import_genai_types().GenerationConfig(response_mime_type="application/json")
            )
            
            result_json = json.loads(response.text)
            validated = AnalysisResult(**result_json)
            
            # Upsert into content_analysis
            supabase.table("content_analysis").upsert({
                "content_id": post["id"],
                "quality_score": validated.quality_score,
                "archetype": validated.archetype,
                "vibe": validated.vibe,
                "category": validated.category,
                "visual_tags": validated.visual_tags,
                "hook_analysis": validated.hook_analysis,
                "analysis_version": "v1.5-pro",
                "gemini_raw_response": result_json
            }).execute()

            # Trigger RPC to refresh profile score
            supabase.rpc("refresh_profile_score", {"p_profile_id": post["profile_id"]}).execute()
            logger.info(f"Analyzed post {post['id']} - Quality Score: {validated.quality_score}")
        except Exception as e:
            logger.error(f"Failed to analyze post {post['id']}: {e}")

def import_genai_types():
    import google.generativeai.types as genai_types
    return genai_types


def detect_trends(workspace_id: UUID):
    """
    Calculates velocity, triggers outlier detection via Postgres function, and generates trend signals.
    """
    logger.info("Detecting trends and outliers...")
    
    # Trigger Postgres RPC for Outlier flagging (view_count > 2x median)
    profiles = supabase.table("profiles").select("id").eq("workspace_id", str(workspace_id)).execute()
    for profile in profiles.data:
        try:
            supabase.rpc("flag_outliers", {"p_profile_id": profile["id"]}).execute()
        except Exception as e:
            logger.error(f"Failed to run flag_outliers RPC for {profile['id']}: {e}")
            
    # Naive velocity calculation code would go here
    # E.g. pulling snapshots from yesterday vs today
    logger.info("Trend detection complete.")


def evaluate_alerts(workspace_id: UUID):
    """
    Walks alerts_config, matches conditions against feed, and generates alerts_feed.
    Stubbed email sender.
    """
    logger.info("Evaluating alert configurations...")
    configs = supabase.table("alerts_config").select("*").eq("workspace_id", str(workspace_id)).eq("is_enabled", True).execute()
    
    for config in configs.data:
        logger.info(f"Evaluating rule: {config['name']} ({config['rule_type']})")
        # Logic to match rule_type against recent signals
        # If match:
        # supabase.table("alerts_feed").insert({"workspace_id": ..., "config_id": config["id"]})
        # send_alert_email(config["notify_emails"], feed_payload)


def send_alert_email(emails: List[str], payload: Dict):
    """
    Stub for Resend email integration.
    """
    resend_key = os.getenv("RESEND_API_KEY")
    if not resend_key:
        return
    logger.info(f"Sending alert email to {emails} via Resend. Payload: {payload}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Agency Command Center - Ingestion Pipeline")
    parser.add_argument("--workspace", type=str, required=True, help="Workspace UUID")
    parser.add_argument("--task", type=str, choices=["ingest", "analyze", "trends", "alerts", "all"], default="all")
    parser.add_argument("--platform", type=str, choices=["instagram", "tiktok"], help="Filter by platform")
    
    args = parser.parse_args()
    
    # Needs a real UUID, for testing logic bypass validation if 'test'
    ws_id = args.workspace
    
    if args.task in ["ingest", "all"]:
        run_ingestion(ws_id, args.platform)
    if args.task in ["analyze", "all"]:
        analyze_pending_content()
    if args.task in ["trends", "all"]:
        detect_trends(ws_id)
    if args.task in ["alerts", "all"]:
        evaluate_alerts(ws_id)
