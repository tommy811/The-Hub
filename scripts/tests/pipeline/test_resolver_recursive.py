# scripts/tests/pipeline/test_resolver_recursive.py
import os
from unittest.mock import MagicMock, patch
import pytest

from schemas import InputContext, DiscoveryResultV2, TextMention, DiscoveredUrl
from pipeline.resolver import ResolverResult, resolve_seed
from pipeline.budget import BudgetTracker
from pipeline.classifier import Classification


def _mk_ctx(**overrides):
    base = dict(
        handle="alice", platform="instagram", display_name="Alice",
        bio="", follower_count=50000, avatar_url="https://cdn/a.jpg",
        external_urls=[], source_note="test",
    )
    base.update(overrides)
    return InputContext(**base)


def test_resolver_module_exposes_max_depth_constant():
    from pipeline import resolver
    assert hasattr(resolver, "MAX_DEPTH")
    assert isinstance(resolver.MAX_DEPTH, int)
    assert resolver.MAX_DEPTH >= 2


def test_resolver_module_exposes_recursive_gemini_constant():
    from pipeline import resolver
    assert hasattr(resolver, "RECURSIVE_GEMINI")
    assert isinstance(resolver.RECURSIVE_GEMINI, bool)


@patch("pipeline.resolver.fetch_ig.fetch")
@patch("pipeline.resolver.run_gemini_discovery_v2")
@patch("pipeline.resolver.classify")
@patch("pipeline.resolver.fetch_seed")
def test_secondary_external_urls_are_followed(
    mock_fetch_seed, mock_classify, mock_gemini, mock_ig_fetch,
):
    """Kira-shaped case: TT seed has 1 external URL pointing to IG.
    The IG ctx has its own external URL pointing to OnlyFans.
    Both must land in discovered_urls."""

    mock_fetch_seed.return_value = _mk_ctx(
        handle="kira", platform="tiktok", bio="",
        external_urls=["https://instagram.com/kirapregiato"],
    )
    mock_ig_fetch.return_value = _mk_ctx(
        handle="kirapregiato", platform="instagram", bio="",
        external_urls=["https://onlyfans.com/kira"],
    )

    classifications = iter([
        Classification(platform="instagram", account_type="social",
                       confidence=1.0, reason="rule:instagram_social"),
        Classification(platform="onlyfans", account_type="monetization",
                       confidence=1.0, reason="rule:onlyfans_monetization"),
    ])
    mock_classify.side_effect = lambda *a, **kw: next(classifications)
    mock_gemini.return_value = DiscoveryResultV2(
        canonical_name="Kira", known_usernames=["kira"],
        display_name_variants=["Kira"], raw_reasoning="",
    )

    budget = BudgetTracker(cap_cents=1000)
    result = resolve_seed(
        handle="kira", platform_hint="tiktok",
        supabase=MagicMock(), apify_client=MagicMock(),
        budget=budget,
    )

    urls = [du.canonical_url for du in result.discovered_urls]
    assert any("instagram.com/kirapregiato" in u for u in urls), \
        f"depth-1 IG missing from {urls}"
    assert any("onlyfans.com/kira" in u for u in urls), \
        f"depth-2 OF missing from {urls} — recursion didn't fire"
    assert any("instagram.com" in k for k in result.enriched_contexts.keys())


@patch("pipeline.resolver.fetch_ig.fetch")
@patch("pipeline.resolver.run_gemini_discovery_v2")
@patch("pipeline.resolver.classify")
@patch("pipeline.resolver.fetch_seed")
def test_max_depth_defensive_cap_truncates_chain(
    mock_fetch_seed, mock_classify, mock_gemini, mock_ig_fetch,
    monkeypatch,
):
    """Force MAX_DEPTH=2; build a 5-deep IG chain. Confirm only depths 1-2 land."""
    monkeypatch.setattr("pipeline.resolver.MAX_DEPTH", 2)

    mock_fetch_seed.return_value = _mk_ctx(
        handle="seed", platform="instagram",
        external_urls=["https://instagram.com/ig1"],
    )

    chain = iter([
        _mk_ctx(handle="ig1", external_urls=["https://instagram.com/ig2"]),
        _mk_ctx(handle="ig2", external_urls=["https://instagram.com/ig3"]),
        _mk_ctx(handle="ig3", external_urls=["https://instagram.com/ig4"]),
        _mk_ctx(handle="ig4", external_urls=["https://instagram.com/ig5"]),
        _mk_ctx(handle="ig5", external_urls=[]),
    ])
    mock_ig_fetch.side_effect = lambda client, h: next(chain)

    mock_classify.return_value = Classification(
        platform="instagram", account_type="social",
        confidence=1.0, reason="rule:instagram_social",
    )
    mock_gemini.return_value = DiscoveryResultV2(
        canonical_name="Seed", known_usernames=["seed"],
        display_name_variants=["Seed"], raw_reasoning="",
    )

    budget = BudgetTracker(cap_cents=10000)
    result = resolve_seed(
        handle="seed", platform_hint="instagram",
        supabase=MagicMock(), apify_client=MagicMock(),
        budget=budget,
    )

    depths = sorted({du.depth for du in result.discovered_urls})
    assert max(depths) <= 2, f"depths={depths} exceeded MAX_DEPTH=2"
    assert 2 in depths, f"never reached depth 2: depths={depths}"


@patch("pipeline.resolver.fetch_ig.fetch")
@patch("pipeline.resolver.fetch_tt.fetch")
@patch("pipeline.resolver.run_gemini_discovery_v2")
@patch("pipeline.resolver.classify")
@patch("pipeline.resolver.fetch_seed")
def test_cycle_dedup_prevents_infinite_loop(
    mock_fetch_seed, mock_classify, mock_gemini, mock_tt_fetch, mock_ig_fetch,
):
    """A's bio links to B; B's bio links back to A. Verify each canonical_url
    appears exactly once and the resolver returns cleanly."""

    seed_url = "https://tiktok.com/@kira"
    ig_url = "https://instagram.com/kira"

    mock_fetch_seed.return_value = _mk_ctx(
        handle="kira", platform="tiktok",
        external_urls=[ig_url],
    )
    mock_ig_fetch.return_value = _mk_ctx(
        handle="kira", platform="instagram",
        external_urls=[seed_url],
    )
    mock_tt_fetch.return_value = _mk_ctx(
        handle="kira", platform="tiktok",
        external_urls=[ig_url],
    )

    mock_classify.side_effect = lambda url, **kw: (
        Classification(platform="instagram", account_type="social",
                       confidence=1.0, reason="rule:instagram_social")
        if "instagram.com" in url else
        Classification(platform="tiktok", account_type="social",
                       confidence=1.0, reason="rule:tiktok_social")
    )
    mock_gemini.return_value = DiscoveryResultV2(
        canonical_name="Kira", known_usernames=["kira"],
        display_name_variants=["Kira"], raw_reasoning="",
    )

    budget = BudgetTracker(cap_cents=1000)
    result = resolve_seed(
        handle="kira", platform_hint="tiktok",
        supabase=MagicMock(), apify_client=MagicMock(),
        budget=budget,
    )

    canonicals = [du.canonical_url for du in result.discovered_urls]
    assert len(canonicals) == len(set(canonicals)), \
        f"duplicate URLs in {canonicals} — cycle dedup failed"
    assert any("instagram.com" in c for c in canonicals)
    assert not any("tiktok.com" in k for k in result.enriched_contexts.keys()), \
        f"TT seed was re-fetched via cycle: {result.enriched_contexts}"


@patch("pipeline.resolver.aggregators_linktree.resolve")
@patch("pipeline.resolver.aggregators_linktree.is_linktree")
@patch("pipeline.resolver.fetch_ig.fetch")
@patch("pipeline.resolver.run_gemini_discovery_v2")
@patch("pipeline.resolver.classify")
@patch("pipeline.resolver.fetch_seed")
def test_aggregator_chain_blocked_at_depth_one(
    mock_fetch_seed, mock_classify, mock_gemini, mock_ig_fetch,
    mock_is_linktree, mock_linktree_resolve,
):
    """Seed -> IG (depth 1) -> Linktree (depth 2) -> children include another Linktree.
    The second Linktree must NOT be re-expanded."""

    mock_fetch_seed.return_value = _mk_ctx(
        handle="seed", platform="instagram",
        external_urls=["https://instagram.com/secondary"],
    )
    mock_ig_fetch.return_value = _mk_ctx(
        handle="secondary", platform="instagram",
        external_urls=["https://linktr.ee/main"],
    )

    mock_is_linktree.side_effect = lambda u: "linktr.ee" in u
    mock_linktree_resolve.return_value = [
        "https://onlyfans.com/x",
        "https://linktr.ee/another",
    ]

    classifications = iter([
        Classification(platform="instagram", account_type="social",
                       confidence=1.0, reason="rule:instagram_social"),
        Classification(platform="linktree", account_type="link_in_bio",
                       confidence=1.0, reason="rule:linktree_link_in_bio"),
        Classification(platform="onlyfans", account_type="monetization",
                       confidence=1.0, reason="rule:onlyfans_monetization"),
        Classification(platform="linktree", account_type="link_in_bio",
                       confidence=1.0, reason="rule:linktree_link_in_bio"),
    ])
    mock_classify.side_effect = lambda *a, **kw: next(classifications)
    mock_gemini.return_value = DiscoveryResultV2(
        canonical_name="Seed", known_usernames=["seed"],
        display_name_variants=["Seed"], raw_reasoning="",
    )

    budget = BudgetTracker(cap_cents=1000)
    result = resolve_seed(
        handle="seed", platform_hint="instagram",
        supabase=MagicMock(), apify_client=MagicMock(),
        budget=budget,
    )

    assert mock_linktree_resolve.call_count == 1, \
        f"second linktree was re-expanded: {mock_linktree_resolve.call_count} calls"
    assert len(result.discovered_urls) == 4
