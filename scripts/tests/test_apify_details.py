# scripts/tests/test_apify_details.py
import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from apify_details import (
    EmptyDatasetError,
    fetch_instagram_details,
    fetch_tiktok_details,
)

FIXTURES = Path(__file__).parent / "fixtures"


def _load(name: str) -> list[dict]:
    return json.loads((FIXTURES / name).read_text())


def _mock_client(dataset_items: list[dict]) -> MagicMock:
    """Build a MagicMock that mimics ApifyClient.actor(id).call(...) + dataset(...).list_items()."""
    client = MagicMock()
    actor = MagicMock()
    dataset = MagicMock()
    run_ret = {"defaultDatasetId": "fake-dataset-id"}
    actor.call.return_value = run_ret
    dataset.list_items.return_value = MagicMock(items=dataset_items)
    client.actor.return_value = actor
    client.dataset.return_value = dataset
    return client


class TestFetchInstagramDetails:
    def test_returns_context_with_bio_and_external_urls(self):
        client = _mock_client(_load("apify_ig_details.json"))
        ctx = fetch_instagram_details(client, "gothgirlnatalie")
        assert ctx.handle == "gothgirlnatalie"
        assert ctx.platform == "instagram"
        assert ctx.bio == "goth girl ✦ 18+ link below"
        assert ctx.follower_count == 48200
        assert ctx.following_count == 612
        assert ctx.post_count == 142
        assert "https://linktr.ee/gothgirlnatalie" in ctx.external_urls
        assert ctx.display_name == "Natalie Vox"
        assert ctx.avatar_url == "https://instagram.com/pic_hd.jpg"
        assert ctx.is_empty() is False

    def test_uses_details_mode(self):
        client = _mock_client(_load("apify_ig_details.json"))
        fetch_instagram_details(client, "gothgirlnatalie")
        call_args = client.actor.return_value.call.call_args
        run_input = call_args.kwargs.get("run_input") or call_args.args[0]
        assert run_input["resultsType"] == "details"
        assert "gothgirlnatalie" in run_input["directUrls"][0]

    def test_raises_on_empty_dataset(self):
        client = _mock_client([])
        with pytest.raises(EmptyDatasetError) as exc:
            fetch_instagram_details(client, "deleteduser")
        assert "deleteduser" in str(exc.value)


class TestFetchTikTokDetails:
    def test_returns_context_from_author_meta(self):
        client = _mock_client(_load("apify_tiktok_profile.json"))
        ctx = fetch_tiktok_details(client, "gothgirlnatalie")
        assert ctx.handle == "gothgirlnatalie"
        assert ctx.platform == "tiktok"
        assert ctx.bio == "goth girl ✦ link below"
        assert ctx.follower_count == 12400
        assert "https://linktr.ee/gothgirlnatalie" in ctx.external_urls
        assert ctx.display_name == "Natalie"
        assert ctx.is_empty() is False

    def test_uses_clockworks_actor(self):
        client = _mock_client(_load("apify_tiktok_profile.json"))
        fetch_tiktok_details(client, "gothgirlnatalie")
        actor_id = client.actor.call_args.args[0]
        assert actor_id == "clockworks/tiktok-scraper"

    def test_raises_on_empty_dataset(self):
        client = _mock_client([])
        with pytest.raises(EmptyDatasetError):
            fetch_tiktok_details(client, "ghost")
