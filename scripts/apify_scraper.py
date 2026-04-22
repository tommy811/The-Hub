import os
import argparse
import sys
from datetime import datetime
from dotenv import load_dotenv
from supabase import create_client, Client
from apify_client import ApifyClient
from rich.console import Console
from common import get_supabase

# scripts/apify_scraper.py — Run Apify Actor and ingest into Supabase

load_dotenv()
console = Console()

def get_apify_client() -> ApifyClient:
    token = os.environ.get("APIFY_TOKEN")
    if not token:
        raise ValueError("Missing APIFY_TOKEN in environment.")
    return ApifyClient(token)

def scrape_instagram_profile(workspace_id: str, handle: str, limit: int = 5):
    """
    Scrapes an Instagram profile using Apify and upserts it into our DB.
    Also scrapes the latest 'limit' posts.
    """
    supabase = get_supabase()
    apify = get_apify_client()
    
    # Check if profile exists
    console.print(f"[bold blue]Checking for existing profile:[/] @{handle} in workspace {workspace_id}")
    profile_response = supabase.table("profiles").select("id").eq("workspace_id", workspace_id).eq("platform", "instagram").eq("handle", handle).execute()
    
    profile_id = None
    if profile_response.data:
        profile_id = profile_response.data[0]["id"]
    else:
        console.print(f"[yellow]Profile not found. Creating a minimal profile record first.[/]")
        new_prof = supabase.table("profiles").insert({
            "workspace_id": workspace_id,
            "platform": "instagram",
            "handle": handle,
            "account_type": "social"
        }).execute()
        profile_id = new_prof.data[0]["id"]
        
    console.print(f"[bold green]Using Profile ID:[/] {profile_id}")
    
    # Prepare Apify input targeting the apify/instagram-scraper
    run_input = {
        "directUrls": [f"https://www.instagram.com/{handle}/"],
        "resultsType": "posts",
        "resultsLimit": limit,
        "addParentData": True, # Usually includes profile data in the posts
    }
    
    console.print(f"[bold blue]Starting Apify Actor (apify/instagram-scraper)...[/]")
    try:
        # Run the actor and wait for it to finish
        run = apify.actor("apify/instagram-scraper").call(run_input=run_input)
        console.print(f"[green]Actor run finished! Dataset ID:[/] {run['defaultDatasetId']}")
        
        # Fetch items from dataset
        dataset_items = apify.dataset(run["defaultDatasetId"]).list_items().items
        console.print(f"Retrieved [bold]{len(dataset_items)}[/] items from Apify.")
        
        if not dataset_items:
            console.print("[yellow]No data retrieved. Make sure the profile is public.[/]")
            return
            
        posts_to_insert = []
        profile_update = {}
        
        for item in dataset_items:
            # 1. Extract Profile stats if available (usually in the first item or parentData)
            owner = item.get("ownerProfilePicUrl")
            if owner and not profile_update:
                profile_update = {
                    "avatar_url": item.get("ownerProfilePicUrl"),
                    "display_name": item.get("ownerFullName"),
                    "follower_count": item.get("ownerFollowers"),
                    "following_count": item.get("ownerFollowing"),
                    "post_count": item.get("ownerPostsCount", 0),
                    "bio": item.get("ownerBiography"),
                    "last_scraped_at": "now()"
                }
            
            # 2. Extract Post data
            post_id = item.get("id")
            if not post_id:
                continue
                
            post_type_raw = item.get("type", "").lower()
            post_type = "image"
            if "video" in post_type_raw:
                post_type = "reel"
            elif "sidecar" in post_type_raw or "carousel" in post_type_raw:
                post_type = "carousel"
                
            caption = item.get("caption", "")
            
            # Estimate hook text (first 50 chars of caption)
            hook_text = caption[:50].strip() if caption else ""
            
            post_record = {
                "profile_id": profile_id,
                "platform": "instagram",
                "platform_post_id": post_id,
                "post_url": item.get("url"),
                "post_type": post_type,
                "caption": caption,
                "hook_text": hook_text,
                "posted_at": item.get("timestamp"),
                "view_count": item.get("videoViewCount", 0) or 0,
                "like_count": item.get("likesCount", 0) or 0,
                "comment_count": item.get("commentsCount", 0) or 0,
                "media_urls": [item.get("displayUrl")] if item.get("displayUrl") else [],
                "thumbnail_url": item.get("displayUrl"),
                "raw_apify_payload": item
            }
            posts_to_insert.append(post_record)
            
        # Execute Profile Update
        if profile_update:
             # Remove keys with None values to avoid DB null overwrites
            profile_update = {k: v for k, v in profile_update.items() if v is not None}
            if profile_update:
                console.print(f"[blue]Updating profile {handle} with latest stats...[/]")
                supabase.table("profiles").update(profile_update).eq("id", profile_id).execute()
        
        # Execute Posts Upsert
        if posts_to_insert:
            console.print(f"[blue]Upserting {len(posts_to_insert)} posts into scraped_content...[/]")
            # On conflict, we DO NOTHING or UPDATE. We can rely on upsert with unique (platform, platform_post_id)
            supabase.table("scraped_content").upsert(
                posts_to_insert, 
                on_conflict="platform,platform_post_id"
            ).execute()
            
        console.print("[bold green]Apify sync complete![/]")
        
    except Exception as e:
        console.print(f"[bold red]Error running Apify scrape:[/] {e}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Test Apify Scraper for Instagram.")
    parser.add_argument("--handle", type=str, required=True, help="Instagram handle (e.g. zuck)")
    parser.add_argument("--workspace", type=str, required=True, help="Supabase Workspace UUID")
    parser.add_argument("--limit", type=int, default=5, help="Number of posts to scrape")
    
    args = parser.parse_args()
    
    if not os.environ.get("APIFY_TOKEN"):
         console.print("[yellow]Notice: APIFY_TOKEN is missing. This script requires a real Apify Token to execute.[/]")
    if not os.environ.get("SUPABASE_URL") or not os.environ.get("SUPABASE_SERVICE_ROLE_KEY"):
         console.print("[yellow]Notice: Supabase env vars missing. Ensure .env is loaded.[/]")
         
    scrape_instagram_profile(args.workspace, args.handle, args.limit)
