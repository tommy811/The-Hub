# scripts/data/gazetteer_loader.py — Load monetization overlay + provide lookup(url)
import re
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse
import yaml

_OVERLAY_PATH = Path(__file__).resolve().parent / "monetization_overlay.yaml"

# Cache: {host: [entry_dict, ...]} where each entry may have a url_pattern
_CACHE: Optional[dict[str, list[dict]]] = None


def load_gazetteer() -> dict[str, list[dict]]:
    """Load + index the monetization overlay by host. Idempotent."""
    global _CACHE
    if _CACHE is not None:
        return _CACHE

    with _OVERLAY_PATH.open("r") as f:
        data = yaml.safe_load(f)

    index: dict[str, list[dict]] = {}
    for entry in data.get("entries", []):
        host = entry["host"].lower()
        # Precompile url_pattern regex if present
        if "url_pattern" in entry:
            entry = {**entry, "_url_re": re.compile(entry["url_pattern"])}
        index.setdefault(host, []).append(entry)

    _CACHE = index
    return index


def lookup(url: str) -> Optional[tuple[str, str, str]]:
    """Look up a (pre-canonicalized) URL in the gazetteer.

    Returns (platform, account_type, reason) or None if no rule matches.
    Expects input to already be canonicalized (lowercase host, no www, etc).
    """
    try:
        parsed = urlparse(url)
    except ValueError:
        return None

    host = (parsed.hostname or "").lower()
    if not host:
        return None

    gaz = load_gazetteer()
    entries = gaz.get(host, [])
    if not entries:
        return None

    path = parsed.path or "/"
    for entry in entries:
        if "_url_re" in entry:
            if entry["_url_re"].search(path):
                return (
                    entry["platform"],
                    entry["account_type"],
                    f"rule:{entry['platform']}_{entry['account_type']}",
                )
            # pattern present but didn't match — skip this entry
            continue
        return (
            entry["platform"],
            entry["account_type"],
            f"rule:{entry['platform']}_{entry['account_type']}",
        )

    # Every entry for this host had a url_pattern and none matched
    return None
