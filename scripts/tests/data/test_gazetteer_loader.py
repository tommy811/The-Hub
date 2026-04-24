# scripts/tests/data/test_gazetteer_loader.py
import pytest
from data.gazetteer_loader import load_gazetteer, lookup


def test_loads_without_error():
    gaz = load_gazetteer()
    assert gaz is not None
    assert len(gaz) > 10


def test_lookup_onlyfans_is_monetization():
    result = lookup("https://onlyfans.com/alice")
    assert result is not None
    platform, account_type, reason = result
    assert platform == "onlyfans"
    assert account_type == "monetization"
    assert reason.startswith("rule:")


def test_lookup_instagram_is_social():
    result = lookup("https://instagram.com/alice")
    assert result is not None
    assert result[0] == "instagram"
    assert result[1] == "social"


def test_lookup_amazon_shop_matches_pattern():
    result = lookup("https://amazon.com/shop/alice")
    assert result is not None
    assert result[0] == "amazon_storefront"


def test_lookup_amazon_non_shop_does_not_match():
    # amazon.com without /shop/ is not a storefront
    result = lookup("https://amazon.com/dp/B01234")
    assert result is None


def test_lookup_tiktok_shop_pattern():
    result = lookup("https://tiktok.com/@alice/shop")
    assert result is not None
    assert result[0] == "tiktok_shop"


def test_lookup_tiktok_profile_is_social():
    result = lookup("https://tiktok.com/@alice")
    assert result is not None
    assert result[0] == "tiktok"
    assert result[1] == "social"


def test_lookup_unknown_host_returns_none():
    result = lookup("https://some-weird-site.example/alice")
    assert result is None


def test_lookup_linktree_is_aggregator():
    result = lookup("https://linktr.ee/alice")
    assert result is not None
    assert result[1] == "link_in_bio"


def test_lookup_t_me_is_messaging():
    result = lookup("https://t.me/alice_channel")
    assert result is not None
    assert result[0] == "telegram_channel"
    assert result[1] == "messaging"


def test_lookup_expects_canonicalized_url():
    # Loader expects pre-canonicalized URLs. www + uppercase returns None
    # because canonicalize_url is the caller's responsibility.
    assert lookup("https://WWW.onlyfans.com/alice") is None
