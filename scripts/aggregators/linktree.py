# scripts/aggregators/linktree.py — Resolve linktr.ee pages to outbound destinations
from urllib.parse import urlparse
import httpx
from bs4 import BeautifulSoup

_HOSTS = {"linktr.ee"}
_EXCLUDED_SCHEMES = {"mailto", "tel", "javascript"}


def _host(url: str) -> str:
    return (urlparse(url).hostname or "").lower().removeprefix("www.")


def is_linktree(url: str) -> bool:
    return _host(url) in _HOSTS


def resolve(url: str, timeout: float = 10.0) -> list[str]:
    """Fetch a linktr.ee URL and return deduplicated outbound destination URLs.

    Returns [] on non-linktree URL, HTTP errors, or parse failures. Excludes
    the aggregator's own domain and sub-pages (/help, /legal). Excludes
    mailto/tel/javascript schemes.
    """
    if not is_linktree(url):
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
        if scheme in _EXCLUDED_SCHEMES or scheme not in {"http", "https"}:
            continue
        dest_host = _host(href)
        if not dest_host or dest_host == source_host or dest_host.endswith(source_host):
            continue
        if href in seen:
            continue
        seen.add(href)
        out.append(href)
    return out
