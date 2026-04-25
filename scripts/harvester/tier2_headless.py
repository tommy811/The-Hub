# scripts/harvester/tier2_headless.py
"""Tier 2 — Apify Puppeteer Scraper run that hooks window.open + auto-clicks
sensitive-content interstitials. Triggered only when Tier 1 trips a signal.

Cost: ~2¢ per page (1 page run on apify/puppeteer-scraper, ~5s @ ~0.5 CU).
"""
import logging
from pathlib import Path

from apify_client import ApifyClient

from common import get_apify_token
from harvester.types import HarvestedUrl
from pipeline.canonicalize import canonicalize_url

logger = logging.getLogger(__name__)

ACTOR_ID = "apify/puppeteer-scraper"
COST_CENTS = 2  # documented; actual cost varies ~1-3¢

_PAGE_FUNCTION_PATH = Path(__file__).resolve().parent / "page_function.js"


def _load_page_function() -> str:
    return _PAGE_FUNCTION_PATH.read_text()


def _build_actor_input(url: str) -> dict:
    return {
        "startUrls": [{"url": url}],
        "pageFunction": _load_page_function(),
        "maxRequestsPerCrawl": 1,
        "linkSelector": "__never_match__",
        "proxyConfiguration": {"useApifyProxy": True},
        "headless": True,
    }


def fetch_headless(url: str, apify_token: str | None = None) -> list[HarvestedUrl]:
    """Run the page function in a real browser and return harvested URLs.

    `destination_class` on each result is left as 'unknown' — the orchestrator
    runs the classifier downstream and rewrites this field per URL.
    """
    token = apify_token or get_apify_token()
    client = ApifyClient(token)

    try:
        run = client.actor(ACTOR_ID).call(
            run_input=_build_actor_input(url),
            timeout_secs=120,
        )
    except Exception as e:
        logger.warning("tier2 actor failed for url=%s: %s: %s", url, type(e).__name__, e)
        return []

    if not run or not run.get("defaultDatasetId"):
        return []

    items = client.dataset(run["defaultDatasetId"]).list_items().items
    if not items:
        return []

    raw_entries = items[0].get("urls", [])
    seen_canon: set[str] = set()
    out: list[HarvestedUrl] = []
    for e in raw_entries:
        raw_url = e.get("url", "").strip()
        if not raw_url:
            continue
        canon = canonicalize_url(raw_url)
        if canon in seen_canon:
            continue
        seen_canon.add(canon)
        out.append(HarvestedUrl(
            canonical_url=canon,
            raw_url=raw_url,
            raw_text=e.get("text", "")[:200],
            destination_class="unknown",
            harvest_method="headless",
        ))
    return out
