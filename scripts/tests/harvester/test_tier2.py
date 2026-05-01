# scripts/tests/harvester/test_tier2.py
from unittest.mock import patch, MagicMock

import pytest

from harvester.tier2_headless import fetch_headless, _build_actor_input, ACTOR_ID, COST_CENTS
from harvester.types import HarvestedUrl


def test_actor_input_includes_page_function():
    inp = _build_actor_input("https://tapforallmylinks.com/esmaecursed")
    assert inp["startUrls"] == [{"url": "https://tapforallmylinks.com/esmaecursed"}]
    assert "pageFunction" in inp
    assert "window.__capturedUrls" in inp["pageFunction"]
    # Critical: hook must run BEFORE any other script
    assert "evaluateOnNewDocument" in inp["pageFunction"]


def test_actor_input_includes_all_interstitial_keywords():
    """Regression guard: every keyword the page function auto-clicks must
    appear in the loaded JS string. If a future edit drops one, this fails."""
    inp = _build_actor_input("https://example.com")
    pf = inp["pageFunction"]
    for keyword in ("open link", "continue", "i am over 18", "i agree",
                    "i confirm", "18+", "enter"):
        assert keyword in pf, f"interstitial keyword {keyword!r} missing from pageFunction"

    # Also assert the lowercase translate mask is full A-Z (catches the
    # incomplete-mask bug that silently breaks age-gate detection)
    assert "ABCDEFGHIJKLMNOPQRSTUVWXYZ" in pf
    assert "abcdefghijklmnopqrstuvwxyz" in pf


def test_actor_input_caps_at_one_request():
    inp = _build_actor_input("https://example.com")
    assert inp["maxRequestsPerCrawl"] == 1
    # No following links from the harvested page itself
    assert inp.get("linkSelector") in (None, "", "__never_match__")


def test_cost_cents_constant():
    # Documented: 1 page run on apify/puppeteer-scraper ≈ 2¢
    assert COST_CENTS == 2


@patch("harvester.tier2_headless.ApifyClient")
def test_fetch_headless_returns_harvested_urls(mock_client_cls):
    mock_run = MagicMock()
    mock_run.call.return_value = {"defaultDatasetId": "ds123"}
    mock_dataset = MagicMock()
    mock_dataset.list_items.return_value.items = [{
        "urls": [
            {"url": "https://fanplace.com/x?l_=abc", "text": "my content"},
            {"url": "https://t.me/xchannel", "text": "telegram"},
        ]
    }]
    mock_client = MagicMock()
    mock_client.actor.return_value = mock_run
    mock_client.dataset.return_value = mock_dataset
    mock_client_cls.return_value = mock_client

    result = fetch_headless("https://tapforallmylinks.com/esmaecursed", apify_token="fake")

    assert len(result) == 2
    assert all(isinstance(h, HarvestedUrl) for h in result)
    fanplace = next(h for h in result if "fanplace" in h.canonical_url)
    assert fanplace.raw_url == "https://fanplace.com/x?l_=abc"
    assert fanplace.canonical_url == "https://fanplace.com/x"
    assert fanplace.raw_text == "my content"
    assert fanplace.harvest_method == "headless"
    assert fanplace.destination_class == "unknown"


@patch("harvester.tier2_headless.ApifyClient")
def test_fetch_headless_returns_empty_on_actor_failure(mock_client_cls):
    mock_client = MagicMock()
    mock_client.actor.return_value.call.side_effect = RuntimeError("actor crashed")
    mock_client_cls.return_value = mock_client

    result = fetch_headless("https://example.com", apify_token="fake")
    assert result == []


@patch("harvester.tier2_headless.ApifyClient")
def test_fetch_headless_dedups_urls(mock_client_cls):
    mock_run = MagicMock()
    mock_run.call.return_value = {"defaultDatasetId": "ds123"}
    mock_dataset = MagicMock()
    mock_dataset.list_items.return_value.items = [{
        "urls": [
            {"url": "https://x.com/y", "text": ""},
            {"url": "https://x.com/y", "text": ""},
            {"url": "https://x.com/y/", "text": ""},  # canonicalizes to same
        ]
    }]
    mock_client = MagicMock()
    mock_client.actor.return_value = mock_run
    mock_client.dataset.return_value = mock_dataset
    mock_client_cls.return_value = mock_client

    result = fetch_headless("https://aggregator.example.com", apify_token="fake")
    assert len(result) == 1
