# scripts/link_in_bio.py — Resolve Linktree/Beacons pages to destination URLs
from urllib.parse import urlparse
import httpx
from bs4 import BeautifulSoup

_AGGREGATOR_DOMAINS = {
    "linktr.ee",
    "beacons.ai",
    "beacons.page",
}

_EXCLUDED_SCHEMES = {"mailto", "tel", "javascript"}


def is_aggregator_url(url: str) -> bool:
    try:
        host = urlparse(url).hostname or ""
    except ValueError:
        return False
    host = host.lower().removeprefix("www.")
    return host in _AGGREGATOR_DOMAINS


def _host(url: str) -> str:
    return (urlparse(url).hostname or "").lower().removeprefix("www.")


def resolve_link_in_bio(url: str, timeout: float = 10.0) -> list[str]:
    """Fetch an aggregator URL (Linktree/Beacons) and return outbound destination URLs.

    Returns [] on non-aggregator URLs, HTTP errors, or parse failures. Destinations are
    deduplicated, exclude the aggregator's own domain, and exclude mailto/tel/javascript.
    """
    if not is_aggregator_url(url):
        return []

    try:
        r = httpx.get(url, timeout=timeout, follow_redirects=True)
        r.raise_for_status()
    except Exception:
        return []

    source_host = _host(url)
    soup = BeautifulSoup(r.text, "html.parser")

    seen: set[str] = set()
    out: list[str] = []
    for a in soup.find_all("a", href=True):
        href: str = a["href"].strip()
        if not href or href.startswith("#"):
            continue
        scheme = urlparse(href).scheme.lower()
        if scheme in _EXCLUDED_SCHEMES:
            continue
        if scheme not in {"http", "https"}:
            continue
        dest_host = _host(href)
        if not dest_host or dest_host == source_host:
            continue
        # Also skip aggregator helper domains (help.linktr.ee, www.beacons.ai/legal etc)
        if dest_host.endswith(source_host):
            continue
        if href in seen:
            continue
        seen.add(href)
        out.append(href)

    return out
