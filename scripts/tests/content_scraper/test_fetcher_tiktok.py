"""Tests for TikTokContentFetcher."""
import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock
from uuid import uuid4

from content_scraper.fetchers.base import ProfileTarget
from content_scraper.fetchers.tiktok import TikTokContentFetcher

FIXTURE_DIR = Path(__file__).parent / "fixtures"


def _load_fixture(name: str) -> dict:
    return json.loads((FIXTURE_DIR / name).read_text())


def _make_apify_mock(items: list[dict]) -> MagicMock:
    apify = MagicMock()
    actor = MagicMock()
    actor.call.return_value = {"defaultDatasetId": "ds_test"}
    apify.actor.return_value = actor
    dataset = MagicMock()
    items_result = MagicMock()
    items_result.items = items
    dataset.list_items.return_value = items_result
    dataset.iterate_items.return_value = iter(items)
    apify.dataset.return_value = dataset
    return apify


def test_tiktok_fetcher_passes_profiles_for_all_targets():
    apify = _make_apify_mock([])
    fetcher = TikTokContentFetcher(apify_client=apify)
    asyncio.run(fetcher.fetch(
        [
            ProfileTarget(profile_id=uuid4(), handle="kira"),
            ProfileTarget(profile_id=uuid4(), handle="esmae"),
        ],
        since=datetime(2026, 4, 1, tzinfo=timezone.utc),
    ))
    apify.actor.assert_called_once_with("clockworks/tiktok-scraper")
    call_input = apify.actor.return_value.call.call_args.kwargs["run_input"]
    assert call_input["profiles"] == ["kira", "esmae"]


def test_tiktok_fetcher_passes_since_via_oldestpostdate():
    apify = _make_apify_mock([])
    fetcher = TikTokContentFetcher(apify_client=apify)
    since = datetime(2026, 4, 1, tzinfo=timezone.utc)
    asyncio.run(fetcher.fetch(
        [ProfileTarget(profile_id=uuid4(), handle="x")],
        since=since,
    ))
    call_input = apify.actor.return_value.call.call_args.kwargs["run_input"]
    assert call_input["oldestPostDate"] == "2026-04-01"


def test_tiktok_fetcher_disaggregates_by_authormeta_name():
    pid_a, pid_b = uuid4(), uuid4()
    raw = _load_fixture("tiktok_post.json")
    item_a = {**raw, "id": "tt_a", "authorMeta": {"name": "kira"}}
    item_b = {**raw, "id": "tt_b", "authorMeta": {"name": "esmae"}}
    apify = _make_apify_mock([item_a, item_b])
    fetcher = TikTokContentFetcher(apify_client=apify)
    result = asyncio.run(fetcher.fetch(
        [
            ProfileTarget(profile_id=pid_a, handle="kira"),
            ProfileTarget(profile_id=pid_b, handle="esmae"),
        ],
        since=datetime(2026, 4, 1, tzinfo=timezone.utc),
    )).posts_by_profile
    assert pid_a in result and pid_b in result
    assert result[pid_a][0].platform_post_id == "tt_a"
    assert result[pid_b][0].platform_post_id == "tt_b"


def test_tiktok_fetcher_handles_authormeta_missing():
    """Posts without authorMeta should be dropped, not crash."""
    pid_a = uuid4()
    raw = _load_fixture("tiktok_post.json")
    item_no_author = {**raw, "id": "no_author"}
    item_no_author.pop("authorMeta", None)
    apify = _make_apify_mock([item_no_author])
    fetcher = TikTokContentFetcher(apify_client=apify)
    result = asyncio.run(fetcher.fetch(
        [ProfileTarget(profile_id=pid_a, handle="kira")],
        since=datetime(2026, 4, 1, tzinfo=timezone.utc),
    )).posts_by_profile
    assert result == {}


def test_tiktok_fetcher_empty_profile_list_makes_no_apify_call():
    apify = _make_apify_mock([])
    fetcher = TikTokContentFetcher(apify_client=apify)
    result = asyncio.run(fetcher.fetch([], since=datetime(2026, 4, 1, tzinfo=timezone.utc)))
    assert result.posts_by_profile == {}
    apify.actor.assert_not_called()
