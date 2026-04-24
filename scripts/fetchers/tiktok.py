# scripts/fetchers/tiktok.py — Apify TikTok profile fetcher
from typing import Any
from apify_client import ApifyClient

from schemas import InputContext
from fetchers.base import EmptyDatasetError, first_or_none


def fetch(client: ApifyClient, handle: str) -> InputContext:
    """Fetch TikTok profile context via clockworks/tiktok-scraper.

    Requests resultsPerPage=1 and reads authorMeta from that single post; the actor
    does not expose a true profile-only mode, but authorMeta is stable across posts.
    """
    run_input: dict[str, Any] = {
        "profiles": [handle],
        "resultsPerPage": 1,
        "shouldDownloadVideos": False,
        "shouldDownloadCovers": False,
        "shouldDownloadSubtitles": False,
    }
    run = client.actor("clockworks/tiktok-scraper").call(run_input=run_input)
    items = client.dataset(run["defaultDatasetId"]).list_items().items

    item = first_or_none(items)
    if item is None:
        raise EmptyDatasetError(
            f"clockworks/tiktok-scraper returned 0 items for @{handle} — "
            f"likely a login wall, private account, or banned handle."
        )

    meta = item.get("authorMeta") or {}
    bio_link = meta.get("bioLink") or {}
    link_url = bio_link.get("link") if isinstance(bio_link, dict) else None

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
