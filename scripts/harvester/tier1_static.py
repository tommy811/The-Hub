# scripts/harvester/tier1_static.py
"""Tier 1 — httpx fetch + BeautifulSoup parse + signal-regex escalation triggers.

Cheap path: 95%+ of pages have all their links in static HTML. Returns a
Tier1Result with extracted anchors and the set of signals (if any) that say
"this page needs Tier 2 (headless browser) to capture everything".
"""
import re

import httpx
from bs4 import BeautifulSoup

from harvester.types import (
    Tier1Result, SIGNAL_KEYWORDS, SPA_MARKERS, LOW_ANCHOR_FLOOR,
)

_DESKTOP_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)

_EXCLUDED_SCHEMES = ("mailto:", "tel:", "javascript:")

# Platform-style filename pattern, e.g. `/assets/platforms/fanplace-logo.svg`.
# Used to detect <button> wrappers that hide a real outbound destination
# behind a click-to-reveal interstitial (the canonical Fanplace gate pattern).
_PLATFORM_ICON_FILENAME_RE = re.compile(
    r"(?:onlyfans|fanvue|fanplace|patreon|telegram|instagram|tiktok|youtube|"
    r"twitter|facebook|amazon|shopify|spotify|buymeacoffee|kofi|substack|"
    r"linktree|beacons|allmylinks|launchyoursocials)"
    r"[^/\"'>]*-(?:logo|icon)\.(?:svg|png|jpg)",
    flags=re.IGNORECASE,
)


def _has_button_with_platform_icon(html: str) -> bool:
    """True if any <button> in `html` contains an <img>/<svg> whose src/href
    references a platform-style filename (e.g. fanplace-logo.svg).

    Uses BeautifulSoup rather than a flat regex because real-world buttons
    carry hundreds of chars of Tailwind class soup between the `<button>`
    open tag and the nested icon — a window-bound regex misses them.
    """
    soup = BeautifulSoup(html, "html.parser")
    for btn in soup.find_all("button"):
        for tag in btn.find_all(["img", "svg"]):
            for attr in ("src", "href"):
                val = tag.get(attr) or ""
                if _PLATFORM_ICON_FILENAME_RE.search(val):
                    return True
    return False


def parse_html(html: str) -> Tier1Result:
    """Parse static HTML; extract anchors and run signal detection."""
    soup = BeautifulSoup(html, "html.parser")
    anchors: list[str] = []
    anchor_texts: dict[str, str] = {}
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        if not href or href.startswith(_EXCLUDED_SCHEMES) or href.startswith("#"):
            continue
        if href.startswith("/"):
            continue  # same-origin path — not an outbound destination
        anchors.append(href)
        anchor_texts[href] = (a.get_text() or "").strip()[:200]

    signals_tripped = detect_signals(html, anchors)

    return Tier1Result(
        html=html,
        anchors=anchors,
        anchor_texts=anchor_texts,
        signals_tripped=signals_tripped,
    )


def detect_signals(html: str, anchors: list[str]) -> set[str]:
    """Run cheap regex/string checks for escalation signals."""
    signals: set[str] = set()
    lowered = html.lower()

    # 1. Interstitial keywords
    if any(kw in lowered for kw in SIGNAL_KEYWORDS):
        signals.add("interstitial")

    # 2. SPA hydration markers
    if any(m in lowered for m in SPA_MARKERS):
        signals.add("spa_hydration")

    # 3. <button> with platform-icon imagery
    if _has_button_with_platform_icon(html):
        signals.add("button_with_platform_icon")

    # 4. Suspiciously low anchor count
    if len(anchors) < LOW_ANCHOR_FLOOR:
        signals.add("low_anchor_count")

    return signals


def fetch_static(url: str, timeout: float = 10.0) -> Tier1Result:
    """Fetch URL via httpx with desktop UA; return Tier1Result.

    On any error returns an empty Tier1Result with `fetch_failed` signal — the
    orchestrator decides whether to escalate.
    """
    try:
        resp = httpx.get(
            url,
            timeout=timeout,
            follow_redirects=True,
            headers={"User-Agent": _DESKTOP_UA},
        )
        resp.raise_for_status()
    except Exception:
        return Tier1Result(html="", anchors=[], signals_tripped={"fetch_failed"})
    return parse_html(resp.text)
