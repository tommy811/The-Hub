# scripts/fetchers/onlyfans.py — OF public landing fetcher via curl_cffi (JA3 impersonation)
from curl_cffi import requests
from bs4 import BeautifulSoup

from schemas import InputContext
from fetchers.base import EmptyDatasetError


def _og(soup: BeautifulSoup, prop: str) -> str | None:
    tag = soup.find("meta", attrs={"property": prop})
    return tag.get("content") if tag else None


def fetch(handle: str, timeout: float = 10.0) -> InputContext:
    """Fetch OF public landing page via curl_cffi with Chrome TLS fingerprint.

    Raw httpx is blocked by OF's JA3 check. `impersonate='chrome120'` works for
    the public creator landing page (display_name, bio, avatar, links). No login
    required for this surface. Raises EmptyDatasetError on 404/error.
    """
    url = f"https://onlyfans.com/{handle}"
    try:
        resp = requests.get(url, impersonate="chrome120", timeout=timeout,
                            allow_redirects=True)
    except Exception as e:
        raise EmptyDatasetError(f"onlyfans fetch failed for {handle}: {e}")

    if resp.status_code != 200:
        raise EmptyDatasetError(f"onlyfans.com/{handle} returned HTTP {resp.status_code}")

    soup = BeautifulSoup(resp.content, "html.parser")

    return InputContext(
        handle=handle,
        platform="onlyfans",
        display_name=_og(soup, "og:title"),
        bio=_og(soup, "og:description"),
        avatar_url=_og(soup, "og:image"),
        external_urls=[url],
        source_note="onlyfans landing curl_cffi chrome120",
    )
