# scripts/tests/test_schemas.py
import pytest
from pydantic import ValidationError

from schemas import (
    InputContext,
    ProposedAccount,
    ProposedFunnelEdge,
    DiscoveryResult,
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
