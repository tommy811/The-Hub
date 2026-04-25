# scripts/tests/test_schemas.py
import pytest
from pydantic import ValidationError

from schemas import (
    InputContext,
    ProposedAccount,
    ProposedFunnelEdge,
    DiscoveryResult,
    DiscoveredUrl,
    TextMention,
    DiscoveryResultV2,
    PLATFORM_VALUES,
)


class TestProposedAccountPlatform:
    def test_accepts_instagram(self):
        acc = ProposedAccount(
            account_type="social",
            platform="instagram",
            discovery_confidence=0.9,
            reasoning="test",
        )
        assert acc.platform == "instagram"

    def test_accepts_patreon(self):
        acc = ProposedAccount(
            account_type="monetization",
            platform="patreon",
            discovery_confidence=0.9,
            reasoning="test",
        )
        assert acc.platform == "patreon"

    def test_rejects_bogus_platform(self):
        with pytest.raises(ValidationError) as exc:
            ProposedAccount(
                account_type="social",
                platform="mastodon",
                discovery_confidence=0.9,
                reasoning="test",
            )
        assert "platform" in str(exc.value)


class TestProposedFunnelEdge:
    def test_rejects_bogus_edge_type(self):
        with pytest.raises(ValidationError):
            ProposedFunnelEdge(
                from_handle="a",
                from_platform="instagram",
                to_handle="b",
                to_platform="tiktok",
                edge_type="magic_portal",
                confidence=0.9,
            )

    def test_accepts_link_in_bio(self):
        edge = ProposedFunnelEdge(
            from_handle="a",
            from_platform="instagram",
            to_handle="b",
            to_platform="onlyfans",
            edge_type="link_in_bio",
            confidence=0.95,
        )
        assert edge.edge_type == "link_in_bio"


class TestInputContext:
    def test_empty_external_urls_default(self):
        ctx = InputContext(handle="x", platform="instagram")
        assert ctx.external_urls == []

    def test_empty_flag_true_when_no_bio_and_no_followers(self):
        ctx = InputContext(handle="x", platform="instagram")
        assert ctx.is_empty() is True

    def test_empty_flag_false_when_bio_present(self):
        ctx = InputContext(handle="x", platform="instagram", bio="hi")
        assert ctx.is_empty() is False

    def test_empty_flag_false_when_followers_present(self):
        ctx = InputContext(handle="x", platform="instagram", follower_count=100)
        assert ctx.is_empty() is False


class TestPlatformValuesCompleteness:
    def test_includes_patreon(self):
        assert "patreon" in PLATFORM_VALUES

    def test_matches_documented_db_enum(self):
        # Full list from PROJECT_STATE §5, excluding 'other'
        expected = {
            "instagram", "tiktok", "youtube", "patreon", "twitter", "linkedin",
            "facebook", "onlyfans", "fanvue", "fanplace", "amazon_storefront",
            "tiktok_shop", "linktree", "beacons", "custom_domain",
            "telegram_channel", "telegram_cupidbot", "other",
        }
        assert set(PLATFORM_VALUES) == expected


# --- v2 additions ---


class TestDiscoveredUrl:
    def test_accepts_valid_monetization(self):
        du = DiscoveredUrl(
            canonical_url="https://onlyfans.com/alice",
            platform="onlyfans", account_type="monetization",
            destination_class="monetization", reason="rule:onlyfans_monetization",
        )
        assert du.platform == "onlyfans"

    def test_rejects_invalid_platform(self):
        with pytest.raises(ValidationError):
            DiscoveredUrl(
                canonical_url="x", platform="bogus", account_type="social",
                destination_class="social", reason="x",
            )

    def test_rejects_invalid_destination_class(self):
        with pytest.raises(ValidationError):
            DiscoveredUrl(
                canonical_url="x", platform="instagram", account_type="social",
                destination_class="bogus", reason="x",
            )


class TestTextMention:
    def test_default_source_is_seed_bio(self):
        tm = TextMention(platform="instagram", handle="alice")
        assert tm.source == "seed_bio"

    def test_rejects_unknown_platform(self):
        with pytest.raises(ValidationError):
            TextMention(platform="bogus", handle="alice")


class TestDiscoveryResultV2:
    def test_minimal(self):
        r = DiscoveryResultV2(
            canonical_name="Alice",
            known_usernames=["alice"],
            display_name_variants=["Alice"],
            raw_reasoning="short",
        )
        assert r.monetization_model == "unknown"
        assert r.text_mentions == []

    def test_no_longer_has_proposed_accounts_or_edges(self):
        # The v1 DiscoveryResult required proposed_accounts/proposed_funnel_edges.
        # V2 omits them entirely — classifier + resolver own those.
        r = DiscoveryResultV2(
            canonical_name="Alice", known_usernames=["alice"],
            display_name_variants=["Alice"], raw_reasoning="x",
        )
        assert not hasattr(r, "proposed_accounts")
        assert not hasattr(r, "proposed_funnel_edges")


class TestHighlightLink:
    def test_link_sticker_minimal(self):
        from schemas import HighlightLink
        link = HighlightLink(
            url="https://onlyfans.com/kira",
            source="highlight_link_sticker",
        )
        assert link.url == "https://onlyfans.com/kira"
        assert link.source == "highlight_link_sticker"
        assert link.platform is None  # only relevant for caption mentions
        assert link.handle is None
        assert link.source_text is None  # optional context

    def test_caption_mention_with_platform_handle(self):
        from schemas import HighlightLink
        link = HighlightLink(
            url="",  # synthesized later
            source="highlight_caption_mention",
            platform="tiktok",
            handle="kira_tt",
            source_text="follow my tt @kira_tt",
        )
        assert link.platform == "tiktok"
        assert link.handle == "kira_tt"

    def test_rejects_unknown_source(self):
        from schemas import HighlightLink
        from pydantic import ValidationError
        import pytest as _pt
        with _pt.raises(ValidationError):
            HighlightLink(url="https://x", source="not_a_real_source")
