"""Refresh IG/TikTok profile avatars directly from platform profile fetchers."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parent))

from common import get_apify_client, get_supabase  # type: ignore
from fetchers.instagram import fetch as fetch_instagram_profile  # type: ignore
from fetchers.tiktok import fetch as fetch_tiktok_profile  # type: ignore


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Refresh profiles.avatar_url for IG/TikTok accounts")
    parser.add_argument("--workspace-id", required=True)
    parser.add_argument("--platform", choices=["instagram", "tiktok", "both"], default="both")
    parser.add_argument("--profile-id", action="append", default=[])
    parser.add_argument("--all", action="store_true", help="Refresh even when profiles.avatar_url is already set")
    parser.add_argument("--limit", type=int, default=100)
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    load_dotenv(Path(__file__).parent / ".env")
    sb = get_supabase()
    apify = get_apify_client()

    platforms = ["instagram", "tiktok"] if args.platform == "both" else [args.platform]
    query = (
        sb.table("profiles")
        .select("id,workspace_id,platform,handle,display_name,avatar_url")
        .eq("workspace_id", args.workspace_id)
        .eq("is_active", True)
        .in_("platform", platforms)
        .order("created_at", desc=False)
        .limit(args.limit)
    )
    if args.profile_id:
        query = query.in_("id", args.profile_id)

    profiles = query.execute().data or []
    if not args.all:
        profiles = [p for p in profiles if not p.get("avatar_url")]

    refreshed = 0
    skipped = 0
    failed = 0

    for profile in profiles:
        platform = profile["platform"]
        handle = profile["handle"]
        try:
            ctx = (
                fetch_instagram_profile(apify, handle)
                if platform == "instagram"
                else fetch_tiktok_profile(apify, handle)
            )
        except Exception as exc:
            failed += 1
            print(f"[fail] {platform} @{handle}: {exc}")
            continue

        if not ctx.avatar_url:
            skipped += 1
            print(f"[skip] {platform} @{handle}: no avatar_url returned")
            continue

        update = {
            "avatar_url": ctx.avatar_url,
            "display_name": ctx.display_name or profile.get("display_name"),
            "follower_count": ctx.follower_count,
            "following_count": ctx.following_count,
            "post_count": ctx.post_count,
        }
        update = {k: v for k, v in update.items() if v is not None}

        print(f"[avatar] {platform} @{handle}: {ctx.avatar_url}")
        if not args.dry_run:
            (
                sb.table("profiles")
                .update(update)
                .eq("id", profile["id"])
                .eq("workspace_id", args.workspace_id)
                .execute()
            )
        refreshed += 1

    print(
        f"[done] selected={len(profiles)} refreshed={refreshed} "
        f"skipped={skipped} failed={failed} dry_run={args.dry_run}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
