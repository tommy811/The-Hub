# scripts/fetchers/base.py — Shared base for platform fetchers
import re
from typing import Optional


class EmptyDatasetError(RuntimeError):
    """Raised when a fetcher returns zero items, or a shape-valid but empty item.

    Signals the login-wall / private / banned / not-found case. Discovery treats
    this as a clean failure (mark_discovery_failed with empty_context reason).
    """


def first_or_none(items: list[dict]) -> Optional[dict]:
    return items[0] if items else None


# Apify scraper actors rotate proxies; some profiles get blocked on certain
# proxy pools and succeed on the next attempt with a fresh one. These phrases
# are the upstream errors we've observed for transient block — anything else
# (truly missing profile, real auth failure, schema crash) should fail loudly
# rather than burn three retry attempts on a permanent error.
_TRANSIENT_APIFY_RE = re.compile(
    r"(?i)("
    r"user was not found|"
    r"authentication token|"
    r"rate limit|"
    r"challenge|"
    r"session expired|"
    r"captcha|"
    r"too many requests|"
    r"429"
    r")"
)


def is_transient_apify_error(exc: BaseException) -> bool:
    """Predicate for tenacity retry — True if the exception looks transient.

    Crucially excludes EmptyDatasetError (its message says "returned 0 items"
    which doesn't match), so genuine no-data outcomes don't get retried.
    """
    return bool(_TRANSIENT_APIFY_RE.search(str(exc)))
