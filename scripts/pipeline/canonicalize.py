# scripts/pipeline/canonicalize.py — URL canonicalization for classifier cache + identity index
from urllib.parse import urlparse, urlunparse, parse_qsl, urlencode
import httpx

# Query params stripped unconditionally
_TRACKING_PARAMS = {
    # Legacy (existing)
    "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
    "fbclid", "gclid", "igshid", "ref", "ref_src", "ref_url", "si",
    "mc_cid", "mc_eid", "_ga", "yclid", "msclkid",
    # NEW — observed in 2026-04-25 sensitive-content harvesting
    "igsh",       # Instagram cross-app share token (different from igshid)
    "l_",         # tapforallmylinks / launchyoursocials click-tracking token
    "s",          # twitter/x share param (?s=21, ?s=20)
    "t",          # twitter/x share token (?t=timestamp)
    "_t",         # tiktok share token
    "aff",        # generic affiliate marker
    "ref_id",     # generic affiliate variant
}

# Hosts that use known short-URL redirect patterns
_SHORT_URL_HOSTS = {
    "bit.ly", "tinyurl.com", "t.co", "goo.gl", "ow.ly",
    "geni.us", "smart.link", "lnk.to", "lnk.bio",
    "rebrand.ly", "buff.ly", "fb.me", "amzn.to",
}

# Path suffixes stripped on known platforms (social profile landing variants)
_STRIP_SUFFIXES = {
    "youtube.com": ["/about", "/home", "/featured"],
    "www.youtube.com": ["/about", "/home", "/featured"],
    "facebook.com": ["/home", "/about"],
    "www.facebook.com": ["/home", "/about"],
}


def _strip_known_suffixes(host: str, path: str) -> str:
    for suffix in _STRIP_SUFFIXES.get(host, []):
        if path.endswith(suffix):
            return path[: -len(suffix)]
    return path


def canonicalize_url(url: str) -> str:
    """Normalize a URL so equivalent destinations produce identical strings.

    Lowercases host, drops www prefix, coerces http→https, strips tracking
    query params, strips trailing slash and known platform suffixes (/about,
    /home). Idempotent. Invalid URLs return unchanged.
    """
    if "://" not in url:
        return url

    try:
        parsed = urlparse(url)
    except ValueError:
        return url

    if not parsed.hostname:
        return url

    scheme = "https"
    host = parsed.hostname.lower().removeprefix("www.")
    path = _strip_known_suffixes(host, parsed.path)
    # Lowercase path for short-URL hosts (Amazon, bit.ly, etc.) for dedup
    if host in _SHORT_URL_HOSTS:
        path = path.lower()
    if path.endswith("/") and path != "/":
        path = path.rstrip("/")

    # Preserve path casing — many platforms (IG, TT, etc.) use lowercase handles
    # but some destinations (e.g. Notion, Substack) are case-sensitive.
    query_pairs = [
        (k, v) for k, v in parse_qsl(parsed.query, keep_blank_values=True)
        if k.lower() not in _TRACKING_PARAMS
    ]
    query = urlencode(query_pairs) if query_pairs else ""

    return urlunparse((scheme, host, path, "", query, ""))


def resolve_short_url(url: str, timeout: float = 5.0) -> str:
    """Follow a short-URL redirect chain to its final destination.

    Returns the input URL unchanged if (a) the host isn't in the known short-URL
    list, or (b) the HEAD request fails. Caps at 5 redirects via httpx itself.
    """
    try:
        host = (urlparse(url).hostname or "").lower().removeprefix("www.")
    except ValueError:
        return url

    if host not in _SHORT_URL_HOSTS:
        return url

    try:
        with httpx.Client(follow_redirects=True, max_redirects=5, timeout=timeout) as client:
            resp = client.head(url)
            return str(resp.url)
    except Exception:
        return url
