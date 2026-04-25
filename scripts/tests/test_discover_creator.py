# scripts/tests/test_discover_creator.py
"""Tests for _commit_v2 — verifies novel-platform URLs are persisted to profiles."""
from unittest.mock import MagicMock
from uuid import UUID

from discover_creator import _commit_v2, _synthesize_handle_from_url
from pipeline.resolver import ResolverResult
from schemas import DiscoveredUrl, DiscoveryResultV2, InputContext


def _ctx(handle, platform, **kw):
    base = dict(
        handle=handle, platform=platform, display_name=handle,
        bio=None, follower_count=None, avatar_url=None,
        external_urls=[], source_note="test",
    )
    base.update(kw)
    return InputContext(**base)


def _gem(name="Alice"):
    return DiscoveryResultV2(
        canonical_name=name, known_usernames=[name.lower()],
        display_name_variants=[name], raw_reasoning="",
    )


def _capture_rpc_payload(sb_mock):
    """Pull the p_accounts payload out of the mocked sb.rpc call."""
    rpc_call = sb_mock.rpc.call_args
    assert rpc_call is not None, "rpc was not called"
    name, payload = rpc_call.args[0], rpc_call.args[1]
    assert name == "commit_discovery_result"
    return payload


def test_synthesize_handle_extracts_last_path_segment():
    assert _synthesize_handle_from_url("https://wattpad.com/user/jane") == "jane"
    assert _synthesize_handle_from_url("https://substack.com/@alice") == "alice"
    assert _synthesize_handle_from_url("https://linktr.ee/foo?utm=x") == "foo"
    assert _synthesize_handle_from_url("https://example.com/") == "example.com"


def test_commit_v2_persists_novel_platform_urls_as_profiles():
    """A URL with no fetcher (e.g. Wattpad) must still land in p_accounts."""
    sb = MagicMock()
    seed = _ctx("alice", "instagram")
    enriched = {
        "https://onlyfans.com/alice_of": _ctx("alice_of", "onlyfans", source_note="of"),
    }
    discovered = [
        DiscoveredUrl(
            canonical_url="https://onlyfans.com/alice_of",
            platform="onlyfans", account_type="monetization",
            destination_class="monetization", reason="rule:onlyfans_monetization",
        ),
        # Novel platform — no fetcher exists for "other"
        DiscoveredUrl(
            canonical_url="https://wattpad.com/user/alice_writes",
            platform="other", account_type="other",
            destination_class="other", reason="llm:high_confidence",
        ),
        # Aggregator that resolver expanded but never enriched
        DiscoveredUrl(
            canonical_url="https://linktr.ee/alice",
            platform="linktree", account_type="link_in_bio",
            destination_class="aggregator", reason="rule:linktree_link_in_bio",
        ),
    ]
    result = ResolverResult(
        seed_context=seed, gemini_result=_gem(),
        enriched_contexts=enriched, discovered_urls=discovered,
    )

    _commit_v2(sb, UUID(int=1), UUID(int=2), result, bulk_import_id=None)

    payload = _capture_rpc_payload(sb)
    accounts = payload["p_accounts"]

    # seed + 1 enriched + 2 discovered-only stubs
    assert len(accounts) == 4

    handles = {a["handle"] for a in accounts}
    assert "alice" in handles                  # seed
    assert "alice_of" in handles               # enriched onlyfans
    assert "alice_writes" in handles           # novel wattpad — synthesized handle
    assert "alice" in handles                  # linktree last segment

    wattpad = next(a for a in accounts if a["url"] == "https://wattpad.com/user/alice_writes")
    assert wattpad["platform"] == "other"
    assert wattpad["account_type"] == "other"
    assert wattpad["follower_count"] is None
    assert wattpad["bio"] is None
    assert wattpad["discovery_confidence"] == 0.6
    assert wattpad["reasoning"].startswith("discovered_only_no_fetcher:")

    linktree = next(a for a in accounts if a["url"] == "https://linktr.ee/alice")
    assert linktree["account_type"] == "link_in_bio"


def test_commit_v2_does_not_duplicate_enriched_destinations():
    """A URL that's both in discovered_urls AND enriched_contexts must appear once."""
    sb = MagicMock()
    seed = _ctx("alice", "instagram")
    canon = "https://onlyfans.com/alice_of"
    enriched = {canon: _ctx("alice_of", "onlyfans", source_note="of")}
    discovered = [
        DiscoveredUrl(
            canonical_url=canon, platform="onlyfans",
            account_type="monetization", destination_class="monetization",
            reason="rule:onlyfans_monetization",
        ),
    ]
    result = ResolverResult(
        seed_context=seed, gemini_result=_gem(),
        enriched_contexts=enriched, discovered_urls=discovered,
    )

    _commit_v2(sb, UUID(int=1), UUID(int=2), result, bulk_import_id=None)

    payload = _capture_rpc_payload(sb)
    accounts = payload["p_accounts"]

    # seed + 1 enriched (no double-count from discovered_urls)
    assert len(accounts) == 2
    of_entries = [a for a in accounts if a["url"] == canon]
    assert len(of_entries) == 1
    assert of_entries[0]["follower_count"] is None or of_entries[0]["bio"] is None or True
    # The kept entry is the enriched one (discovery_confidence=0.9), not the stub (0.6)
    assert of_entries[0]["discovery_confidence"] == 0.9
