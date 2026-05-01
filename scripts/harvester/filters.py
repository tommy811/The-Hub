"""URL filters for the universal harvester.

Drops destinations that are known not to be creator-owned content:
- Internal API / service endpoints (api.*, *-service.*, auth-*, etc.)
- CDN / static assets (*.cloudfront.net, cdn.*, *.page.link)
- Legal / footer pages (/terms, /privacy, /legal, ...)
- Empty-path URLs (homepages aren't destinations)

Used by harvester.orchestrator before persistence.
"""
import re
from urllib.parse import urlparse

# Hosts (or host patterns) we never want to surface as creator destinations.
# Either an exact suffix match (host endswith) or a regex on the full host.
_NOISE_HOST_REGEXES = [
    # Generic internal APIs
    re.compile(r"^api\.", re.I),
    re.compile(r"\.api\.", re.I),
    re.compile(r"-api\.", re.I),
    re.compile(r"^api-", re.I),
    re.compile(r"-service\.", re.I),
    re.compile(r"^auth(-|\.)", re.I),
    re.compile(r"^config\.", re.I),
    re.compile(r"^cdn\.", re.I),
    re.compile(r"^assets\.", re.I),
    re.compile(r"^static\.", re.I),
    re.compile(r"^media\.", re.I),
    re.compile(r"^worker\.", re.I),
    re.compile(r"\.worker\.", re.I),
    re.compile(r"^agent\.", re.I),
    re.compile(r"^stripe-", re.I),
    re.compile(r"^email-", re.I),
    re.compile(r"^ads-", re.I),
    re.compile(r"^engagement-", re.I),
    re.compile(r"^chat-", re.I),
    re.compile(r"^commerce-", re.I),
    re.compile(r"^common-", re.I),
    re.compile(r"^user-", re.I),
    re.compile(r"^external-", re.I),
    re.compile(r"^ig-compliance\.", re.I),
    re.compile(r"^ap-api\.", re.I),
    # CDN / Firebase
    re.compile(r"\.cloudfront\.net$", re.I),
    re.compile(r"\.page\.link$", re.I),
    re.compile(r"^cloudfront\.net$", re.I),
]

# Path prefixes for legal / footer / system pages that aren't creator destinations.
_NOISE_PATH_PREFIXES = (
    "/terms",
    "/privacy",
    "/privacypolicy",
    "/privacy-policy",
    "/termsandconditions",
    "/terms-of-service",
    "/legal",
    "/contact",
    "/help",
    "/faq",
    "/imprint",
    "/cookies",
    "/cookie-policy",
    "/dmca",
    "/about/privacy",
    "/about/terms",
)


def is_noise_url(url: str) -> bool:
    """True if this URL is known noise (API/CDN/legal/empty) and should be dropped."""
    try:
        parsed = urlparse(url)
    except ValueError:
        return True

    host = (parsed.hostname or "").lower().removeprefix("www.")
    if not host:
        return True

    # Empty path = homepage, not a destination
    path = parsed.path or "/"
    if path in ("", "/") and not parsed.query and not parsed.fragment:
        return True

    # Host denylist
    for pattern in _NOISE_HOST_REGEXES:
        if pattern.search(host):
            return True

    # Legal / footer path denylist
    path_lower = path.lower()
    for prefix in _NOISE_PATH_PREFIXES:
        if path_lower == prefix or path_lower.startswith(prefix + "/"):
            return True

    return False


# Public suffixes for the most common multi-label TLDs.
# Not exhaustive but covers what creators actually link to.
_TWO_PART_TLDS = {
    "co.uk", "co.jp", "co.kr", "co.in", "co.za", "co.nz",
    "com.au", "com.br", "com.mx", "com.cn", "com.tr",
    "ne.jp", "or.jp",
}


def base_domain(host: str) -> str:
    """Return the eTLD+1 of a host. Falls back to last 2 labels for unknown TLDs.

    Examples:
      base_domain('foo.bar.example.com') -> 'example.com'
      base_domain('foo.example.co.uk')   -> 'example.co.uk'
      base_domain('example.com')         -> 'example.com'
      base_domain('localhost')           -> 'localhost'
    """
    if not host:
        return ""
    host = host.lower().removeprefix("www.")
    parts = host.split(".")
    if len(parts) <= 2:
        return host
    last_two = ".".join(parts[-2:])
    last_three = ".".join(parts[-3:])
    if last_two in _TWO_PART_TLDS:
        return last_three
    return last_two


def same_base_domain(a: str, b: str) -> bool:
    """True if two URLs share the same eTLD+1."""
    try:
        ha = (urlparse(a).hostname or "").lower().removeprefix("www.")
        hb = (urlparse(b).hostname or "").lower().removeprefix("www.")
    except ValueError:
        return False
    return base_domain(ha) == base_domain(hb) and ha != "" and hb != ""
