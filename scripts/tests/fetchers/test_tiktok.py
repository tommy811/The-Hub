# scripts/tests/fetchers/test_tiktok.py
from unittest.mock import MagicMock
import pytest

from fetchers.tiktok import fetch
from fetchers.base import EmptyDatasetError


def _make_client(items: list[dict]) -> MagicMock:
    client = MagicMock()
    actor = MagicMock()
    actor.call.return_value = {"defaultDatasetId": "ds-test"}
    client.actor.return_value = actor
    dataset = MagicMock()
    list_items = MagicMock()
    list_items.items = items
    dataset.list_items.return_value = list_items
    client.dataset.return_value = dataset
    return client


class TestTikTokFetch:
    def test_bioLink_string_shape_current_actor(self):
        # clockworks/tiktok-scraper currently returns bioLink as a plain string.
        # Was silently dropped pre-fix because code only handled legacy dict shape.
        client = _make_client([{
            "authorMeta": {
                "id": "1", "name": "theellableu", "nickName": "theellableu",
                "verified": False,
                "signature": "Fitness. Faith. Structure",
                "bioLink": "https://www.instagram.com/theellableu?igsh=abc",
                "avatar": "https://t.com/p.jpg",
                "fans": 35700, "following": 1, "video": 82,
            }
        }])
        ctx = fetch(client, "theellableu")
        assert ctx.external_urls == ["https://www.instagram.com/theellableu?igsh=abc"]
        assert ctx.bio == "Fitness. Faith. Structure"
        assert ctx.follower_count == 35700

    def test_bioLink_dict_shape_legacy(self):
        # Older actor builds returned bioLink as {"link": "<url>"}. Keep working
        # in case the actor flips back or rolls back deploys.
        client = _make_client([{
            "authorMeta": {
                "id": "2", "name": "natalie", "nickName": "Natalie",
                "verified": False, "signature": "goth girl",
                "bioLink": {"link": "https://linktr.ee/natalie"},
                "fans": 1000, "following": 10, "video": 10,
            }
        }])
        ctx = fetch(client, "natalie")
        assert ctx.external_urls == ["https://linktr.ee/natalie"]

    def test_bioLink_missing(self):
        client = _make_client([{
            "authorMeta": {
                "id": "3", "name": "nolink", "nickName": "no link",
                "verified": False, "signature": "no funnel",
                "fans": 100, "following": 5, "video": 1,
            }
        }])
        ctx = fetch(client, "nolink")
        assert ctx.external_urls == []

    def test_bioLink_empty_string(self):
        client = _make_client([{
            "authorMeta": {
                "id": "4", "name": "empty", "nickName": "empty",
                "verified": False, "signature": "",
                "bioLink": "",
                "fans": 1, "following": 0, "video": 0,
            }
        }])
        ctx = fetch(client, "empty")
        assert ctx.external_urls == []

    def test_bioLink_dict_with_empty_link(self):
        client = _make_client([{
            "authorMeta": {
                "id": "5", "name": "halfempty", "nickName": "half",
                "verified": False, "signature": "",
                "bioLink": {"link": ""},
                "fans": 1, "following": 0, "video": 0,
            }
        }])
        ctx = fetch(client, "halfempty")
        assert ctx.external_urls == []

    def test_raises_on_empty_dataset(self):
        client = _make_client([])
        with pytest.raises(EmptyDatasetError):
            fetch(client, "ghost")
