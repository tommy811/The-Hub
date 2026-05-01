"""Regression tests around _commit_v2's dedup + handle-normalization behavior.

These lock in the protections added by T18 + earlier work. If someone
refactors the dedup logic and reintroduces a duplicate-platform-row bug,
these tests fail loudly. The mocked RPC capture lets us assert on the
payload that WOULD be sent to Postgres without actually hitting the DB.
"""
from unittest.mock import MagicMock
from uuid import UUID

import pytest

from discover_creator import _commit_v2, _normalize_handle
from pipeline.resolver import ResolverResult
from schemas import (
    InputContext, DiscoveryResultV2, DiscoveredUrl,
)


def _mk_resolver_result(
    seed_handle: str,
    seed_platform: str = "instagram",
    discovered: list[dict] | None = None,
    enriched: dict[str, dict] | None = None,
) -> ResolverResult:
    """Build a synthetic ResolverResult for testing _commit_v2.

    `discovered` items: list of dicts with at least canonical_url + platform + account_type.
    `enriched` items: {canonical_url: ctx-dict-with-platform-handle-url}.
    """
    seed_ctx = InputContext(
        platform=seed_platform,
        handle=seed_handle,
        bio="test bio",
        external_urls=[],
        follower_count=1000,
    )
    gem = DiscoveryResultV2(
        canonical_name="Test Creator",
        known_usernames=[seed_handle],
        display_name_variants=["Test Creator"],
        primary_niche="test",
        monetization_model="unknown",
        text_mentions=[],
        raw_reasoning="",
    )

    discovered_urls = []
    for d in (discovered or []):
        discovered_urls.append(DiscoveredUrl(
            canonical_url=d["canonical_url"],
            platform=d.get("platform", "other"),
            account_type=d.get("account_type", "other"),
            destination_class=d.get("destination_class", "unknown"),
            reason=d.get("reason", "test"),
            depth=d.get("depth", 1),
        ))

    enriched_contexts = {}
    for canon, ctx_data in (enriched or {}).items():
        enriched_contexts[canon] = InputContext(
            platform=ctx_data["platform"],
            handle=ctx_data["handle"],
            bio=ctx_data.get("bio", ""),
            external_urls=ctx_data.get("external_urls", []),
            follower_count=ctx_data.get("follower_count", 0),
            display_name=ctx_data.get("display_name"),
            source_note=ctx_data.get("source_note"),
        )

    return ResolverResult(
        seed_context=seed_ctx,
        gemini_result=gem,
        enriched_contexts=enriched_contexts,
        discovered_urls=discovered_urls,
    )


def _capture_rpc_payload(sb_mock: MagicMock) -> dict:
    """Return the kwargs dict that was passed to the commit_discovery_result RPC."""
    call = sb_mock.rpc.call_args
    assert call is not None, "RPC was never called"
    assert call.args[0] == "commit_discovery_result"
    return call.args[1]


# === Handle normalization tests ===

def test_normalize_handle_strips_at_prefix():
    assert _normalize_handle("@kira", "tiktok") == "kira"
    assert _normalize_handle("kira", "tiktok") == "kira"


def test_normalize_handle_lowercases_for_tiktok():
    assert _normalize_handle("@Kira", "tiktok") == "kira"
    assert _normalize_handle("KIRA", "tiktok") == "kira"


def test_normalize_handle_lowercases_for_youtube():
    assert _normalize_handle("@Gothgirlnatalie", "youtube") == "gothgirlnatalie"


def test_normalize_handle_idempotent():
    h = _normalize_handle("@Kira", "tiktok")
    assert _normalize_handle(h, "tiktok") == h


def test_normalize_handle_empty():
    assert _normalize_handle("", "tiktok") == ""
    assert _normalize_handle(None, "tiktok") == ""


def test_normalize_handle_strips_whitespace():
    assert _normalize_handle("  @kira  ", "tiktok") == "kira"


def test_normalize_handle_preserves_case_for_unknown_platform():
    # If platform isn't in the case-insensitive set, preserve case
    assert _normalize_handle("@MixedCase", "some_unknown_platform") == "MixedCase"


# === _commit_v2 dedup integration tests ===

def test_commit_v2_dedups_duplicate_canonical_urls(monkeypatch):
    """Two enriched contexts pointing to the same canonical URL should produce
    ONE account row (not two). Higher-confidence/longer-bio context wins."""
    result = _mk_resolver_result(
        seed_handle="kira",
        seed_platform="tiktok",
        enriched={
            "https://tiktok.com/@kira": {
                "platform": "tiktok",
                "handle": "@kira",  # raw form from fetcher
                "follower_count": 2_600_000,
                "bio": "Real Kira",
            },
        },
        discovered=[{
            "canonical_url": "https://tiktok.com/@kira",
            "platform": "tiktok",
            "account_type": "social",
            "depth": 1,
        }],
    )
    sb = MagicMock()
    sb.rpc.return_value.execute.return_value = MagicMock()

    _commit_v2(sb, UUID("00000000-0000-0000-0000-000000000001"),
               UUID("00000000-0000-0000-0000-000000000010"), result,
               bulk_import_id=None)

    payload = _capture_rpc_payload(sb)
    accounts = payload["p_accounts"]
    tt_accounts = [a for a in accounts if a["platform"] == "tiktok"]
    # One TT row — the seed (handle=kira). The enriched ctx for the same URL
    # should be deduped against the seed's URL OR vice versa. Either way: 1 row.
    assert len(tt_accounts) == 1
    assert tt_accounts[0]["handle"] == "kira"  # normalized (no @)


def test_commit_v2_normalizes_at_signs_in_handles(monkeypatch):
    """Different code paths produce @kira, kira, @Kira — _commit_v2 must collapse
    them to a single 'kira' before sending to RPC."""
    result = _mk_resolver_result(
        seed_handle="kira",  # primary, normalized
        seed_platform="tiktok",
        enriched={
            "https://tiktok.com/@kira": {
                "platform": "tiktok",
                "handle": "@Kira",  # capital + @ from fetcher
                "follower_count": 2_600_000,
            },
        },
    )
    sb = MagicMock()
    sb.rpc.return_value.execute.return_value = MagicMock()

    _commit_v2(sb, UUID("00000000-0000-0000-0000-000000000001"),
               UUID("00000000-0000-0000-0000-000000000010"), result,
               bulk_import_id=None)

    payload = _capture_rpc_payload(sb)
    accounts = payload["p_accounts"]
    tt_accounts = [a for a in accounts if a["platform"] == "tiktok"]
    handles = [a["handle"] for a in tt_accounts]
    # No '@' prefix. No capital K. Single row.
    assert all(not h.startswith("@") for h in handles), f"@ prefix leaked: {handles}"
    assert all(h == h.lower() for h in handles), f"capital handle leaked: {handles}"
    assert len(set(handles)) == len(handles), f"duplicate handles: {handles}"


def test_commit_v2_dedups_link_me_vs_fanfix_same_handle(monkeypatch):
    """The Valentina case: link.me/@valentinabacce + app.fanfix.io/@valentinabacce
    both have handle 'valentinabacce' but DIFFERENT platforms ('link_me' vs
    'fanfix'). They should NOT collapse — different (platform, handle) keys.

    This is the inverse of the duplicate-collapse test: we want to verify dedup
    doesn't go too far and merge different-platform rows."""
    result = _mk_resolver_result(
        seed_handle="valentinabacce",
        seed_platform="instagram",
        discovered=[
            {
                "canonical_url": "https://link.me/@valentinabacce",
                "platform": "link_me",
                "account_type": "link_in_bio",
                "depth": 1,
            },
            {
                "canonical_url": "https://app.fanfix.io/@valentinabacce",
                "platform": "fanfix",
                "account_type": "monetization",
                "depth": 1,
            },
        ],
    )
    sb = MagicMock()
    sb.rpc.return_value.execute.return_value = MagicMock()

    _commit_v2(sb, UUID("00000000-0000-0000-0000-000000000001"),
               UUID("00000000-0000-0000-0000-000000000010"), result,
               bulk_import_id=None)

    payload = _capture_rpc_payload(sb)
    accounts = payload["p_accounts"]
    by_platform = {a["platform"]: a for a in accounts}
    assert "link_me" in by_platform, f"link_me row missing: {accounts}"
    assert "fanfix" in by_platform, f"fanfix row missing: {accounts}"
    # Both have the same handle but distinct platforms — DB unique key (ws,pf,handle) keeps them separate
    assert by_platform["link_me"]["handle"] == "valentinabacce"
    assert by_platform["fanfix"]["handle"] == "valentinabacce"


def test_commit_v2_dedups_higher_confidence_wins(monkeypatch):
    """When two rows for the same URL exist (e.g. seed + enriched), the dedup
    should keep the HIGHER-confidence one. Seed gets confidence=1.0; enriched
    secondary gets _confidence_at_depth(1)=0.9."""
    result = _mk_resolver_result(
        seed_handle="primaryuser",
        seed_platform="instagram",
        enriched={
            # Different URL, no collision
            "https://tiktok.com/@secondary": {
                "platform": "tiktok",
                "handle": "secondary",
                "follower_count": 100_000,
            },
        },
        discovered=[
            # Discovered-only with same URL as the seed — should be deduped against seed
            {
                "canonical_url": "https://instagram.com/primaryuser",
                "platform": "instagram",
                "account_type": "social",
                "depth": 1,
                "reason": "discovered_only_no_fetcher: llm:high_confidence",
            },
        ],
    )
    sb = MagicMock()
    sb.rpc.return_value.execute.return_value = MagicMock()

    _commit_v2(sb, UUID("00000000-0000-0000-0000-000000000001"),
               UUID("00000000-0000-0000-0000-000000000010"), result,
               bulk_import_id=None)

    payload = _capture_rpc_payload(sb)
    accounts = payload["p_accounts"]
    ig_accounts = [a for a in accounts if a["platform"] == "instagram"]
    assert len(ig_accounts) == 1, f"expected 1 IG row (seed wins via dedup), got: {ig_accounts}"
    # Confidence should be 1.0 (seed's) — not 0.9 (discovered-only's)
    assert float(ig_accounts[0]["discovery_confidence"]) == 1.0


def test_commit_v2_dedups_youtube_case_variants(monkeypatch):
    """Natalie's YT bug: yt-dlp returns @Gothgirlnatalie (capital G), bulk import
    or recursive enrichment gives @gothgirlnatalie. They should collapse."""
    result = _mk_resolver_result(
        seed_handle="gothgirlnatalie",
        seed_platform="instagram",
        enriched={
            "https://youtube.com/@gothgirlnatalie": {
                "platform": "youtube",
                "handle": "@Gothgirlnatalie",  # capital G from yt-dlp
                "follower_count": 50_000,
                "bio": "yt info",
            },
        },
        discovered=[{
            "canonical_url": "https://youtube.com/@gothgirlnatalie",
            "platform": "youtube",
            "account_type": "social",
            "depth": 1,
        }],
    )
    sb = MagicMock()
    sb.rpc.return_value.execute.return_value = MagicMock()

    _commit_v2(sb, UUID("00000000-0000-0000-0000-000000000001"),
               UUID("00000000-0000-0000-0000-000000000010"), result,
               bulk_import_id=None)

    payload = _capture_rpc_payload(sb)
    accounts = payload["p_accounts"]
    yt_accounts = [a for a in accounts if a["platform"] == "youtube"]
    assert len(yt_accounts) == 1, f"expected 1 YT row, got {yt_accounts}"
    assert yt_accounts[0]["handle"] == "gothgirlnatalie"  # lowercased + @ stripped


def test_commit_v2_funnel_edges_handles_normalized(monkeypatch):
    """Funnel edges' from_handle and to_handle must also be normalized so the
    edge dedup ON CONFLICT works correctly across discovery code paths."""
    result = _mk_resolver_result(
        seed_handle="seedhandle",
        seed_platform="instagram",
        enriched={
            "https://tiktok.com/@target": {
                "platform": "tiktok",
                "handle": "@Target",  # capital + @ from fetcher
                "follower_count": 1000,
            },
        },
    )
    sb = MagicMock()
    sb.rpc.return_value.execute.return_value = MagicMock()

    _commit_v2(sb, UUID("00000000-0000-0000-0000-000000000001"),
               UUID("00000000-0000-0000-0000-000000000010"), result,
               bulk_import_id=None)

    payload = _capture_rpc_payload(sb)
    edges = payload["p_funnel_edges"]
    assert len(edges) >= 1
    edge = edges[0]
    assert not edge["to_handle"].startswith("@"), f"@ leaked into funnel edge: {edge}"
    assert edge["to_handle"] == edge["to_handle"].lower(), f"capital leaked: {edge}"
