# scripts/tests/pipeline/test_resolver.py
from unittest.mock import MagicMock, patch
import pytest

from schemas import InputContext, DiscoveryResultV2, TextMention
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


@patch("pipeline.resolver.run_gemini_discovery_v2")
@patch("pipeline.resolver.classify")
@patch("pipeline.resolver.fetch_seed")
def test_stage_a_fetches_seed_then_stage_b_classifies_urls(
    mock_fetch, mock_classify, mock_gemini,
):
    mock_fetch.return_value = _mk_ctx(
        external_urls=["https://onlyfans.com/alice"],
    )
    mock_classify.return_value = Classification(
        platform="onlyfans", account_type="monetization",
        confidence=1.0, reason="rule:onlyfans_monetization",
    )
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

    assert result.seed_context.handle == "alice"
    assert len(result.discovered_urls) == 1
    assert result.discovered_urls[0].platform == "onlyfans"
    assert result.discovered_urls[0].destination_class == "monetization"


@patch("pipeline.resolver.aggregators_linktree.resolve")
@patch("pipeline.resolver.run_gemini_discovery_v2")
@patch("pipeline.resolver.classify")
@patch("pipeline.resolver.fetch_seed")
def test_aggregator_children_expanded_once_not_chained(
    mock_fetch, mock_classify, mock_gemini, mock_linktree_resolve,
):
    # Seed has a linktree URL; linktree resolves to 2 destinations
    mock_fetch.return_value = _mk_ctx(
        external_urls=["https://linktr.ee/alice"],
    )
    mock_linktree_resolve.return_value = [
        "https://onlyfans.com/alice",
        "https://linktr.ee/other",  # another linktree — should NOT be expanded again
    ]
    classifications = iter([
        Classification(platform="linktree", account_type="link_in_bio",
                       confidence=1.0, reason="rule:linktree_link_in_bio"),
        Classification(platform="onlyfans", account_type="monetization",
                       confidence=1.0, reason="rule:onlyfans_monetization"),
        Classification(platform="linktree", account_type="link_in_bio",
                       confidence=1.0, reason="rule:linktree_link_in_bio"),
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

    # Should have 3 URLs: the linktree itself + 2 destinations.
    # The second linktree (linktr.ee/other) is recorded but NOT re-expanded.
    assert len(result.discovered_urls) == 3
    # Only the first linktree was resolved — mock_linktree_resolve called once.
    assert mock_linktree_resolve.call_count == 1


@patch("pipeline.resolver.run_gemini_discovery_v2")
@patch("pipeline.resolver.classify")
@patch("pipeline.resolver.fetch_seed")
def test_text_mentions_synthesize_urls_and_loop_stage_b(
    mock_fetch, mock_classify, mock_gemini,
):
    mock_fetch.return_value = _mk_ctx(
        bio="also @alice_backup on tiktok",
        external_urls=[],
    )
    mock_gemini.return_value = DiscoveryResultV2(
        canonical_name="Alice", known_usernames=["alice", "alice_backup"],
        display_name_variants=["Alice"],
        text_mentions=[TextMention(platform="tiktok", handle="alice_backup")],
        raw_reasoning="",
    )
    mock_classify.return_value = Classification(
        platform="tiktok", account_type="social",
        confidence=1.0, reason="rule:tiktok_social",
    )

    budget = BudgetTracker(cap_cents=1000)
    result = resolve_seed(
        handle="alice", platform_hint="instagram",
        supabase=MagicMock(), apify_client=MagicMock(),
        budget=budget,
    )

    # The synthesized https://tiktok.com/@alice_backup should appear
    assert any("alice_backup" in du.canonical_url for du in result.discovered_urls)


@patch("pipeline.resolver.run_gemini_discovery_v2")
@patch("pipeline.resolver.classify")
@patch("pipeline.resolver.fetch_seed")
def test_empty_seed_context_raises(mock_fetch, mock_classify, mock_gemini):
    from fetchers.base import EmptyDatasetError
    mock_fetch.side_effect = EmptyDatasetError("login wall")

    budget = BudgetTracker(cap_cents=1000)
    with pytest.raises(EmptyDatasetError):
        resolve_seed(
            handle="empty", platform_hint="instagram",
            supabase=MagicMock(), apify_client=MagicMock(),
            budget=budget,
        )


def test_discovered_url_has_depth_field_default_zero():
    from schemas import DiscoveredUrl
    du = DiscoveredUrl(
        canonical_url="https://example.com",
        platform="other",
        account_type="other",
        destination_class="other",
        reason="rule:test",
    )
    assert du.depth == 0
