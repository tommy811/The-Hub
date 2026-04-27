"""Deterministic quality validator for scraped_content rows.

Manual v1 tool: marks obvious bad rows as suspicious/rejected using stable
rules. LLM-as-judge can later review the suspicious subset.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parent))

from common import get_supabase  # type: ignore


AUTH_WALL_RE = re.compile(r"sign in|captcha|cf-chl|access denied|log in", re.I)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate scraped_content quality flags")
    parser.add_argument("--workspace-id", required=True)
    parser.add_argument("--limit", type=int, default=500)
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def _reason_for(row: dict[str, Any]) -> tuple[str, str | None]:
    raw_text = json.dumps(row.get("raw_apify_payload") or {}, ensure_ascii=False)
    media_urls = row.get("media_urls") or []
    caption = row.get("caption")
    platform = row.get("platform")

    if not row.get("post_url"):
        return "rejected", "missing_post_url"
    if not row.get("posted_at"):
        return "rejected", "missing_posted_at"
    if AUTH_WALL_RE.search(raw_text):
        return "rejected", "auth_wall_marker"
    if platform == "tiktok" and int(row.get("view_count") or 0) == 0:
        return "suspicious", "tiktok_zero_views"
    if not caption and not media_urls and not row.get("thumbnail_url"):
        return "suspicious", "empty_caption_and_media"
    return "clean", None


def main() -> int:
    args = _parse_args()
    load_dotenv(Path(__file__).parent / ".env")
    sb = get_supabase()

    profiles = (
        sb.table("profiles")
        .select("id")
        .eq("workspace_id", args.workspace_id)
        .execute()
    ).data or []
    profile_ids = [p["id"] for p in profiles]
    if not profile_ids:
        print("[info] no profiles in workspace")
        return 0

    rows = (
        sb.table("scraped_content")
        .select(
            "id,profile_id,platform,post_url,posted_at,caption,view_count,"
            "media_urls,thumbnail_url,raw_apify_payload,quality_flag"
        )
        .in_("profile_id", profile_ids)
        .limit(args.limit)
        .execute()
    ).data or []

    changes = []
    for row in rows:
        flag, reason = _reason_for(row)
        if flag != row.get("quality_flag"):
            changes.append((row["id"], flag, reason))

    for content_id, flag, reason in changes:
        print(f"{content_id} -> {flag} ({reason or 'ok'})")
        if not args.dry_run:
            (
                sb.table("scraped_content")
                .update({"quality_flag": flag, "quality_reason": reason})
                .eq("id", content_id)
                .execute()
            )

    print(f"[done] scanned={len(rows)} changed={len(changes)} dry_run={args.dry_run}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
