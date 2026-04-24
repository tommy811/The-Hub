# scripts/link_in_bio.py — DEPRECATED shim. Use aggregators.{linktree,beacons,custom_domain} directly.
import httpx  # re-exported for legacy test patches (link_in_bio.httpx.get)

from aggregators.linktree import is_linktree, resolve as _resolve_linktree
from aggregators.beacons import is_beacons, resolve as _resolve_beacons


def is_aggregator_url(url: str) -> bool:
    return is_linktree(url) or is_beacons(url)


def resolve_link_in_bio(url: str, timeout: float = 10.0) -> list[str]:
    if is_linktree(url):
        return _resolve_linktree(url, timeout=timeout)
    if is_beacons(url):
        return _resolve_beacons(url, timeout=timeout)
    return []
