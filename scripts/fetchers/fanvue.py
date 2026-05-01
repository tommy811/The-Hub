# scripts/fetchers/fanvue.py — Fanvue creator landing fetcher via httpx
import httpx
from bs4 import BeautifulSoup

from schemas import InputContext
from fetchers.base import EmptyDatasetError

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9",
}


def _og(soup: BeautifulSoup, prop: str) -> str | None:
    tag = soup.find("meta", attrs={"property": prop})
    return tag.get("content") if tag else None


def fetch(handle: str, timeout: float = 10.0) -> InputContext:
    url = f"https://www.fanvue.com/{handle}"
    try:
        with httpx.Client(follow_redirects=True, timeout=timeout, headers=_HEADERS) as client:
            resp = client.get(url)
    except Exception as e:
        raise EmptyDatasetError(f"fanvue fetch failed for {handle}: {e}")

    if resp.status_code != 200:
        raise EmptyDatasetError(f"fanvue.com/{handle} returned HTTP {resp.status_code}")

    soup = BeautifulSoup(resp.content, "html.parser")

    return InputContext(
        handle=handle,
        platform="fanvue",
        display_name=_og(soup, "og:title"),
        bio=_og(soup, "og:description"),
        avatar_url=_og(soup, "og:image"),
        external_urls=[url],
        source_note="fanvue landing httpx",
    )
