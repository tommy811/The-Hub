# scripts/fetchers/instagram.py — Apify IG profile fetcher
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
    """Wraps the Apify actor call with retry on transient proxy/challenge errors.

    Won't retry EmptyDatasetError (different message shape) or programming bugs.
    Re-raises the original exception type after 3 failed attempts.
    """
    return client.actor("apify/instagram-scraper").call(run_input=run_input)


def fetch(client: ApifyClient, handle: str) -> InputContext:
    """Fetch IG profile context via apify/instagram-scraper in details mode.

    Raises EmptyDatasetError if the actor returns no items (login wall, banned, private).
    Transient proxy/challenge failures retry up to 3x with exponential backoff.
    """
    run_input: dict[str, Any] = {
        "directUrls": [f"https://www.instagram.com/{handle}/"],
        "resultsType": "details",
        "resultsLimit": 1,
    }
    run = _call_actor(client, run_input)
    items = client.dataset(run["defaultDatasetId"]).list_items().items

    item = first_or_none(items)
    if item is None:
        raise EmptyDatasetError(
            f"apify/instagram-scraper returned 0 items for @{handle} — "
            f"likely a login wall, private account, or banned handle."
        )

    external_urls = [
        e["url"] for e in (item.get("externalUrls") or []) if e.get("url")
    ]

    return InputContext(
        handle=handle,
        platform="instagram",
        display_name=item.get("fullName"),
        bio=item.get("biography"),
        follower_count=item.get("followersCount"),
        following_count=item.get("followsCount"),
        post_count=item.get("postsCount"),
        avatar_url=item.get("profilePicUrlHD") or item.get("profilePicUrl"),
        is_verified=bool(item.get("verified", False)),
        external_urls=external_urls,
        source_note="apify/instagram-scraper details mode",
    )
