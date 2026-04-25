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
