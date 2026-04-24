# scripts/fetchers/instagram.py — Apify IG profile fetcher
from typing import Any
from apify_client import ApifyClient

from schemas import InputContext
from fetchers.base import EmptyDatasetError, first_or_none


def fetch(client: ApifyClient, handle: str) -> InputContext:
    """Fetch IG profile context via apify/instagram-scraper in details mode.

    Raises EmptyDatasetError if the actor returns no items (login wall, banned, private).
    """
    run_input: dict[str, Any] = {
        "directUrls": [f"https://www.instagram.com/{handle}/"],
        "resultsType": "details",
        "resultsLimit": 1,
    }
    run = client.actor("apify/instagram-scraper").call(run_input=run_input)
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
