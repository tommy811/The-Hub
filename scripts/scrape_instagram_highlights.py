"""Import Instagram highlight stories into scraped_content.

Uses a dedicated highlights actor when --dataset-id is not provided. If a
dataset id is provided, imports that dataset without running another actor.
"""
from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID

from apify_client import ApifyClient
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parent))

from common import get_supabase  # type: ignore
from content_scraper.normalizer import NormalizedPost, PlatformMetrics


ACTOR_ID = "seemuapps/instagram-highlights-scraper"


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Scrape/import Instagram story highlights")
    parser.add_argument("--workspace-id", required=True)
    parser.add_argument("--profile-id", action="append", default=[])
    parser.add_argument("--dataset-id", help="Import an existing Apify dataset instead of running the actor")
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def _profiles(sb, workspace_id: str, profile_ids: list[str], limit: int) -> list[dict]:
    query = (
        sb.table("profiles")
        .select("id,workspace_id,creator_id,platform,handle")
        .eq("workspace_id", workspace_id)
        .eq("platform", "instagram")
        .eq("is_active", True)
        .order("created_at", desc=False)
        .limit(limit)
    )
    if profile_ids:
        query = query.in_("id", profile_ids)
    return query.execute().data or []


def _story_timestamp(value: object) -> datetime:
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value, tz=timezone.utc)
    if isinstance(value, str):
        try:
            return datetime.fromtimestamp(float(value), tz=timezone.utc)
        except ValueError:
            try:
                parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
                return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
            except ValueError:
                pass
    return datetime.now(timezone.utc)


def _normalize_item(item: dict, *, profile_id: UUID) -> list[NormalizedPost]:
    username = str(item.get("username") or "").lstrip("@")
    highlight_id = str(item.get("highlightId") or "").strip()
    title = str(item.get("title") or "").strip()
    cover_url = item.get("coverUrl")
    stories = item.get("stories") or []
    posts: list[NormalizedPost] = []

    for index, story in enumerate(stories):
        if not isinstance(story, dict):
            continue
        story_id = str(story.get("id") or f"{highlight_id}:{index}")
        image_url = story.get("imageUrl")
        video_url = story.get("videoUrl")
        media_urls = [u for u in (video_url, image_url) if isinstance(u, str) and u]
        mentions = [
            str(m).lstrip("@")
            for m in (story.get("mentions") or [])
            if isinstance(m, str) and m
        ]
        links = [
            str(link)
            for link in (story.get("links") or [])
            if isinstance(link, str) and link
        ]
        caption_parts = [p for p in (title, " ".join(links)) if p]
        caption = " | ".join(caption_parts) or None

        raw = {
            "highlight": {
                "username": username,
                "highlightId": highlight_id,
                "title": title,
                "coverUrl": cover_url,
                "mediaCount": item.get("mediaCount"),
            },
            "story": story,
        }
        posts.append(NormalizedPost(
            profile_id=profile_id,
            platform="instagram",
            platform_post_id=f"highlight:{highlight_id}:{story_id}",
            post_url=f"https://www.instagram.com/stories/highlights/{highlight_id}/",
            post_type="story_highlight",
            caption=caption,
            hook_text=caption[:50] if caption else None,
            posted_at=_story_timestamp(story.get("timestamp")),
            view_count=0,
            like_count=0,
            comment_count=0,
            share_count=None,
            save_count=None,
            is_pinned=False,
            is_sponsored=False,
            video_duration_seconds=None,
            hashtags=[],
            mentions=mentions,
            media_urls=media_urls,
            thumbnail_url=image_url if isinstance(image_url, str) else cover_url,
            platform_metrics=PlatformMetrics(product_type="instagram_highlight"),
            raw_apify_payload=raw,
        ))
    return posts


def main() -> int:
    args = _parse_args()
    load_dotenv(Path(__file__).parent / ".env")
    apify_token = os.environ.get("APIFY_TOKEN")
    if not apify_token:
        print("[err] APIFY_TOKEN missing in scripts/.env", file=sys.stderr)
        return 2

    sb = get_supabase()
    apify = ApifyClient(apify_token)
    profiles = _profiles(sb, args.workspace_id, args.profile_id, args.limit)
    if not profiles:
        print("[info] no instagram profiles in scope")
        return 0

    by_handle = {p["handle"].lower(): p for p in profiles}
    handles = list(by_handle)
    if args.dataset_id:
        dataset_id = args.dataset_id
        run_id = None
        items = list(apify.dataset(dataset_id).iterate_items())
    else:
        run = apify.actor(ACTOR_ID).call(run_input={"usernames": handles})
        run_id = run.get("id")
        dataset_id = run["defaultDatasetId"]
        items = list(apify.dataset(dataset_id).iterate_items())

    posts_by_profile: dict[str, list[NormalizedPost]] = {}
    skipped = 0
    for item in items:
        if not isinstance(item, dict):
            skipped += 1
            continue
        handle = str(item.get("username") or "").lstrip("@").lower()
        profile = by_handle.get(handle)
        if not profile:
            skipped += 1
            continue
        posts = _normalize_item(item, profile_id=UUID(profile["id"]))
        posts_by_profile.setdefault(profile["id"], []).extend(posts)

    print(
        f"[info] actor={ACTOR_ID} run_id={run_id} dataset_id={dataset_id} "
        f"highlight_records={len(items)} profiles_with_highlights={len(posts_by_profile)} "
        f"story_rows={sum(len(v) for v in posts_by_profile.values())} skipped={skipped}"
    )
    if args.dry_run:
        return 0

    total = 0
    for profile_id, posts in posts_by_profile.items():
        payload = [p.model_dump(mode="json") for p in posts]
        resp = sb.rpc("commit_scrape_result", {
            "p_profile_id": profile_id,
            "p_posts": payload,
        }).execute()
        count = int((resp.data or {}).get("posts_upserted", 0))
        total += count
        sb.table("profiles").update({
            "last_scraped_at": datetime.now(timezone.utc).isoformat(),
        }).eq("id", profile_id).eq("workspace_id", args.workspace_id).execute()
        print(f"[commit] profile_id={profile_id} story_highlights={count}")

    print(f"[done] story_highlights_upserted={total}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
