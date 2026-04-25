# scripts/harvester/orchestrator.py
"""Orchestrator: cache → Tier 1 → (Tier 2 if signals) → classify each URL → cache write.

This is the single entry point used by pipeline/resolver.py. The recursion
structure in `_classify_and_enrich` calls this with one URL at a time and
recurses on the results based on `HARVEST_CLASSES`.
"""
from harvester.cache import lookup_cache, write_cache
from harvester.types import HarvestedUrl
from harvester.tier1_static import fetch_static
from harvester.tier2_headless import fetch_headless
from pipeline.canonicalize import canonicalize_url
from pipeline.classifier import classify

# `destination_class` derived from classifier's account_type.
_DEST_CLASS_FROM_ACCOUNT_TYPE = {
    "monetization": "monetization",
    "link_in_bio": "aggregator",
    "social": "social",
    "messaging": "messaging",
}


def _destination_class_for(account_type: str) -> str:
    return _DEST_CLASS_FROM_ACCOUNT_TYPE.get(account_type, "unknown")


def harvest_urls(url: str, supabase=None) -> list[HarvestedUrl]:
    """Harvest all outbound URLs from a page. Returns classified HarvestedUrl list.

    Cascade:
      1. Cache lookup (supabase) → return immediately on hit.
      2. Tier 1 httpx + signal regex.
      3. If signals tripped → Tier 2 Apify headless harvest.
      4. Classify each URL via pipeline.classifier.classify.
      5. Persist to url_harvest_cache (24h TTL).

    `supabase=None` is supported (unit tests, offline). Cache layer skipped.
    """
    # 1. Cache layer
    cached = lookup_cache(supabase, url)
    if cached is not None:
        return cached

    # 2. Tier 1
    tier1 = fetch_static(url)

    # 3. Tier 2 escalation
    raw_entries: list[tuple[str, str]] = []  # (raw_url, raw_text)
    harvest_method = "httpx"
    if tier1.needs_tier2():
        tier2 = fetch_headless(url)
        for h in tier2:
            raw_entries.append((h.raw_url, h.raw_text))
        harvest_method = "headless"
    else:
        for anchor in tier1.anchors:
            raw_entries.append((anchor, tier1.anchor_texts.get(anchor, "")))

    # 4. Classify + canonicalize each URL
    seen_canon: set[str] = set()
    classified: list[HarvestedUrl] = []
    for raw_url, raw_text in raw_entries:
        canon = canonicalize_url(raw_url)
        if canon in seen_canon:
            continue
        seen_canon.add(canon)
        cls = classify(canon, supabase=supabase)
        classified.append(HarvestedUrl(
            canonical_url=canon,
            raw_url=raw_url,
            raw_text=raw_text,
            destination_class=_destination_class_for(cls.account_type),
            harvest_method=harvest_method,
        ))

    # 5. Persist to cache (only if we have supabase)
    if supabase is not None and classified:
        write_cache(supabase, url, harvest_method, classified)

    return classified
