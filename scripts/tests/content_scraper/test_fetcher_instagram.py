"""Tests for InstagramContentFetcher.

Mocks the ApifyClient so we can assert on the actor input shape and the
return-disaggregation logic without burning real Apify credits.
"""
import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from content_scraper.fetchers.base import ProfileTarget
from content_scraper.fetchers.instagram import InstagramContentFetcher

FIXTURE_DIR = Path(__file__).parent / "fixtures"


def _load_fixture(name: str) -> dict:
    return json.loads((FIXTURE_DIR / name).read_text())


def _make_apify_mock(items: list[dict]) -> MagicMock:
    """Mock an ApifyClient where actor(...).call(...) returns a run dict
    and dataset(...).list_items() returns the given items.
    """
    apify = MagicMock()
    actor = MagicMock()
    actor.call.return_value = {"defaultDatasetId": "ds_test"}
    apify.actor.return_value = actor
    dataset = MagicMock()
    dataset_items_result = MagicMock()
    dataset_items_result.items = items
    dataset.list_items.return_value = dataset_items_result
    apify.dataset.return_value = dataset
    return apify


def test_instagram_fetcher_passes_directUrls_for_all_profiles():
    pid_a, pid_b = uuid4(), uuid4()
    apify = _make_apify_mock([])
    fetcher = InstagramContentFetcher(apify_client=apify)

    profiles = [
        ProfileTarget(profile_id=pid_a, handle="creator_a"),
        ProfileTarget(profile_id=pid_b, handle="creator_b"),
    ]
    asyncio.run(fetcher.fetch(profiles, since=datetime(2026, 4, 1, tzinfo=timezone.utc)))

    apify.actor.assert_called_once_with("apify/instagram-scraper")
    call_input = apify.actor.return_value.call.call_args.kwargs["run_input"]
    assert call_input["directUrls"] == [
        "https://www.instagram.com/creator_a/",
        "https://www.instagram.com/creator_b/",
    ]
    assert call_input["resultsType"] == "posts"


def test_instagram_fetcher_passes_since_filter():
    apify = _make_apify_mock([])
    fetcher = InstagramContentFetcher(apify_client=apify)
    since = datetime(2026, 4, 1, tzinfo=timezone.utc)
    asyncio.run(fetcher.fetch(
        [ProfileTarget(profile_id=uuid4(), handle="x")],
        since=since,
    ))
    call_input = apify.actor.return_value.call.call_args.kwargs["run_input"]
    assert call_input["onlyPostsNewerThan"] == "2026-04-01"


def test_instagram_fetcher_disaggregates_by_owner_username():
    pid_a, pid_b = uuid4(), uuid4()
    raw = _load_fixture("instagram_post.json")
    item_a = {**raw, "id": "post_a_1", "ownerUsername": "creator_a"}
    item_b1 = {**raw, "id": "post_b_1", "ownerUsername": "creator_b"}
    item_b2 = {**raw, "id": "post_b_2", "ownerUsername": "creator_b"}
    apify = _make_apify_mock([item_a, item_b1, item_b2])
    fetcher = InstagramContentFetcher(apify_client=apify)

    result = asyncio.run(fetcher.fetch(
        [
            ProfileTarget(profile_id=pid_a, handle="creator_a"),
            ProfileTarget(profile_id=pid_b, handle="creator_b"),
        ],
        since=datetime(2026, 4, 1, tzinfo=timezone.utc),
    ))

    assert pid_a in result
    assert pid_b in result
    assert len(result[pid_a]) == 1
    assert len(result[pid_b]) == 2
    assert result[pid_a][0].platform_post_id == "post_a_1"
    assert {p.platform_post_id for p in result[pid_b]} == {"post_b_1", "post_b_2"}


def test_instagram_fetcher_omits_profiles_with_zero_posts():
    pid_a, pid_b = uuid4(), uuid4()
    raw = _load_fixture("instagram_post.json")
    item_a = {**raw, "id": "post_a", "ownerUsername": "creator_a"}
    apify = _make_apify_mock([item_a])
    fetcher = InstagramContentFetcher(apify_client=apify)

    result = asyncio.run(fetcher.fetch(
        [
            ProfileTarget(profile_id=pid_a, handle="creator_a"),
            ProfileTarget(profile_id=pid_b, handle="creator_b"),
        ],
        since=datetime(2026, 4, 1, tzinfo=timezone.utc),
    ))

    assert pid_a in result
    assert pid_b not in result


def test_instagram_fetcher_skips_unmapped_owner():
    """An item whose ownerUsername doesn't match any profile target is dropped."""
    pid_a = uuid4()
    raw = _load_fixture("instagram_post.json")
    item_orphan = {**raw, "id": "orphan", "ownerUsername": "totally_other"}
    apify = _make_apify_mock([item_orphan])
    fetcher = InstagramContentFetcher(apify_client=apify)
    result = asyncio.run(fetcher.fetch(
        [ProfileTarget(profile_id=pid_a, handle="creator_a")],
        since=datetime(2026, 4, 1, tzinfo=timezone.utc),
    ))
    assert result == {}


def test_instagram_fetcher_empty_profile_list_makes_no_apify_call():
    apify = _make_apify_mock([])
    fetcher = InstagramContentFetcher(apify_client=apify)
    result = asyncio.run(fetcher.fetch([], since=datetime(2026, 4, 1, tzinfo=timezone.utc)))
    assert result == {}
    apify.actor.assert_not_called()
