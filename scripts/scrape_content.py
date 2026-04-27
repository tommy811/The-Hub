"""Manual-trigger CLI for the content scraper.

Resolves a target set of (creator, profile) pairs from one of three
mutually exclusive input modes (--creator-id / --tracking-type / --profile-id),
then dispatches the orchestrator.

Spec: docs/superpowers/specs/2026-04-27-content-scraper-v1-design.md §4
"""
from __future__ import annotations
import argparse
import asyncio
import logging
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from dotenv import load_dotenv
from apify_client import ApifyClient

# Make scripts/ importable
sys.path.insert(0, str(Path(__file__).resolve().parent))

from common import get_supabase  # type: ignore
from content_scraper.fetchers.instagram import InstagramContentFetcher
from content_scraper.fetchers.tiktok import TikTokContentFetcher
from content_scraper.orchestrator import ScrapeOrchestrator, ProfileScope


DEAD_LETTER_PATH = str(Path(__file__).parent / "content_scraper_dead_letter.jsonl")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Manual-trigger content scraper (IG + TT)")
    parser.add_argument("--workspace-id", required=True)
    sel = parser.add_mutually_exclusive_group(required=True)
    sel.add_argument("--creator-id", action="append", default=[])
    sel.add_argument("--tracking-type")
    sel.add_argument("--profile-id", action="append", default=[])
    parser.add_argument("--limit-days", type=int, default=30)
    parser.add_argument("--platform", choices=["ig", "tt", "both"], default="both")
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def _resolve_scopes(sb, args: argparse.Namespace) -> list[ProfileScope]:
    """Resolve the (creator_id, profile_id, handle, platform) tuples to scrape."""
    workspace_id = args.workspace_id

    if args.profile_id:
        rows = (
            sb.table("profiles")
            .select("id,handle,platform,creator_id,is_active,workspace_id")
            .in_("id", args.profile_id)
            .eq("workspace_id", workspace_id)
            .eq("is_active", True)
            .execute()
        ).data or []
    else:
        if args.creator_id:
            creator_ids = args.creator_id
        else:
            cr = (
                sb.table("creators")
                .select("id")
                .eq("workspace_id", workspace_id)
                .eq("tracking_type", args.tracking_type)
                .execute()
            ).data or []
            creator_ids = [c["id"] for c in cr]
            if not creator_ids:
                print(f"[warn] no creators found with tracking_type={args.tracking_type!r}",
                      file=sys.stderr)
                return []

        rows = (
            sb.table("profiles")
            .select("id,handle,platform,creator_id,is_active,workspace_id")
            .in_("creator_id", creator_ids)
            .eq("workspace_id", workspace_id)
            .eq("is_active", True)
            .in_("platform", ["instagram", "tiktok"])
            .execute()
        ).data or []

    plat_filter = {"ig": {"instagram"}, "tt": {"tiktok"}, "both": {"instagram", "tiktok"}}[args.platform]
    scopes = []
    for r in rows:
        if r["platform"] not in plat_filter:
            continue
        scopes.append(ProfileScope(
            profile_id=r["id"],
            handle=r["handle"],
            platform=r["platform"],
            creator_id=r["creator_id"],
        ))
    return scopes


async def _run(args: argparse.Namespace) -> int:
    load_dotenv(Path(__file__).parent / ".env")
    apify_token = os.environ.get("APIFY_TOKEN")
    if not apify_token:
        print("[err] APIFY_TOKEN missing in scripts/.env", file=sys.stderr)
        return 2

    sb = get_supabase()
    scopes = _resolve_scopes(sb, args)
    if not scopes:
        print("[info] no profiles in scope; exiting")
        return 0

    print(f"[info] resolved {len(scopes)} profile(s) across {len({s.creator_id for s in scopes})} creator(s)")
    for s in scopes:
        print(f"  - {s.platform:9s} @{s.handle}  profile_id={s.profile_id}  creator_id={s.creator_id}")

    if args.dry_run:
        print("[info] --dry-run: exiting before Apify call")
        return 0

    apify = ApifyClient(apify_token)
    orch = ScrapeOrchestrator(
        supabase=sb,
        ig_fetcher=InstagramContentFetcher(apify_client=apify),
        tt_fetcher=TikTokContentFetcher(apify_client=apify),
        dead_letter_path=DEAD_LETTER_PATH,
    )
    since = datetime.now(timezone.utc) - timedelta(days=args.limit_days)
    summary = await orch.run(scopes, since=since)

    print(f"[done] profiles_scraped={summary.profiles_scraped} "
          f"profiles_skipped={summary.profiles_skipped} "
          f"posts_upserted={summary.posts_upserted} "
          f"outliers_flagged={summary.outliers_flagged} "
          f"failures={summary.failures}")
    return 0 if summary.failures == 0 else 1


def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    args = _parse_args()
    return asyncio.run(_run(args))


if __name__ == "__main__":
    sys.exit(main())
