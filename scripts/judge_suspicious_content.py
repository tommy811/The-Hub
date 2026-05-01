"""LLM-as-judge for rows flagged suspicious by deterministic validators."""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Literal

from dotenv import load_dotenv
from pydantic import BaseModel, ValidationError

sys.path.insert(0, str(Path(__file__).resolve().parent))

from common import get_supabase  # type: ignore


class JudgeDecision(BaseModel):
    quality_flag: Literal["clean", "rejected"]
    quality_reason: str


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Judge suspicious scraped_content rows with Gemini")
    parser.add_argument("--workspace-id", required=True)
    parser.add_argument("--limit", type=int, default=50)
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def _parse_decision(text: str) -> JudgeDecision:
    raw = text.strip()
    if raw.startswith("```"):
        raw = raw.strip("`")
        raw = raw.removeprefix("json").strip()
    return JudgeDecision.model_validate_json(raw)


def _prompt(row: dict[str, Any]) -> str:
    payload = {
        "platform": row.get("platform"),
        "post_url": row.get("post_url"),
        "caption": row.get("caption"),
        "posted_at": row.get("posted_at"),
        "view_count": row.get("view_count"),
        "quality_reason": row.get("quality_reason"),
        "raw_sample": row.get("raw_apify_payload"),
    }
    return (
        "You are judging whether a scraped social post row is usable. "
        "Return only JSON: {\"quality_flag\":\"clean|rejected\",\"quality_reason\":\"short_snake_case_reason\"}. "
        "Choose rejected only for login walls, captchas, malformed rows, non-post pages, or unusable data. "
        f"Row: {json.dumps(payload, ensure_ascii=False)[:12000]}"
    )


def main() -> int:
    args = _parse_args()
    load_dotenv(Path(__file__).parent / ".env")
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("[err] GEMINI_API_KEY missing in scripts/.env", file=sys.stderr)
        return 2

    import google.generativeai as genai

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(os.environ.get("GEMINI_JUDGE_MODEL", "gemini-2.5-flash"))
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
        .select("id,profile_id,platform,post_url,caption,posted_at,view_count,raw_apify_payload,quality_reason")
        .in_("profile_id", profile_ids)
        .eq("quality_flag", "suspicious")
        .limit(args.limit)
        .execute()
    ).data or []

    changed = 0
    for row in rows:
        try:
            response = model.generate_content(_prompt(row))
            decision = _parse_decision(response.text)
        except (ValidationError, ValueError) as exc:
            print(f"[warn] judge_parse_failed id={row['id']} err={exc}")
            continue

        print(f"{row['id']} -> {decision.quality_flag} ({decision.quality_reason})")
        if not args.dry_run:
            (
                sb.table("scraped_content")
                .update(decision.model_dump())
                .eq("id", row["id"])
                .execute()
            )
        changed += 1

    print(f"[done] judged={len(rows)} changed={changed} dry_run={args.dry_run}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
