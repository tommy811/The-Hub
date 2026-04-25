# scripts/harvester/cache.py
"""Workspace-agnostic URL → harvested-destinations cache.

24h TTL by default. Service-role only (no RLS). Mirrors classifier_llm_guesses
pattern. Cache miss returns None; cache hit deserializes destinations into
HarvestedUrl instances.
"""
from datetime import datetime, timedelta, timezone
from typing import Optional

from harvester.types import HarvestedUrl

DEFAULT_TTL_SECONDS = 24 * 3600


def lookup_cache(sb, canonical_url: str) -> Optional[list[HarvestedUrl]]:
    """Look up a URL in url_harvest_cache. Returns None on miss or expired entry."""
    if sb is None:
        return None
    now_iso = datetime.now(timezone.utc).isoformat()
    resp = (
        sb.table("url_harvest_cache")
        .select("*")
        .eq("canonical_url", canonical_url)
        .gt("expires_at", now_iso)
        .maybe_single()
        .execute()
    )
    if resp is None:  # supabase-py 2.x: maybe_single may return None
        return None
    row = resp.data
    if not row:
        return None
    raw_destinations = row.get("destinations") or []
    return [HarvestedUrl(**d) for d in raw_destinations]


def write_cache(sb, canonical_url: str, harvest_method: str,
                destinations: list[HarvestedUrl],
                ttl_seconds: int = DEFAULT_TTL_SECONDS) -> None:
    """Upsert a harvest result into the cache. No-op if sb is None."""
    if sb is None:
        return
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(seconds=ttl_seconds)
    sb.table("url_harvest_cache").upsert({
        "canonical_url": canonical_url,
        "harvest_method": harvest_method,
        "destinations": [d.model_dump() for d in destinations],
        "harvested_at": now.isoformat(),
        "expires_at": expires_at.isoformat(),
    }).execute()
