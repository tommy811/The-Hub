# scripts/fetchers/tiktok.py — Apify TikTok profile fetcher
from typing import Any
from apify_client import ApifyClient
from tenacity import (
    retry, stop_after_attempt, wait_exponential, retry_if_exception, before_sleep_log,
)
import logging

from schemas import InputContext
from fetchers.base import EmptyDatasetError, first_or_none, is_transient_apify_error


_log = logging.getLogger(__name__)


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=2, min=3, max=15),
    retry=retry_if_exception(is_transient_apify_error),
    reraise=True,
    before_sleep=before_sleep_log(_log, logging.WARNING),
)
def _call_actor(client: ApifyClient, run_input: dict[str, Any]) -> dict:
    return client.actor("clockworks/tiktok-scraper").call(run_input=run_input)


def fetch(client: ApifyClient, handle: str) -> InputContext:
    """Fetch TikTok profile context via clockworks/tiktok-scraper.

    Requests resultsPerPage=1 and reads authorMeta from that single post; the actor
    does not expose a true profile-only mode, but authorMeta is stable across posts.
    Transient proxy/challenge failures retry up to 3x with exponential backoff.
    """
    run_input: dict[str, Any] = {
        "profiles": [handle],
        "resultsPerPage": 1,
        "shouldDownloadVideos": False,
        "shouldDownloadCovers": False,
        "shouldDownloadSubtitles": False,
    }
    run = _call_actor(client, run_input)
    items = client.dataset(run["defaultDatasetId"]).list_items().items

    item = first_or_none(items)
    if item is None:
        raise EmptyDatasetError(
            f"clockworks/tiktok-scraper returned 0 items for @{handle} — "
            f"likely a login wall, private account, or banned handle."
        )

    meta = item.get("authorMeta") or {}
    # clockworks/tiktok-scraper's bioLink shape changed from {"link": "<url>"}
    # to a plain string. Handle both — newer string shape first, dict for
    # legacy/rollback safety. Either empty form yields no link.
    bio_link_raw = meta.get("bioLink")
    if isinstance(bio_link_raw, str):
        link_url = bio_link_raw or None
    elif isinstance(bio_link_raw, dict):
        link_url = bio_link_raw.get("link") or None
    else:
        link_url = None

    external_urls: list[str] = []
    if link_url:
        external_urls.append(link_url)

    return InputContext(
        handle=handle,
        platform="tiktok",
        display_name=meta.get("nickName") or meta.get("name"),
        bio=meta.get("signature"),
        follower_count=meta.get("fans"),
        following_count=meta.get("following"),
        post_count=meta.get("video"),
        avatar_url=meta.get("avatar"),
        is_verified=bool(meta.get("verified", False)),
        external_urls=external_urls,
        source_note="clockworks/tiktok-scraper",
    )
