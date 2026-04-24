# scripts/tests/pipeline/test_integration.py
"""Integration tests for the resolver: full linktree-hub flow and budget exhaustion."""
from unittest.mock import MagicMock, patch
from pipeline.resolver import resolve_seed
from pipeline.budget import BudgetTracker
from pipeline.classifier import Classification
from schemas import InputContext, DiscoveryResultV2


def _ctx(handle, platform, external_urls=None):
    """Build a minimal InputContext for testing."""
    return InputContext(
        handle=handle, platform=platform, display_name=handle,
        bio="", follower_count=1000, avatar_url=None,
        external_urls=external_urls or [], source_note="test",
    )


@patch("pipeline.resolver.aggregators_linktree.resolve")
@patch("pipeline.resolver.run_gemini_discovery_v2")
@patch("pipeline.resolver.classify")
@patch("pipeline.resolver.fetch_seed")
def test_linktree_hub_with_monetization_destination(
    mock_fetch, mock_classify, mock_gemini, mock_linktree,
):
    """Full IG → Linktree → (OnlyFans + IG_backup) path.

    Verifies:
    - Seed fetch on IG
    - Linktree detected and expanded
    - All 3 URLs (linktree, onlyfans, ig_backup) classified and recorded
    - Classifications reflect the actual destination types
    """
    mock_fetch.return_value = _ctx("alice", "instagram",
                                    external_urls=["https://linktr.ee/alice"])
    mock_linktree.return_value = [
        "https://onlyfans.com/alice_of",
        "https://instagram.com/alice_backup",
    ]
    # Iterator of classifications: one per URL (linktree + 2 children)
    classifications = iter([
        Classification("linktree", "link_in_bio", 1.0, "rule:linktree_link_in_bio"),
        Classification("onlyfans", "monetization", 1.0, "rule:onlyfans_monetization"),
        Classification("instagram", "social", 1.0, "rule:instagram_social"),
    ])
    mock_classify.side_effect = lambda *a, **kw: next(classifications)
    mock_gemini.return_value = DiscoveryResultV2(
        canonical_name="Alice", known_usernames=["alice"],
        display_name_variants=["Alice"], raw_reasoning="",
    )

    budget = BudgetTracker(cap_cents=1000)
    result = resolve_seed(
        handle="alice", platform_hint="instagram",
        supabase=MagicMock(), apify_client=MagicMock(),
        budget=budget,
    )

    # All 3 URLs should be discovered and classified
    urls = {du.canonical_url for du in result.discovered_urls}
    assert "https://linktr.ee/alice" in urls
    assert "https://onlyfans.com/alice_of" in urls
    assert "https://instagram.com/alice_backup" in urls

    # Verify destination classes are correct
    du_by_url = {du.canonical_url: du for du in result.discovered_urls}
    assert du_by_url["https://linktr.ee/alice"].destination_class == "aggregator"
    assert du_by_url["https://onlyfans.com/alice_of"].destination_class == "monetization"
    assert du_by_url["https://instagram.com/alice_backup"].destination_class == "social"


@patch("pipeline.resolver.run_gemini_discovery_v2")
@patch("pipeline.resolver.classify")
@patch("pipeline.resolver.fetch_seed")
def test_budget_exhaustion_partial_completion(mock_fetch, mock_classify, mock_gemini):
    """Budget exhaustion stops enrichment cleanly but allows classification.

    Verifies:
    - Classification runs on all discovered URLs (classification is free)
    - Enrichment (fetching profiles) stops when budget exhausted
    - No exception raised; graceful degradation
    - Budget state remains consistent
    """
    mock_fetch.return_value = _ctx("alice", "instagram",
                                    external_urls=["https://instagram.com/b", "https://tiktok.com/@c"])
    classifications = iter([
        Classification("instagram", "social", 1.0, "rule:instagram_social"),
        Classification("tiktok", "social", 1.0, "rule:tiktok_social"),
    ])
    mock_classify.side_effect = lambda *a, **kw: next(classifications)
    mock_gemini.return_value = DiscoveryResultV2(
        canonical_name="Alice", known_usernames=["alice"],
        display_name_variants=["Alice"], raw_reasoning="",
    )

    # Cap just fits the seed fetch (10¢ for IG scraper) but limits enrichment.
    # Classification of 2 URLs is free.
    # IG enrichment would be 10¢ (total 20¢), TT would be 8¢ (total 28¢, over budget).
    budget = BudgetTracker(cap_cents=25)
    result = resolve_seed(
        handle="alice", platform_hint="instagram",
        supabase=MagicMock(), apify_client=MagicMock(),
        budget=budget,
    )

    # Both URLs should be classified (free operation)
    assert len(result.discovered_urls) == 2
    urls = {du.canonical_url for du in result.discovered_urls}
    assert "https://instagram.com/b" in urls
    assert "https://tiktok.com/@c" in urls

    # Enrichment is budget-limited; at most one IG fetch at 10¢ (seed was 10¢, total 20¢)
    # TT fetch would exceed budget (20¢ + 8¢ = 28¢ > 25¢)
    assert len(result.enriched_contexts) <= 1

    # Budget should not be exceeded
    assert budget.spent_cents <= budget.cap_cents
