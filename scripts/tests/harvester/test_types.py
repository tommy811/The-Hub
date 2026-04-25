# scripts/tests/harvester/test_types.py
import pytest
from pydantic import ValidationError

from harvester.types import HarvestedUrl, Tier1Result, HARVEST_CLASSES, SIGNAL_KEYWORDS
from schemas import DestinationClass


def test_harvested_url_minimal():
    h = HarvestedUrl(
        canonical_url="https://fanplace.com/x",
        raw_url="https://fanplace.com/x?l_=abc",
        raw_text="my content",
        destination_class="monetization",
        harvest_method="headless",
    )
    assert h.canonical_url == "https://fanplace.com/x"
    assert h.harvest_method == "headless"


def test_harvested_url_rejects_unknown_destination_class():
    with pytest.raises(ValidationError):
        HarvestedUrl(
            canonical_url="https://x.com/y",
            raw_url="https://x.com/y",
            raw_text="",
            destination_class="bogus",  # not in DestinationClass Literal
            harvest_method="httpx",
        )


def test_destination_class_extended():
    # All 10 values must be valid Literal members
    for v in ("monetization", "aggregator", "social", "commerce", "messaging",
              "content", "affiliate", "professional", "other", "unknown"):
        h = HarvestedUrl(
            canonical_url="https://example.com",
            raw_url="https://example.com",
            raw_text="",
            destination_class=v,  # type: ignore[arg-type]
            harvest_method="httpx",
        )
        assert h.destination_class == v


def test_harvest_classes_does_not_include_terminal_destinations():
    # Recursion gate: don't recurse into social profiles (fetcher path),
    # monetization endpoints (terminal), or messaging links (terminal).
    assert "social" not in HARVEST_CLASSES
    assert "monetization" not in HARVEST_CLASSES
    assert "messaging" not in HARVEST_CLASSES
    # But DO recurse into anything that might contain further outbound links
    assert "aggregator" in HARVEST_CLASSES
    assert "content" in HARVEST_CLASSES
    assert "commerce" in HARVEST_CLASSES
    assert "professional" in HARVEST_CLASSES
    assert "unknown" in HARVEST_CLASSES


def test_signal_keywords_present():
    assert "sensitive content" in SIGNAL_KEYWORDS
    assert "open link" in SIGNAL_KEYWORDS
    assert "continue to" in SIGNAL_KEYWORDS
    assert "i am over 18" in SIGNAL_KEYWORDS


def test_tier1_result_holds_signals():
    r = Tier1Result(
        html="<html></html>",
        anchors=["https://x.com/y"],
        signals_tripped={"interstitial", "low_anchor_count"},
    )
    assert "interstitial" in r.signals_tripped
    assert r.needs_tier2() is True


def test_tier1_result_no_signals_skips_tier2():
    r = Tier1Result(html="", anchors=["https://x.com/y"], signals_tripped=set())
    assert r.needs_tier2() is False
