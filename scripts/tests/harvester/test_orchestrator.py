# scripts/tests/harvester/test_orchestrator.py
from unittest.mock import patch, MagicMock

from harvester.orchestrator import harvest_urls
from harvester.types import HarvestedUrl, Tier1Result


@patch("harvester.orchestrator.write_cache")
@patch("harvester.orchestrator.classify")
@patch("harvester.orchestrator.fetch_headless")
@patch("harvester.orchestrator.fetch_static")
@patch("harvester.orchestrator.lookup_cache")
def test_cache_hit_short_circuits(
    mock_cache, mock_static, mock_headless, mock_classify, mock_write
):
    mock_cache.return_value = [HarvestedUrl(
        canonical_url="https://onlyfans.com/x",
        raw_url="https://onlyfans.com/x",
        raw_text="OnlyFans",
        destination_class="monetization",
        harvest_method="httpx",
    )]
    sb = MagicMock()
    result = harvest_urls("https://linktr.ee/x", supabase=sb)

    assert len(result) == 1
    assert result[0].canonical_url == "https://onlyfans.com/x"
    mock_static.assert_not_called()
    mock_headless.assert_not_called()
    mock_classify.assert_not_called()
    mock_write.assert_not_called()


@patch("harvester.orchestrator.write_cache")
@patch("harvester.orchestrator.classify")
@patch("harvester.orchestrator.fetch_headless")
@patch("harvester.orchestrator.fetch_static")
@patch("harvester.orchestrator.lookup_cache")
def test_tier1_only_when_no_signals(
    mock_cache, mock_static, mock_headless, mock_classify, mock_write
):
    mock_cache.return_value = None
    mock_static.return_value = Tier1Result(
        html="<html></html>",
        anchors=["https://onlyfans.com/x", "https://patreon.com/x", "https://instagram.com/x"],
        anchor_texts={
            "https://onlyfans.com/x": "OF",
            "https://patreon.com/x": "Patreon",
            "https://instagram.com/x": "IG",
        },
        signals_tripped=set(),
    )

    def _fake_classify(url, supabase):
        from pipeline.classifier import Classification
        if "onlyfans" in url:
            return Classification(platform="onlyfans", account_type="monetization", confidence=1.0, reason="rule:onlyfans_monetization")
        if "patreon" in url:
            return Classification(platform="patreon", account_type="monetization", confidence=1.0, reason="rule:patreon_monetization")
        return Classification(platform="instagram", account_type="social", confidence=1.0, reason="rule:instagram_social")

    mock_classify.side_effect = _fake_classify
    sb = MagicMock()

    result = harvest_urls("https://linktr.ee/x", supabase=sb)

    assert len(result) == 3
    mock_static.assert_called_once()
    mock_headless.assert_not_called()  # signals empty → no escalation
    mock_write.assert_called_once()
    written_method = mock_write.call_args.args[2]
    assert written_method == "httpx"


@patch("harvester.orchestrator.write_cache")
@patch("harvester.orchestrator.classify")
@patch("harvester.orchestrator.fetch_headless")
@patch("harvester.orchestrator.fetch_static")
@patch("harvester.orchestrator.lookup_cache")
def test_tier2_fires_when_signals_tripped(
    mock_cache, mock_static, mock_headless, mock_classify, mock_write
):
    mock_cache.return_value = None
    mock_static.return_value = Tier1Result(
        html="<button>my content</button>",
        anchors=["https://t.me/foo"],
        signals_tripped={"interstitial", "button_with_platform_icon"},
    )
    mock_headless.return_value = [
        HarvestedUrl(
            canonical_url="https://fanplace.com/x",
            raw_url="https://fanplace.com/x?l_=abc",
            raw_text="my content",
            destination_class="unknown",
            harvest_method="headless",
        ),
    ]

    def _fake_classify(url, supabase):
        from pipeline.classifier import Classification
        return Classification(platform="fanplace", account_type="monetization", confidence=1.0, reason="rule:fanplace_monetization")

    mock_classify.side_effect = _fake_classify
    sb = MagicMock()

    result = harvest_urls("https://tapforallmylinks.com/esmae", supabase=sb)

    mock_headless.assert_called_once_with("https://tapforallmylinks.com/esmae")
    assert len(result) == 1
    assert result[0].destination_class == "monetization"
    assert result[0].harvest_method == "headless"


@patch("harvester.orchestrator.lookup_cache")
def test_no_supabase_skips_cache_layer(mock_cache):
    # When supabase=None (offline tests), cache layer is skipped entirely
    mock_cache.return_value = None
    with patch("harvester.orchestrator.fetch_static") as mock_static:
        mock_static.return_value = Tier1Result(html="", anchors=[], signals_tripped={"fetch_failed"})
        # And tier 2 also skipped if no apify token
        with patch("harvester.orchestrator.fetch_headless", return_value=[]):
            result = harvest_urls("https://example.com", supabase=None)
    assert result == []


@patch("harvester.orchestrator.classify")
@patch("harvester.orchestrator.fetch_static")
@patch("harvester.orchestrator.lookup_cache")
def test_canonicalizes_anchors_before_classify(mock_cache, mock_static, mock_classify):
    mock_cache.return_value = None
    # Anchor with tracking params
    mock_static.return_value = Tier1Result(
        html="",
        anchors=["https://onlyfans.com/x?l_=abc&utm_source=ig"],
        anchor_texts={"https://onlyfans.com/x?l_=abc&utm_source=ig": "OF"},
        signals_tripped=set(),
    )
    from pipeline.classifier import Classification
    mock_classify.return_value = Classification(
        platform="onlyfans", account_type="monetization", confidence=1.0,
        reason="rule:onlyfans_monetization",
    )
    sb = MagicMock()
    result = harvest_urls("https://linktr.ee/x", supabase=sb)

    # classify() should have been called with the canonicalized URL
    mock_classify.assert_called_once_with("https://onlyfans.com/x", supabase=sb)
    assert result[0].canonical_url == "https://onlyfans.com/x"
    assert result[0].raw_url == "https://onlyfans.com/x?l_=abc&utm_source=ig"


@patch("harvester.orchestrator.write_cache")
@patch("harvester.orchestrator.classify")
@patch("harvester.orchestrator.fetch_static")
@patch("harvester.orchestrator.lookup_cache")
def test_filters_same_base_domain_and_noise(
    mock_cache, mock_static, mock_classify, mock_write
):
    """Same-eTLD+1 URLs and known-noise hosts are filtered before classify."""
    from pipeline.classifier import Classification
    mock_cache.return_value = None
    mock_static.return_value = Tier1Result(
        html="",
        anchors=[
            "https://onlyfans.com/x",                # different domain — keep
            "https://link.me/",                      # same eTLD+1 — drop
            "https://api.link.me/foo",               # same eTLD+1 + noise — drop
            "https://about.link.me/privacypolicy",   # same eTLD+1 + legal — drop
            "https://api.linkme.global",             # different domain BUT noise host — drop
            "https://d1abc.cloudfront.net",          # CDN noise — drop
        ],
        anchor_texts={
            "https://onlyfans.com/x": "OF",
            "https://link.me/": "Home",
            "https://api.link.me/foo": "API",
            "https://about.link.me/privacypolicy": "Privacy",
            "https://api.linkme.global": "API global",
            "https://d1abc.cloudfront.net": "CDN",
        },
        signals_tripped=set(),
    )
    mock_classify.return_value = Classification(
        platform="onlyfans", account_type="monetization", confidence=1.0,
        reason="rule:onlyfans_monetization",
    )
    sb = MagicMock()
    result = harvest_urls("https://link.me/kirapregiato", supabase=sb)
    assert len(result) == 1
    assert result[0].canonical_url == "https://onlyfans.com/x"
