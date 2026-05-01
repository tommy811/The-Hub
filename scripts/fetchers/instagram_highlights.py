# scripts/fetchers/instagram_highlights.py — Apify IG highlights fetcher (stories mode)
import logging
from typing import Any

from apify_client import ApifyClient
from tenacity import (
    retry, stop_after_attempt, wait_exponential, retry_if_exception, before_sleep_log,
)

from schemas import HighlightLink
from fetchers.base import is_transient_apify_error


_log = logging.getLogger(__name__)


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=2, min=3, max=15),
    retry=retry_if_exception(is_transient_apify_error),
    reraise=True,
    before_sleep=before_sleep_log(_log, logging.WARNING),
)
def _call_actor(client: ApifyClient, run_input: dict[str, Any]) -> dict:
    """Wraps the Apify actor call with retry on transient proxy/challenge errors.

    Mirrors fetchers/instagram.py::_call_actor exactly — same retry profile.
    """
    return client.actor("apify/instagram-scraper").call(run_input=run_input)


def _parse_link_stickers(item: dict) -> list[HighlightLink]:
    """Extract HighlightLink rows from one story-item's story_link_stickers."""
    out: list[HighlightLink] = []
    for s in (item.get("story_link_stickers") or []):
        url = (s or {}).get("url")
        if not url:
            continue
        title = (s or {}).get("link_title")
        out.append(HighlightLink(
            url=url,
            source="highlight_link_sticker",
            source_text=title,
        ))
    return out


def _parse_mentions(item: dict) -> list[HighlightLink]:
    """Extract HighlightLink rows from one story-item's mentions[]."""
    out: list[HighlightLink] = []
    for m in (item.get("mentions") or []):
        handle = (m or {}).get("username") if isinstance(m, dict) else m
        if not handle:
            continue
        out.append(HighlightLink(
            url="",
            source="highlight_caption_mention",
            platform=None,  # caller's responsibility to infer (resolver may dispatch
                            # to multiple synthesis attempts or skip if ambiguous)
            handle=str(handle).lstrip("@"),
        ))
    return out


def fetch_highlights(client: ApifyClient, handle: str) -> list[HighlightLink]:
    """Fetch IG highlights for `handle` and return surfaced URLs/mentions.

    Uses apify/instagram-scraper resultsType=stories (which Instagram's reel_media
    endpoint covers — includes pinned highlights when addParentData is True).

    Returns [] on:
    - Empty dataset (no highlights, private profile, login wall)
    - Any exception (network, schema mismatch, rate limit after retries)

    NEVER raises — a failed highlights extraction must not crash discovery.
    Same contract as run_gemini_bio_mentions.
    """
    try:
        run_input: dict[str, Any] = {
            "directUrls": [f"https://www.instagram.com/{handle}/"],
            "resultsType": "stories",
            "resultsLimit": 200,  # generous — most creators have <50 highlight items
            "addParentData": True,  # required to attribute items to parent highlight
        }
        run = _call_actor(client, run_input)
        items = client.dataset(run["defaultDatasetId"]).list_items().items or []
    except Exception as e:
        _log.warning("highlights extraction failed for @%s: %s", handle, e)
        return []

    seen_urls: set[str] = set()
    seen_mentions: set[str] = set()
    out: list[HighlightLink] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        for link in _parse_link_stickers(item):
            if link.url in seen_urls:
                continue
            seen_urls.add(link.url)
            out.append(link)
        for link in _parse_mentions(item):
            key = f"{link.platform}|{link.handle}"
            if key in seen_mentions:
                continue
            seen_mentions.add(key)
            out.append(link)
    return out
