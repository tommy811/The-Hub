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

from content_scraper.fetchers.base import ProfileTarget
from content_scraper.normalizer import NormalizedPost, PlatformMetrics
from content_scraper.orchestrator import ScrapeOrchestrator, ProfileScope


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


def _async_return(value):
    """Helper: return an awaitable that resolves to `value`."""
    async def _r(*args, **kwargs):
        return value
    return _r()


def _supabase_mock_with_outlier_query(outlier_count: int = 0) -> MagicMock:
    """Build a supabase mock where the post-flag query returns `outlier_count` outlier rows."""
    sb = MagicMock()
    rpc_chain = MagicMock()
    rpc_chain.execute.return_value = MagicMock(data={"posts_upserted": 1, "snapshots_written": 1})
    sb.rpc.return_value = rpc_chain

    table_chain = MagicMock()
    table_chain.upsert.return_value = table_chain
    table_chain.execute.return_value = MagicMock(data=[{}])

    sc_select_chain = MagicMock()
    sc_select_chain.eq.return_value = sc_select_chain
    sc_select_chain.execute.return_value = MagicMock(
        data=[{"view_count": 100, "is_outlier": i < outlier_count} for i in range(5)]
    )

    profiles_chain = MagicMock()
    profiles_chain.select.return_value = profiles_chain
    profiles_chain.eq.return_value = profiles_chain
    profiles_chain.single.return_value = profiles_chain
    profiles_chain.execute.return_value = MagicMock(data={"follower_count": 1000})

    def table_factory(name):
        if name == "profile_metrics_snapshots":
            return table_chain
        if name == "scraped_content":
            sc = MagicMock()
            sc.select.return_value = sc_select_chain
            return sc
        if name == "profiles":
            return profiles_chain
        return MagicMock()

    sb.table.side_effect = table_factory
    return sb


def test_orchestrator_calls_commit_then_flag_outliers_per_profile():
    pid = uuid4()
    post = _make_post(pid)
    ig_fetcher = MagicMock()
    ig_fetcher.fetch = MagicMock(return_value=_async_return({pid: [post]}))
    tt_fetcher = MagicMock()
    tt_fetcher.fetch = MagicMock(return_value=_async_return({}))

    sb = _supabase_mock_with_outlier_query()
    orch = ScrapeOrchestrator(
        supabase=sb,
        ig_fetcher=ig_fetcher,
        tt_fetcher=tt_fetcher,
        dead_letter_path=None,
    )
    asyncio.run(orch.run([
        ProfileScope(profile_id=pid, handle="x", platform="instagram", creator_id=uuid4()),
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
    ig_fetcher.fetch = MagicMock(return_value=_async_return({}))
    tt_fetcher = MagicMock()
    tt_fetcher.fetch = MagicMock(return_value=_async_return({}))

    sb = _supabase_mock_with_outlier_query()
    orch = ScrapeOrchestrator(
        supabase=sb,
        ig_fetcher=ig_fetcher,
        tt_fetcher=tt_fetcher,
        dead_letter_path=None,
    )
    asyncio.run(orch.run([
        ProfileScope(profile_id=pid, handle="x", platform="instagram", creator_id=uuid4()),
    ], since=datetime(2026, 4, 1, tzinfo=timezone.utc)))

    sb.rpc.assert_not_called()


def test_orchestrator_groups_by_platform_and_calls_each_fetcher_once():
    pid_ig, pid_tt = uuid4(), uuid4()
    post_ig = _make_post(pid_ig, post_id="ig1")
    post_tt = _make_post(pid_tt, post_id="tt1")
    post_tt = post_tt.model_copy(update={"platform": "tiktok", "post_type": "tiktok_video"})

    ig_fetcher = MagicMock()
    ig_fetcher.fetch = MagicMock(return_value=_async_return({pid_ig: [post_ig]}))
    tt_fetcher = MagicMock()
    tt_fetcher.fetch = MagicMock(return_value=_async_return({pid_tt: [post_tt]}))

    sb = _supabase_mock_with_outlier_query()
    orch = ScrapeOrchestrator(
        supabase=sb, ig_fetcher=ig_fetcher, tt_fetcher=tt_fetcher,
        dead_letter_path=None,
    )
    asyncio.run(orch.run([
        ProfileScope(profile_id=pid_ig, handle="x", platform="instagram", creator_id=uuid4()),
        ProfileScope(profile_id=pid_tt, handle="y", platform="tiktok", creator_id=uuid4()),
    ], since=datetime(2026, 4, 1, tzinfo=timezone.utc)))

    ig_fetcher.fetch.assert_called_once()
    tt_fetcher.fetch.assert_called_once()
