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


@patch("pipeline.resolver.fetch_ig.fetch")
@patch("pipeline.resolver.run_gemini_discovery_v2")
@patch("pipeline.resolver.classify")
@patch("pipeline.resolver.fetch_seed")
def test_budget_exhaustion_during_recursion_returns_partial(
    mock_fetch_seed, mock_classify, mock_gemini, mock_ig_fetch,
):
    """Budget is tight: seed fetch (10c) + 1 IG enrich (10c) = 20c.
    Cap = 25c — third IG fetch must be budget-skipped, not crash."""

    mock_fetch_seed.return_value = _mk_ctx(
        handle="seed", platform="instagram",
        external_urls=["https://instagram.com/sec1"],
    )
    chain = iter([
        _mk_ctx(handle="sec1", platform="instagram",
                external_urls=["https://instagram.com/sec2"]),
        _mk_ctx(handle="sec2", platform="instagram",
                external_urls=["https://instagram.com/sec3"]),
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

    budget = BudgetTracker(cap_cents=25)
    result = resolve_seed(
        handle="seed", platform_hint="instagram",
        supabase=MagicMock(), apify_client=MagicMock(),
        budget=budget,
    )

    assert isinstance(result, ResolverResult)
    urls = [du.canonical_url for du in result.discovered_urls]
    assert any("sec1" in u for u in urls)
    assert not any("sec3" in u for u in urls), \
        f"sec3 should not have been fetched: {urls}"


@patch("pipeline.resolver.fetch_of.fetch")
@patch("pipeline.resolver.run_gemini_discovery_v2")
@patch("pipeline.resolver.classify")
@patch("pipeline.resolver.fetch_seed")
def test_terminal_secondary_dead_ends_cleanly(
    mock_fetch_seed, mock_classify, mock_gemini, mock_of_fetch,
):
    """An OnlyFans secondary returns a ctx with no externals + no bio.
    Resolver must end the chain there with no error."""

    mock_fetch_seed.return_value = _mk_ctx(
        handle="seed", platform="instagram",
        external_urls=["https://onlyfans.com/seed"],
    )
    mock_of_fetch.return_value = _mk_ctx(
        handle="seed", platform="onlyfans",
        bio="", external_urls=[],
    )
    mock_classify.return_value = Classification(
        platform="onlyfans", account_type="monetization",
        confidence=1.0, reason="rule:onlyfans_monetization",
    )
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

    assert isinstance(result, ResolverResult)
    canonicals = [du.canonical_url for du in result.discovered_urls]
    assert len(canonicals) == 1
    assert "onlyfans.com/seed" in canonicals[0]
    assert any("onlyfans.com" in k for k in result.enriched_contexts.keys())


def test_run_gemini_bio_mentions_returns_empty_for_empty_bio():
    """The function under unit test, not via resolver."""
    from discover_creator import run_gemini_bio_mentions
    ctx = _mk_ctx(bio="")
    assert run_gemini_bio_mentions(ctx) == []


def test_confidence_at_depth_formula():
    from pipeline.resolver import _confidence_at_depth
    assert _confidence_at_depth(0) == 1.0   # seed
    assert _confidence_at_depth(1) == 0.9   # matches existing hardcoded value
    assert abs(_confidence_at_depth(2) - 0.85) < 1e-9
    assert abs(_confidence_at_depth(5) - 0.7) < 1e-9
    assert _confidence_at_depth(20) == 0.5  # floor


@patch("pipeline.resolver.fetch_ig.fetch")
@patch("pipeline.resolver.run_gemini_discovery_v2")
@patch("pipeline.resolver.classify")
@patch("pipeline.resolver.fetch_seed")
def test_depth_propagates_into_discovered_urls(
    mock_fetch_seed, mock_classify, mock_gemini, mock_ig,
):
    """End-to-end: a depth-2 URL must have depth=2 on its DiscoveredUrl row."""
    mock_fetch_seed.return_value = _mk_ctx(
        handle="seed", platform="instagram",
        external_urls=["https://instagram.com/sec"],
    )
    mock_ig.return_value = _mk_ctx(
        handle="sec", platform="instagram",
        external_urls=["https://onlyfans.com/sec"],
    )
    classifications = iter([
        Classification(platform="instagram", account_type="social",
                       confidence=1.0, reason="rule:instagram_social"),
        Classification(platform="onlyfans", account_type="monetization",
                       confidence=1.0, reason="rule:onlyfans_monetization"),
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

    by_url = {du.canonical_url: du for du in result.discovered_urls}
    ig = next(du for url, du in by_url.items() if "instagram.com/sec" in url)
    of = next(du for url, du in by_url.items() if "onlyfans.com" in url)
    assert ig.depth == 1, f"IG should be depth 1, got {ig.depth}"
    assert of.depth == 2, f"OF should be depth 2, got {of.depth}"


@patch("pipeline.resolver.run_gemini_bio_mentions")
@patch("pipeline.resolver.fetch_ig.fetch")
@patch("pipeline.resolver.run_gemini_discovery_v2")
@patch("pipeline.resolver.classify")
@patch("pipeline.resolver.fetch_seed")
def test_secondary_bio_mentions_followed_when_flag_on(
    mock_fetch_seed, mock_classify, mock_gemini_seed, mock_ig_fetch,
    mock_gemini_bio,
):
    """Secondary IG ctx has bio prose with a @tiktok mention but NO clickable
    external_url. With RECURSIVE_GEMINI=True (default), the mention is followed."""

    mock_fetch_seed.return_value = _mk_ctx(
        handle="seed", platform="instagram",
        external_urls=["https://instagram.com/sec"],
    )
    mock_ig_fetch.return_value = _mk_ctx(
        handle="sec", platform="instagram",
        bio="also follow my tiktok @sec_tt",
        external_urls=[],
    )
    mock_gemini_bio.return_value = [
        TextMention(platform="tiktok", handle="sec_tt", source="enriched_bio"),
    ]
    classifications = iter([
        Classification(platform="instagram", account_type="social",
                       confidence=1.0, reason="rule:instagram_social"),
        Classification(platform="tiktok", account_type="social",
                       confidence=1.0, reason="rule:tiktok_social"),
    ])
    mock_classify.side_effect = lambda *a, **kw: next(classifications)
    mock_gemini_seed.return_value = DiscoveryResultV2(
        canonical_name="Seed", known_usernames=["seed"],
        display_name_variants=["Seed"], raw_reasoning="",
    )

    budget = BudgetTracker(cap_cents=1000)
    result = resolve_seed(
        handle="seed", platform_hint="instagram",
        supabase=MagicMock(), apify_client=MagicMock(),
        budget=budget,
    )

    urls = [du.canonical_url for du in result.discovered_urls]
    assert any("tiktok.com/@sec_tt" in u for u in urls), \
        f"bio-mention TT not followed: {urls}"
    assert mock_gemini_bio.called


@patch("pipeline.resolver.run_gemini_bio_mentions")
@patch("pipeline.resolver.fetch_ig.fetch")
@patch("pipeline.resolver.run_gemini_discovery_v2")
@patch("pipeline.resolver.classify")
@patch("pipeline.resolver.fetch_seed")
def test_recursive_gemini_disabled_skips_bio_mentions(
    mock_fetch_seed, mock_classify, mock_gemini_seed, mock_ig_fetch,
    mock_gemini_bio, monkeypatch,
):
    """With RECURSIVE_GEMINI=False, secondary external_urls still expand
    but bio-mentions extraction is skipped."""
    monkeypatch.setattr("pipeline.resolver.RECURSIVE_GEMINI", False)

    mock_fetch_seed.return_value = _mk_ctx(
        handle="seed", platform="instagram",
        external_urls=["https://instagram.com/sec"],
    )
    mock_ig_fetch.return_value = _mk_ctx(
        handle="sec", platform="instagram",
        bio="also @sec_tt on tiktok",
        external_urls=[],
    )
    mock_classify.return_value = Classification(
        platform="instagram", account_type="social",
        confidence=1.0, reason="rule:instagram_social",
    )
    mock_gemini_seed.return_value = DiscoveryResultV2(
        canonical_name="Seed", known_usernames=["seed"],
        display_name_variants=["Seed"], raw_reasoning="",
    )

    budget = BudgetTracker(cap_cents=1000)
    result = resolve_seed(
        handle="seed", platform_hint="instagram",
        supabase=MagicMock(), apify_client=MagicMock(),
        budget=budget,
    )

    assert not mock_gemini_bio.called, "bio extractor called despite flag=off"
    urls = [du.canonical_url for du in result.discovered_urls]
    assert any("instagram.com/sec" in u for u in urls)
    assert not any("sec_tt" in u for u in urls)


@patch("pipeline.resolver.aggregators_linktree.resolve")
@patch("pipeline.resolver.aggregators_linktree.is_linktree")
@patch("pipeline.resolver.fetch_ig.fetch")
@patch("pipeline.resolver.run_gemini_bio_mentions")
@patch("pipeline.resolver.run_gemini_discovery_v2")
@patch("pipeline.resolver.classify")
@patch("pipeline.resolver.fetch_seed")
def test_kira_shaped_full_funnel_resolution(
    mock_fetch_seed, mock_classify, mock_gemini_seed, mock_gemini_bio,
    mock_ig_fetch, mock_is_linktree, mock_linktree_resolve,
):
    """End-to-end synthetic of the failing Kira case from PROJECT_STATE.

    Seed: TT @kira (no externals, no bio links).
    Gemini text_mentions: @kirapregiato on instagram.
    IG profile: aggregator URL https://tapforallmylinks.com/kira.
    Aggregator children: [OF, telegram_channel].
    Expected: all 4 destinations recorded; OF + telegram are terminal.
    """
    mock_fetch_seed.return_value = _mk_ctx(
        handle="kira", platform="tiktok", bio="more on @kirapregiato",
        external_urls=[],
    )
    mock_ig_fetch.return_value = _mk_ctx(
        handle="kirapregiato", platform="instagram",
        bio="", external_urls=["https://tapforallmylinks.com/kira"],
    )
    mock_is_linktree.return_value = False  # not linktr.ee — falls through to custom_domain

    with patch("pipeline.resolver.aggregators_custom.resolve") as mock_custom_resolve:
        mock_custom_resolve.return_value = [
            "https://onlyfans.com/kira",
            "https://t.me/kirachannel",
        ]

        classifications = iter([
            Classification(platform="instagram", account_type="social",
                           confidence=1.0, reason="rule:instagram_social"),
            Classification(platform="custom_domain", account_type="link_in_bio",
                           confidence=1.0, reason="rule:custom_domain_aggregator"),
            Classification(platform="onlyfans", account_type="monetization",
                           confidence=1.0, reason="rule:onlyfans_monetization"),
            Classification(platform="telegram_channel", account_type="messaging",
                           confidence=1.0, reason="rule:telegram_messaging"),
        ])
        mock_classify.side_effect = lambda *a, **kw: next(classifications)
        mock_gemini_seed.return_value = DiscoveryResultV2(
            canonical_name="Kira", known_usernames=["kira", "kirapregiato"],
            display_name_variants=["Kira"],
            text_mentions=[TextMention(platform="instagram", handle="kirapregiato")],
            raw_reasoning="",
        )
        mock_gemini_bio.return_value = []  # IG bio empty, no mentions

        budget = BudgetTracker(cap_cents=1000)
        result = resolve_seed(
            handle="kira", platform_hint="tiktok",
            supabase=MagicMock(), apify_client=MagicMock(),
            budget=budget,
        )

    by_platform = {du.platform: du for du in result.discovered_urls}
    assert "instagram" in by_platform
    assert "custom_domain" in by_platform
    assert "onlyfans" in by_platform
    assert "telegram_channel" in by_platform

    # Depth: IG depth=1 (text_mention from seed), aggregator depth=2, children depth=3.
    assert by_platform["instagram"].depth == 1
    assert by_platform["custom_domain"].depth == 2
    assert by_platform["onlyfans"].depth == 3
    assert by_platform["telegram_channel"].depth == 3

    # IG was enriched (we mocked fetch_ig.fetch); aggregator + terminals were not.
    assert any("instagram.com/kirapregiato" in k
               for k in result.enriched_contexts.keys())


def test_resolver_module_exposes_fetch_highlights_wrapper():
    """The resolver re-exports fetch_highlights so tests can patch at this site."""
    from pipeline import resolver
    assert hasattr(resolver, "fetch_highlights"), \
        "pipeline.resolver must export fetch_highlights for test patching"


def test_resolver_module_exposes_highlights_enabled_constant():
    from pipeline import resolver
    assert hasattr(resolver, "HIGHLIGHTS_ENABLED")
    assert isinstance(resolver.HIGHLIGHTS_ENABLED, bool)


def test_resolver_module_exposes_highlights_cost_cents_constant():
    from pipeline import resolver
    assert hasattr(resolver, "HIGHLIGHTS_COST_CENTS")
    assert isinstance(resolver.HIGHLIGHTS_COST_CENTS, int)
    assert resolver.HIGHLIGHTS_COST_CENTS > 0


@patch("pipeline.resolver.fetch_highlights")
@patch("pipeline.resolver.run_gemini_bio_mentions")
@patch("pipeline.resolver.fetch_ig.fetch")
@patch("pipeline.resolver.run_gemini_discovery_v2")
@patch("pipeline.resolver.classify")
@patch("pipeline.resolver.fetch_seed")
def test_highlight_link_sticker_lands_in_discovered_urls(
    mock_fetch_seed, mock_classify, mock_gemini_seed, mock_ig_fetch,
    mock_gemini_bio, mock_fetch_highlights, monkeypatch,
):
    """Depth-1 IG profile has a highlight with an OF link sticker.
    The OF URL must land in discovered_urls at depth 2."""
    monkeypatch.setattr("pipeline.resolver.HIGHLIGHTS_ENABLED", True)
    from schemas import HighlightLink

    mock_fetch_seed.return_value = _mk_ctx(
        handle="seed", platform="instagram",
        external_urls=["https://instagram.com/sec"],
    )
    # Depth-1 IG profile: empty bio, no externals — only highlights are the source
    mock_ig_fetch.return_value = _mk_ctx(
        handle="sec", platform="instagram",
        bio="", external_urls=[],
    )
    mock_gemini_bio.return_value = []  # no bio mentions
    mock_fetch_highlights.return_value = [
        HighlightLink(
            url="https://onlyfans.com/sec",
            source="highlight_link_sticker",
        ),
    ]

    classifications = iter([
        Classification(platform="instagram", account_type="social",
                       confidence=1.0, reason="rule:instagram_social"),
        Classification(platform="onlyfans", account_type="monetization",
                       confidence=1.0, reason="rule:onlyfans_monetization"),
    ])
    mock_classify.side_effect = lambda *a, **kw: next(classifications)
    mock_gemini_seed.return_value = DiscoveryResultV2(
        canonical_name="Seed", known_usernames=["seed"],
        display_name_variants=["Seed"], raw_reasoning="",
    )

    budget = BudgetTracker(cap_cents=1000)
    result = resolve_seed(
        handle="seed", platform_hint="instagram",
        supabase=MagicMock(), apify_client=MagicMock(),
        budget=budget,
    )

    by_url = {du.canonical_url: du for du in result.discovered_urls}
    of = next((du for url, du in by_url.items() if "onlyfans.com/sec" in url), None)
    assert of is not None, \
        f"highlight-surfaced OF URL missing from {list(by_url.keys())}"
    assert of.depth == 2, f"OF should be depth 2, got {of.depth}"
    # And fetch_highlights was actually called (for the depth-1 IG)
    assert mock_fetch_highlights.called
    # And NOT called for the seed (depth 0)
    assert mock_fetch_highlights.call_count == 1


@patch("pipeline.resolver.fetch_highlights")
@patch("pipeline.resolver.run_gemini_bio_mentions")
@patch("pipeline.resolver.fetch_ig.fetch")
@patch("pipeline.resolver.run_gemini_discovery_v2")
@patch("pipeline.resolver.classify")
@patch("pipeline.resolver.fetch_seed")
def test_highlights_not_called_for_seed_or_non_ig(
    mock_fetch_seed, mock_classify, mock_gemini_seed, mock_ig_fetch,
    mock_gemini_bio, mock_fetch_highlights, monkeypatch,
):
    """Seed (depth 0) never triggers highlights. A TT secondary (depth 1) doesn't either."""
    monkeypatch.setattr("pipeline.resolver.HIGHLIGHTS_ENABLED", True)
    mock_fetch_seed.return_value = _mk_ctx(
        handle="seed", platform="instagram",
        external_urls=["https://tiktok.com/@sec_tt"],  # depth-1 TT
    )
    # Mock the TT fetcher so the secondary enriches successfully
    with patch("pipeline.resolver.fetch_tt.fetch") as mock_tt_fetch:
        mock_tt_fetch.return_value = _mk_ctx(
            handle="sec_tt", platform="tiktok",
            bio="", external_urls=[],
        )
        mock_gemini_bio.return_value = []
        mock_classify.return_value = Classification(
            platform="tiktok", account_type="social",
            confidence=1.0, reason="rule:tiktok_social",
        )
        mock_gemini_seed.return_value = DiscoveryResultV2(
            canonical_name="Seed", known_usernames=["seed"],
            display_name_variants=["Seed"], raw_reasoning="",
        )
        budget = BudgetTracker(cap_cents=1000)
        resolve_seed(
            handle="seed", platform_hint="instagram",
            supabase=MagicMock(), apify_client=MagicMock(),
            budget=budget,
        )

    # Highlights branch must never have fired:
    # - seed is depth 0 (skipped by `depth >= 1` gate)
    # - the only secondary is TT (skipped by `ctx.platform == "instagram"` gate)
    assert not mock_fetch_highlights.called, \
        "fetch_highlights was called despite no IG depth-1 profile"


@patch("pipeline.resolver.fetch_highlights")
@patch("pipeline.resolver.run_gemini_bio_mentions")
@patch("pipeline.resolver.fetch_ig.fetch")
@patch("pipeline.resolver.run_gemini_discovery_v2")
@patch("pipeline.resolver.classify")
@patch("pipeline.resolver.fetch_seed")
def test_highlights_failure_does_not_crash_resolver(
    mock_fetch_seed, mock_classify, mock_gemini_seed, mock_ig_fetch,
    mock_gemini_bio, mock_fetch_highlights, monkeypatch,
):
    """When fetch_highlights raises, resolver completes cleanly. Other branches (
    external_urls, bio_mentions) still surface their URLs."""
    monkeypatch.setattr("pipeline.resolver.HIGHLIGHTS_ENABLED", True)
    mock_fetch_seed.return_value = _mk_ctx(
        handle="seed", platform="instagram",
        external_urls=["https://instagram.com/sec"],
    )
    mock_ig_fetch.return_value = _mk_ctx(
        handle="sec", platform="instagram",
        bio="follow @sec_tt on tiktok",
        external_urls=["https://onlyfans.com/sec"],
    )
    # bio_mentions returns something — must still surface
    mock_gemini_bio.return_value = [
        TextMention(platform="tiktok", handle="sec_tt", source="enriched_bio"),
    ]
    # Highlights fetcher blows up
    mock_fetch_highlights.side_effect = RuntimeError("apify timeout")

    classifications = iter([
        Classification(platform="instagram", account_type="social",
                       confidence=1.0, reason="rule:instagram_social"),
        Classification(platform="onlyfans", account_type="monetization",
                       confidence=1.0, reason="rule:onlyfans_monetization"),
        Classification(platform="tiktok", account_type="social",
                       confidence=1.0, reason="rule:tiktok_social"),
    ])
    mock_classify.side_effect = lambda *a, **kw: next(classifications)
    mock_gemini_seed.return_value = DiscoveryResultV2(
        canonical_name="Seed", known_usernames=["seed"],
        display_name_variants=["Seed"], raw_reasoning="",
    )

    budget = BudgetTracker(cap_cents=1000)
    result = resolve_seed(
        handle="seed", platform_hint="instagram",
        supabase=MagicMock(), apify_client=MagicMock(),
        budget=budget,
    )

    # No exception leaked — resolver returned cleanly.
    assert isinstance(result, ResolverResult)
    urls = [du.canonical_url for du in result.discovered_urls]
    # external_urls branch landed
    assert any("onlyfans.com/sec" in u for u in urls)
    # bio_mentions branch landed
    assert any("tiktok.com/@sec_tt" in u for u in urls)


@patch("pipeline.resolver.fetch_highlights")
@patch("pipeline.resolver.run_gemini_bio_mentions")
@patch("pipeline.resolver.fetch_ig.fetch")
@patch("pipeline.resolver.run_gemini_discovery_v2")
@patch("pipeline.resolver.classify")
@patch("pipeline.resolver.fetch_seed")
def test_highlights_disabled_skips_branch(
    mock_fetch_seed, mock_classify, mock_gemini_seed, mock_ig_fetch,
    mock_gemini_bio, mock_fetch_highlights, monkeypatch,
):
    """HIGHLIGHTS_ENABLED=False — fetch_highlights is never called even for IG depth 1."""
    monkeypatch.setattr("pipeline.resolver.HIGHLIGHTS_ENABLED", False)

    mock_fetch_seed.return_value = _mk_ctx(
        handle="seed", platform="instagram",
        external_urls=["https://instagram.com/sec"],
    )
    mock_ig_fetch.return_value = _mk_ctx(
        handle="sec", platform="instagram", bio="", external_urls=[],
    )
    mock_gemini_bio.return_value = []
    mock_classify.return_value = Classification(
        platform="instagram", account_type="social",
        confidence=1.0, reason="rule:instagram_social",
    )
    mock_gemini_seed.return_value = DiscoveryResultV2(
        canonical_name="Seed", known_usernames=["seed"],
        display_name_variants=["Seed"], raw_reasoning="",
    )

    budget = BudgetTracker(cap_cents=1000)
    resolve_seed(
        handle="seed", platform_hint="instagram",
        supabase=MagicMock(), apify_client=MagicMock(),
        budget=budget,
    )
    assert not mock_fetch_highlights.called, \
        "highlights branch fired despite HIGHLIGHTS_ENABLED=False"
    # Budget should NOT have been debited for highlights (seed fetch 10c + IG
    # enrich 10c = 20c; if highlights had fired we'd see ≥25c).
    assert budget.spent_cents <= 20, \
        f"budget debited for highlights: spent={budget.spent_cents}c"
