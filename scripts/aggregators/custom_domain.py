# scripts/aggregators/custom_domain.py — Follow redirect chains + extract outbound links
from urllib.parse import urlparse
import httpx
from bs4 import BeautifulSoup

_EXCLUDED_SCHEMES = {"mailto", "tel", "javascript"}
_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
}


def _host(url: str) -> str:
    return (urlparse(url).hostname or "").lower().removeprefix("www.")


def resolve(url: str, timeout: float = 10.0) -> list[str]:
    """Follow redirect chain from a custom-domain URL and extract all outbound HTTP links.

    Used when classifier returns (custom_domain, link_in_bio) or when a creator's
    bio links to a creator-owned redirect domain (mylink.link, hoo.be, etc.).
    Returns deduplicated outbound URLs excluding the final host's own domain.

    Returns [] on network error, 4xx/5xx, or parse failure.
    """
    try:
        with httpx.Client(follow_redirects=True, timeout=timeout,
                           max_redirects=5, headers=_HEADERS) as client:
            resp = client.get(url)
    except Exception:
        return []

    if resp.status_code != 200:
        return []

    final_host = _host(str(resp.url))
    soup = BeautifulSoup(resp.text, "html.parser")
    seen: set[str] = set()
    out: list[str] = []
    for a in soup.find_all("a", href=True):
        href: str = a["href"].strip()
        if not href or href.startswith("#"):
            continue
        scheme = urlparse(href).scheme.lower()
        if scheme in _EXCLUDED_SCHEMES or scheme not in {"http", "https"}:
            continue
        dest_host = _host(href)
        if not dest_host or dest_host == final_host:
            continue
        if href in seen:
            continue
        seen.add(href)
        out.append(href)
    return out
