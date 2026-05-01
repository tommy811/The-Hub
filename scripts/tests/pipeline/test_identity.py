# scripts/tests/pipeline/test_identity.py
from dataclasses import dataclass
from unittest.mock import MagicMock, patch
import pytest
from pipeline.identity import (
    ProfileFingerprint,
    score_pair,
    find_candidates_for_profile,
    IdentityVerdict,
)


def _fp(profile_id="p1", handle="alice", platform="instagram", bio="",
        display_name="Alice", avatar_url=None, destination_urls=None,
        destination_classes=None, niche=None):
    return ProfileFingerprint(
        profile_id=profile_id,
        handle=handle,
        platform=platform,
        bio=bio,
        display_name=display_name,
        avatar_url=avatar_url,
        destination_urls=list(destination_urls or []),
        destination_classes=dict(destination_classes or {}),
        niche=niche,
    )


class TestRule1SharedMonetization:
    def test_shared_onlyfans_url_auto_merges(self):
        a = _fp(profile_id="a", destination_urls=["https://onlyfans.com/alice"],
                destination_classes={"https://onlyfans.com/alice": "monetization"})
        b = _fp(profile_id="b", destination_urls=["https://onlyfans.com/alice"],
                destination_classes={"https://onlyfans.com/alice": "monetization"})
        verdict = score_pair(a, b, clip_fn=None)
        assert verdict.action == "auto_merge"
        assert verdict.confidence == 1.0
        assert "shared_monetization" in verdict.reason
        assert verdict.evidence["shared_url"] == "https://onlyfans.com/alice"


class TestRule2SharedAggregator:
    def test_shared_linktree_auto_merges(self):
        a = _fp(profile_id="a", destination_urls=["https://linktr.ee/alice"],
                destination_classes={"https://linktr.ee/alice": "aggregator"})
        b = _fp(profile_id="b", destination_urls=["https://linktr.ee/alice"],
                destination_classes={"https://linktr.ee/alice": "aggregator"})
        verdict = score_pair(a, b, clip_fn=None)
        assert verdict.action == "auto_merge"
        assert "shared_aggregator" in verdict.reason


class TestRule3BioCrossMention:
    def test_bio_mentions_other_handle(self):
        a = _fp(profile_id="a", handle="alice", platform="instagram",
                bio="also on tiktok @bob_backup", destination_urls=[])
        b = _fp(profile_id="b", handle="bob_backup", platform="tiktok",
                destination_urls=[])
        verdict = score_pair(a, b, clip_fn=None)
        assert verdict.action == "merge_candidate"
        assert verdict.confidence == 0.8
        assert "bio_cross_mention" in verdict.reason


class TestRule4HandleMatchPlusClip:
    def test_exact_handle_plus_high_clip_is_candidate(self):
        a = _fp(profile_id="a", handle="alice", platform="instagram",
                avatar_url="https://cdn/a.jpg")
        b = _fp(profile_id="b", handle="alice", platform="tiktok",
                avatar_url="https://cdn/b.jpg")
        # CLIP returns 0.9 similarity
        verdict = score_pair(a, b, clip_fn=lambda _a, _b: 0.9)
        assert verdict.action == "merge_candidate"
        assert verdict.confidence == 0.7
        assert "handle_match_clip" in verdict.reason

    def test_handle_match_low_clip_is_discard(self):
        a = _fp(profile_id="a", handle="alice", platform="instagram",
                avatar_url="https://cdn/a.jpg")
        b = _fp(profile_id="b", handle="alice", platform="tiktok",
                avatar_url="https://cdn/b.jpg")
        verdict = score_pair(a, b, clip_fn=lambda _a, _b: 0.3)
        assert verdict.action == "discard"


class TestDiscardCases:
    def test_shared_affiliate_domain_discarded(self):
        a = _fp(profile_id="a", destination_urls=["https://amazon.com/dp/B01"],
                destination_classes={"https://amazon.com/dp/B01": "other"})
        b = _fp(profile_id="b", destination_urls=["https://amazon.com/dp/B01"],
                destination_classes={"https://amazon.com/dp/B01": "other"})
        verdict = score_pair(a, b, clip_fn=None)
        assert verdict.action == "discard"

    def test_no_signals_discards(self):
        a = _fp(profile_id="a", handle="alice")
        b = _fp(profile_id="b", handle="bob")
        verdict = score_pair(a, b, clip_fn=None)
        assert verdict.action == "discard"


class TestFindCandidates:
    def test_queries_inverted_index(self):
        """find_candidates_for_profile looks up profile_destination_links on
        the profile's monetization+aggregator URLs, returning peer profile_ids."""
        sb = MagicMock()
        sb.table.return_value.select.return_value.eq.return_value.in_.return_value\
            .neq.return_value.execute.return_value.data = [
                {"profile_id": "other-1", "canonical_url": "https://onlyfans.com/alice"},
                {"profile_id": "other-2", "canonical_url": "https://onlyfans.com/alice"},
            ]

        fp = _fp(profile_id="me",
                 destination_urls=["https://onlyfans.com/alice"],
                 destination_classes={"https://onlyfans.com/alice": "monetization"})

        candidates = find_candidates_for_profile(fp, workspace_id="ws-1", supabase=sb)

        assert set(candidates) == {"other-1", "other-2"}
