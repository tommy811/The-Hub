# scripts/fetchers/generic.py — Fallback fetcher for unclassified profile-like URLs
import httpx
from bs4 import BeautifulSoup

from schemas import InputContext
from fetchers.base import EmptyDatasetError

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9",
}


def _meta(soup: BeautifulSoup, name: str) -> str | None:
    tag = soup.find("meta", attrs={"name": name})
    return tag.get("content") if tag else None


def _og(soup: BeautifulSoup, prop: str) -> str | None:
    tag = soup.find("meta", attrs={"property": prop})
    return tag.get("content") if tag else None


def fetch_url(url: str, timeout: float = 10.0) -> InputContext:
    """Generic HTML fetcher for unknown-platform profile-like URLs.

    Takes a URL directly (no handle concept). Returns platform='other'.
    Parses <title>, <meta name=description>, og:image.
    """
    try:
        with httpx.Client(follow_redirects=True, timeout=timeout, headers=_HEADERS) as client:
            resp = client.get(url)
    except Exception as e:
        raise EmptyDatasetError(f"generic fetch failed for {url}: {e}")

    if resp.status_code != 200:
        raise EmptyDatasetError(f"{url} returned HTTP {resp.status_code}")

    soup = BeautifulSoup(resp.content, "html.parser")

    title = soup.find("title")
    display_name = title.get_text(strip=True) if title else None
    bio = _meta(soup, "description") or _og(soup, "og:description")
    avatar = _og(soup, "og:image")

    return InputContext(
        handle=url,  # no notion of handle here; store the URL
        platform="other",
        display_name=display_name,
        bio=bio,
        avatar_url=avatar,
        external_urls=[url],
        source_note="generic httpx landing",
    )
