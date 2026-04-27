"""Extract audio trends from scraped_content.platform_metrics.

Reads the closed-shape PlatformMetrics jsonb (`audio.signature`) captured by
content scraper v1, upserts `trends`, and links matching content rows.
"""
from __future__ import annotations

import argparse
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parent))

from common import get_supabase  # type: ignore


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Extract audio trends from scraped content")
    parser.add_argument("--workspace-id", required=True)
    parser.add_argument("--limit", type=int, default=1000)
    parser.add_argument("--min-usage", type=int, default=2)
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def _audio(row: dict[str, Any]) -> dict[str, Any] | None:
    metrics = row.get("platform_metrics") or {}
    audio = metrics.get("audio") or {}
    signature = audio.get("signature")
    if not signature:
        return None
    return {
        "signature": str(signature),
        "artist": audio.get("artist"),
        "title": audio.get("title"),
    }


def _eligible_signatures(
    by_signature: dict[str, list[dict[str, Any]]],
    *,
    min_usage: int,
) -> dict[str, list[dict[str, Any]]]:
    return {
        signature: content_rows
        for signature, content_rows in by_signature.items()
        if len(content_rows) >= min_usage
    }


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
        .select("id,profile_id,platform_metrics,trend_id,quality_flag")
        .in_("profile_id", profile_ids)
        .neq("quality_flag", "rejected")
        .limit(args.limit)
        .execute()
    ).data or []

    by_signature: dict[str, list[dict[str, Any]]] = defaultdict(list)
    audio_meta: dict[str, dict[str, Any]] = {}
    for row in rows:
        audio = _audio(row)
        if not audio:
            continue
        by_signature[audio["signature"]].append(row)
        audio_meta.setdefault(audio["signature"], audio)

    eligible = _eligible_signatures(by_signature, min_usage=args.min_usage)

    linked = 0
    for signature, content_rows in eligible.items():
        audio = audio_meta[signature]
        title = audio.get("title")
        artist = audio.get("artist")
        name = " - ".join([v for v in [artist, title] if v]) or signature
        usage_count = len(content_rows)
        print(f"{signature}: {usage_count} post(s) -> {name}")
        if args.dry_run:
            continue

        existing_res = (
            sb.table("trends")
            .select("id")
            .eq("workspace_id", args.workspace_id)
            .eq("audio_signature", signature)
            .maybe_single()
            .execute()
        )
        existing = existing_res.data if existing_res else None
        if existing:
            trend_id = existing["id"]
            (
                sb.table("trends")
                .update({
                    "name": name,
                    "audio_artist": artist,
                    "audio_title": title,
                    "usage_count": usage_count,
                })
                .eq("id", trend_id)
                .eq("workspace_id", args.workspace_id)
                .execute()
            )
        else:
            inserted = (
                sb.table("trends")
                .insert({
                    "workspace_id": args.workspace_id,
                    "name": name,
                    "trend_type": "audio",
                    "audio_signature": signature,
                    "audio_artist": artist,
                    "audio_title": title,
                    "usage_count": usage_count,
                    "is_canonical": True,
                })
                .execute()
            ).data or []
            trend_id = inserted[0]["id"]

        for row in content_rows:
            if row.get("trend_id") == trend_id:
                continue
            (
                sb.table("scraped_content")
                .update({"trend_id": trend_id})
                .eq("id", row["id"])
                .execute()
            )
            linked += 1

    print(
        f"[done] scanned={len(rows)} audio_signatures={len(by_signature)} "
        f"eligible={len(eligible)} min_usage={args.min_usage} linked={linked} dry_run={args.dry_run}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
