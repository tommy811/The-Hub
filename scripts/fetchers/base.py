# scripts/fetchers/base.py — Shared base for platform fetchers
from typing import Optional


class EmptyDatasetError(RuntimeError):
    """Raised when a fetcher returns zero items, or a shape-valid but empty item.

    Signals the login-wall / private / banned / not-found case. Discovery treats
    this as a clean failure (mark_discovery_failed with empty_context reason).
    """


def first_or_none(items: list[dict]) -> Optional[dict]:
    return items[0] if items else None
