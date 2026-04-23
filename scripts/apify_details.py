# scripts/apify_details.py — Apify profile-details fetchers for discovery context
from typing import Any, Optional
from apify_client import ApifyClient

from schemas import InputContext


class EmptyDatasetError(RuntimeError):
    """Raised when Apify returns zero items — the login-wall / gone / private signal."""


def _first_or_none(items: list[dict]) -> Optional[dict]:
    return items[0] if items else None


def fetch_instagram_details(client: ApifyClient, handle: str) -> InputContext:
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

    item = _first_or_none(items)
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


def fetch_tiktok_details(client: ApifyClient, handle: str) -> InputContext:
    """Fetch TikTok profile context via clockworks/tiktok-scraper.

    We request resultsPerPage=1 and read authorMeta from that single post; the actor
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

    item = _first_or_none(items)
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
