# scripts/tests/harvester/test_gazetteer_extended.py
import pytest
from unittest.mock import MagicMock, patch

from data.gazetteer_loader import lookup
import data.gazetteer_loader as gz_module
from harvester.orchestrator import _destination_class_for


@pytest.fixture(autouse=True)
def _reload_gazetteer():
    """Force reload — fixtures may have run earlier and cached the old rules."""
    gz_module._CACHE = None
    yield
    gz_module._CACHE = None


def test_buymeacoffee_classifies_as_monetization():
    result = lookup("https://buymeacoffee.com/example")
    assert result is not None
    _, account_type, _ = result
    assert account_type == "monetization"


def test_kofi_classifies_as_monetization():
    result = lookup("https://ko-fi.com/example")
    assert result is not None
    _, account_type, _ = result
    assert account_type == "monetization"


def test_telegram_classifies_as_messaging():
    result = lookup("https://t.me/exampleuser")
    assert result is not None
    _, account_type, _ = result
    assert account_type == "messaging"


def test_substack_classifies_via_host_aware_mapping():
    # gazetteer returns 'other'; host-aware map promotes to 'content'
    cls = _destination_class_for("other", "https://example.substack.com/")
    assert cls == "content"


def test_amzn_to_classifies_via_host_aware_as_affiliate():
    cls = _destination_class_for("monetization", "https://amzn.to/3xy2z")
    assert cls == "affiliate"


def test_geni_us_classifies_as_affiliate():
    cls = _destination_class_for("monetization", "https://geni.us/abc")
    assert cls == "affiliate"


def test_open_spotify_classifies_as_content():
    cls = _destination_class_for("other", "https://open.spotify.com/show/abc123")
    assert cls == "content"


def test_shopify_classifies_as_commerce():
    cls = _destination_class_for("monetization", "https://example.shopify.com/")
    assert cls == "commerce"


def test_etsy_classifies_as_commerce():
    cls = _destination_class_for("monetization", "https://etsy.com/shop/example")
    assert cls == "commerce"


def test_default_account_type_mapping_unchanged():
    # When no host-aware override applies, the simple account_type → class map wins
    cls = _destination_class_for("monetization", "https://onlyfans.com/x")
    assert cls == "monetization"
    cls = _destination_class_for("link_in_bio", "https://linktr.ee/x")
    assert cls == "aggregator"
    cls = _destination_class_for("social", "https://instagram.com/x")
    assert cls == "social"
    cls = _destination_class_for("messaging", "https://t.me/x")
    assert cls == "messaging"


def test_unknown_account_type_falls_through_to_unknown():
    cls = _destination_class_for("other", "https://example.com/random")
    assert cls == "unknown"
