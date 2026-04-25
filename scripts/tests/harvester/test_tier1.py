# scripts/tests/harvester/test_tier1.py
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from harvester.tier1_static import (
    fetch_static, parse_html, detect_signals, _has_button_with_platform_icon,
)
from harvester.types import LOW_ANCHOR_FLOOR


FIXTURES = Path(__file__).parent / "fixtures"


def _read(name: str) -> str:
    return (FIXTURES / name).read_text()


def test_parse_clean_linktree_extracts_all_anchors():
    html = _read("linktree_clean.html")
    result = parse_html(html)
    assert len(result.anchors) == 5
    assert "https://onlyfans.com/example" in result.anchors
    assert "https://patreon.com/example" in result.anchors


def test_parse_clean_linktree_no_signals_tripped():
    html = _read("linktree_clean.html")
    result = parse_html(html)
    assert result.signals_tripped == set()
    assert result.needs_tier2() is False


def test_parse_tapforallmylinks_trips_signals_for_tier2_escalation():
    """Live tapforallmylinks page must escalate to Tier 2 via SOME signal.

    The page is Astro/SPA-rendered: 'Sensitive Content' / 'Open link' interstitial
    text appears only after JS hydration, NOT in static HTML. So the `interstitial`
    keyword signal won't trip on this fixture, but the page still must be flagged
    for Tier 2 — via either `button_with_platform_icon` (the Fanplace gate) or
    `spa_hydration` (the astro-island markers).
    """
    html = _read("tapforallmylinks_esmae.html")
    result = parse_html(html)
    assert result.needs_tier2() is True
    # At least one of these specific signals should trip — interstitial keywords
    # may or may not appear in the static HTML depending on the page's framework.
    expected_signals = {"button_with_platform_icon", "spa_hydration"}
    assert expected_signals & result.signals_tripped, (
        f"Expected at least one of {expected_signals} to trip; "
        f"got {result.signals_tripped}"
    )


def test_parse_tapforallmylinks_trips_button_with_platform_icon_signal():
    html = _read("tapforallmylinks_esmae.html")
    result = parse_html(html)
    # Page has <button> elements with platform-logo SVGs (Fanplace gate)
    assert "button_with_platform_icon" in result.signals_tripped


def test_parse_synthetic_interstitial_keywords_trip_signal():
    """Direct test of the interstitial-keyword path. The keyword detector is the
    primary signal for non-SPA aggregators that put the gate copy in static HTML."""
    html = """<html><body>
        <h2>Sensitive Content</h2>
        <p>This link may contain content that is not appropriate for all audiences.</p>
        <button>Open link</button>
    </body></html>"""
    result = parse_html(html)
    assert "interstitial" in result.signals_tripped
    assert result.needs_tier2() is True


def test_parse_spa_hydration_trips_spa_signal():
    html = _read("spa_hydration.html")
    result = parse_html(html)
    assert "spa_hydration" in result.signals_tripped
    assert len(result.anchors) == 0


def test_parse_low_anchor_count_trips_signal():
    html = "<html><body><a href='https://example.com'>only one</a></body></html>"
    result = parse_html(html)
    assert "low_anchor_count" in result.signals_tripped


def test_button_with_platform_icon_detector():
    # button containing img with `*-logo.svg` src and no nearby anchor
    html = '''
    <button><img src="/assets/platforms/fanplace-logo.svg">my content</button>
    '''
    assert _has_button_with_platform_icon(html) is True


def test_button_with_text_only_does_not_trip():
    html = '<button>Subscribe</button>'
    assert _has_button_with_platform_icon(html) is False


@patch("harvester.tier1_static.httpx.get")
def test_fetch_static_uses_desktop_user_agent(mock_get):
    mock_response = MagicMock(text="<html></html>", status_code=200)
    mock_get.return_value = mock_response
    fetch_static("https://example.com/page")
    headers = mock_get.call_args.kwargs["headers"]
    assert "Mozilla/5.0" in headers["User-Agent"]
    assert "Macintosh" in headers["User-Agent"]  # desktop UA, prevents native-app deeplink injection


@patch("harvester.tier1_static.httpx.get")
def test_fetch_static_returns_empty_result_on_error(mock_get):
    mock_get.side_effect = Exception("network down")
    result = fetch_static("https://example.com/page")
    assert result.html == ""
    assert result.anchors == []
    assert "fetch_failed" in result.signals_tripped
