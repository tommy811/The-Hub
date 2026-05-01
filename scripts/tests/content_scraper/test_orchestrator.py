"""Tests for the content scraper orchestrator.

Mocks fetchers + supabase RPCs; asserts the per-profile sequence
commit_scrape_result → flag_outliers → profile_metrics_snapshots is
emitted in the right order with the right inputs.
"""
import asyncio
from datetime import datetime, timezone
from unittest.mock import MagicMock, call
from uuid import uuid4

import pytest

from content_scraper.fetchers.base import FetchBatchResult
from content_scraper.normalizer import NormalizedPost, PlatformMetrics
from content_scraper.orchestrator import (
    ScrapeOrchestrator, ProfileScope, ScrapeRunSummary, _profile_avatar_from_posts,
)


def _make_post(profile_id, post_id="p1", view_count=100) -> NormalizedPost:
    return NormalizedPost(
        profile_id=profile_id,
        platform="instagram",
        platform_post_id=post_id,
        post_url=f"https://instagram.com/p/{post_id}",
        post_type="reel",
        caption="x",
        hook_text="x",
        posted_at=datetime(2026, 4, 27, tzinfo=timezone.utc),
        view_count=view_count,
        like_count=10,
        comment_count=1,
        platform_metrics=PlatformMetrics(),
        raw_apify_payload={},
    )


def test_profile_avatar_from_posts_uses_platform_metrics_first():
    pid = uuid4()
    post = _make_post(
        pid,
        post_id="avatar",
    ).model_copy(update={
        "platform_metrics": PlatformMetrics(author_avatar_url="https://cdn.example/avatar.jpg"),
    })

    assert _profile_avatar_from_posts([post]) == "https://cdn.example/avatar.jpg"


def test_profile_avatar_from_posts_reads_tiktok_author_meta():
    pid = uuid4()
    post = _make_post(pid, post_id="tt-avatar").model_copy(update={
        "platform": "tiktok",
        "post_type": "tiktok_video",
        "raw_apify_payload": {"authorMeta": {"avatar": "https://p.tiktokcdn.com/a.jpg"}},
    })

    assert _profile_avatar_from_posts([post]) == "https://p.tiktokcdn.com/a.jpg"


def _async_return(value):
    """Helper: return an awaitable that resolves to `value`."""
    async def _r(*args, **kwargs):
        return value
    return _r()


def _supabase_mock_with_outlier_query(
    outlier_count: int = 0,
    rows: list[dict] | None = None,
) -> MagicMock:
    """Build a supabase mock where the post-flag query returns `outlier_count` outlier rows."""
    sb = MagicMock()
    rpc_chain = MagicMock()
    rpc_chain.execute.return_value = MagicMock(data={"posts_upserted": 1, "snapshots_written": 1})
    sb.rpc.return_value = rpc_chain

    table_chain = MagicMock()
    table_chain.upsert.return_value = table_chain
    table_chain.insert.return_value = table_chain
    table_chain.update.return_value = table_chain
    table_chain.eq.return_value = table_chain
    table_chain.execute.return_value = MagicMock(data=[{}])

    sc_select_chain = MagicMock()
    sc_select_chain.in_.return_value = sc_select_chain
    sc_select_chain.eq.return_value = sc_select_chain
    sc_select_chain.execute.return_value = MagicMock(
        data=rows if rows is not None else [
            {"view_count": 100, "is_outlier": i < outlier_count, "engagement_rate": 0.05}
            for i in range(5)
        ]
    )

    profiles_chain = MagicMock()
    profiles_chain.select.return_value = profiles_chain
    profiles_chain.eq.return_value = profiles_chain
    profiles_chain.single.return_value = profiles_chain
    profiles_chain.execute.return_value = MagicMock(data={"follower_count": 1000})

    def table_factory(name):
        if name == "profile_metrics_snapshots":
            return table_chain
        if name == "scrape_runs":
            return table_chain
        if name == "scraped_content":
            sc = MagicMock()
            sc.select.return_value = sc_select_chain
            return sc
        if name == "profiles":
            profiles_chain.update.return_value = profiles_chain
            return profiles_chain
        return MagicMock()

    sb.table.side_effect = table_factory
    return sb


def test_profile_snapshot_median_ignores_missing_static_view_counts():
    pid = uuid4()
    post = _make_post(pid)
    rows = [
        {"view_count": 0, "is_outlier": False, "engagement_rate": 0.10},
        {"view_count": 0, "is_outlier": False, "engagement_rate": 0.12},
        {"view_count": 100, "is_outlier": False, "engagement_rate": 0.05},
        {"view_count": 200, "is_outlier": False, "engagement_rate": 0.06},
        {"view_count": 300, "is_outlier": False, "engagement_rate": 0.07},
    ]
    sb = _supabase_mock_with_outlier_query(rows=rows)
    orch = ScrapeOrchestrator(
        supabase=sb,
        ig_fetcher=MagicMock(),
        tt_fetcher=MagicMock(),
        dead_letter_path=None,
    )

    asyncio.run(orch._write_profile_snapshot(
        ProfileScope(profile_id=pid, handle="x", platform="instagram", creator_id=uuid4(), workspace_id=uuid4()),
        [post],
        ScrapeRunSummary(),
    ))

    snapshot_chain = sb.table("profile_metrics_snapshots")
    snapshot_row = snapshot_chain.upsert.call_args.args[0]
    assert snapshot_row["median_views"] == 200


def test_orchestrator_calls_commit_then_flag_outliers_per_profile():
    pid = uuid4()
    post = _make_post(pid)
    ig_fetcher = MagicMock()
    ig_fetcher.fetch = MagicMock(return_value=_async_return(FetchBatchResult(
        posts_by_profile={pid: [post]},
        actor_id="apify/instagram-scraper",
        apify_run_id="run_1",
        dataset_id="ds_1",
    )))
    tt_fetcher = MagicMock()
    tt_fetcher.fetch = MagicMock(return_value=_async_return(FetchBatchResult(posts_by_profile={}, actor_id="clockworks/tiktok-scraper")))

    sb = _supabase_mock_with_outlier_query()
    orch = ScrapeOrchestrator(
        supabase=sb,
        ig_fetcher=ig_fetcher,
        tt_fetcher=tt_fetcher,
        dead_letter_path=None,
    )
    asyncio.run(orch.run([
        ProfileScope(profile_id=pid, handle="x", platform="instagram", creator_id=uuid4(), workspace_id=uuid4()),
    ], since=datetime(2026, 4, 1, tzinfo=timezone.utc)))

    rpc_calls = sb.rpc.call_args_list
    assert any(c.args[0] == "commit_scrape_result" for c in rpc_calls)
    assert any(c.args[0] == "flag_outliers" for c in rpc_calls)

    rpc_names = [c.args[0] for c in rpc_calls]
    commit_idx = rpc_names.index("commit_scrape_result")
    flag_idx = rpc_names.index("flag_outliers")
    assert commit_idx < flag_idx


def test_orchestrator_skips_profiles_with_zero_posts():
    pid = uuid4()
    ig_fetcher = MagicMock()
    ig_fetcher.fetch = MagicMock(return_value=_async_return(FetchBatchResult(posts_by_profile={}, actor_id="apify/instagram-scraper")))
    tt_fetcher = MagicMock()
    tt_fetcher.fetch = MagicMock(return_value=_async_return(FetchBatchResult(posts_by_profile={}, actor_id="clockworks/tiktok-scraper")))

    sb = _supabase_mock_with_outlier_query()
    orch = ScrapeOrchestrator(
        supabase=sb,
        ig_fetcher=ig_fetcher,
        tt_fetcher=tt_fetcher,
        dead_letter_path=None,
    )
    asyncio.run(orch.run([
        ProfileScope(profile_id=pid, handle="x", platform="instagram", creator_id=uuid4(), workspace_id=uuid4()),
    ], since=datetime(2026, 4, 1, tzinfo=timezone.utc)))

    sb.rpc.assert_not_called()


def test_orchestrator_groups_by_platform_and_calls_each_fetcher_once():
    pid_ig, pid_tt = uuid4(), uuid4()
    post_ig = _make_post(pid_ig, post_id="ig1")
    post_tt = _make_post(pid_tt, post_id="tt1")
    post_tt = post_tt.model_copy(update={"platform": "tiktok", "post_type": "tiktok_video"})

    ig_fetcher = MagicMock()
    ig_fetcher.fetch = MagicMock(return_value=_async_return(FetchBatchResult(posts_by_profile={pid_ig: [post_ig]}, actor_id="apify/instagram-scraper")))
    tt_fetcher = MagicMock()
    tt_fetcher.fetch = MagicMock(return_value=_async_return(FetchBatchResult(posts_by_profile={pid_tt: [post_tt]}, actor_id="clockworks/tiktok-scraper")))

    sb = _supabase_mock_with_outlier_query()
    orch = ScrapeOrchestrator(
        supabase=sb, ig_fetcher=ig_fetcher, tt_fetcher=tt_fetcher,
        dead_letter_path=None,
    )
    asyncio.run(orch.run([
        ProfileScope(profile_id=pid_ig, handle="x", platform="instagram", creator_id=uuid4(), workspace_id=uuid4()),
        ProfileScope(profile_id=pid_tt, handle="y", platform="tiktok", creator_id=uuid4(), workspace_id=uuid4()),
    ], since=datetime(2026, 4, 1, tzinfo=timezone.utc)))

    ig_fetcher.fetch.assert_called_once()
    tt_fetcher.fetch.assert_called_once()


import json
import tempfile
from pathlib import Path


def test_orchestrator_dead_letters_rpc_failure_and_continues():
    pid_a, pid_b = uuid4(), uuid4()
    post_a = _make_post(pid_a, "a1")
    post_b = _make_post(pid_b, "b1")
    ig_fetcher = MagicMock()
    ig_fetcher.fetch = MagicMock(return_value=_async_return(FetchBatchResult(posts_by_profile={pid_a: [post_a], pid_b: [post_b]}, actor_id="apify/instagram-scraper")))
    tt_fetcher = MagicMock()
    tt_fetcher.fetch = MagicMock(return_value=_async_return(FetchBatchResult(posts_by_profile={}, actor_id="clockworks/tiktok-scraper")))

    sb = _supabase_mock_with_outlier_query()

    def rpc_side_effect(name, args):
        chain = MagicMock()
        if name == "commit_scrape_result" and args["p_profile_id"] == str(pid_b):
            chain.execute.side_effect = RuntimeError("rpc exploded")
        else:
            chain.execute.return_value = MagicMock(data={"posts_upserted": 1, "snapshots_written": 1})
        return chain
    sb.rpc.side_effect = rpc_side_effect

    with tempfile.TemporaryDirectory() as tmpdir:
        dl_path = str(Path(tmpdir) / "dead_letter.jsonl")
        orch = ScrapeOrchestrator(
            supabase=sb, ig_fetcher=ig_fetcher, tt_fetcher=tt_fetcher,
            dead_letter_path=dl_path,
        )
        summary = asyncio.run(orch.run([
            ProfileScope(profile_id=pid_a, handle="a", platform="instagram", creator_id=uuid4(), workspace_id=uuid4()),
            ProfileScope(profile_id=pid_b, handle="b", platform="instagram", creator_id=uuid4(), workspace_id=uuid4()),
        ], since=datetime(2026, 4, 1, tzinfo=timezone.utc)))

        assert summary.profiles_scraped == 1
        assert summary.failures == 1

        dl_lines = Path(dl_path).read_text().strip().splitlines()
        assert len(dl_lines) == 1
        entry = json.loads(dl_lines[0])
        assert entry["profile_id"] == str(pid_b)
        assert entry["platform"] == "instagram"
        assert "rpc exploded" in entry["error"]


def test_orchestrator_no_dead_letter_path_logs_only():
    """When dead_letter_path is None, failures still don't crash the run."""
    pid = uuid4()
    post = _make_post(pid)
    ig_fetcher = MagicMock()
    ig_fetcher.fetch = MagicMock(return_value=_async_return(FetchBatchResult(posts_by_profile={pid: [post]}, actor_id="apify/instagram-scraper")))
    tt_fetcher = MagicMock()
    tt_fetcher.fetch = MagicMock(return_value=_async_return(FetchBatchResult(posts_by_profile={}, actor_id="clockworks/tiktok-scraper")))

    sb = MagicMock()
    chain = MagicMock()
    chain.execute.side_effect = RuntimeError("boom")
    sb.rpc.return_value = chain
    sb.table.return_value = chain

    orch = ScrapeOrchestrator(
        supabase=sb, ig_fetcher=ig_fetcher, tt_fetcher=tt_fetcher,
        dead_letter_path=None,
    )
    summary = asyncio.run(orch.run([
        ProfileScope(profile_id=pid, handle="a", platform="instagram", creator_id=uuid4(), workspace_id=uuid4()),
    ], since=datetime(2026, 4, 1, tzinfo=timezone.utc)))
    assert summary.failures == 1
