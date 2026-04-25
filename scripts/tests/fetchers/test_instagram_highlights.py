# scripts/tests/fetchers/test_instagram_highlights.py
from unittest.mock import MagicMock
import pytest

from schemas import HighlightLink


def _mk_apify_client(items: list[dict]) -> MagicMock:
    """Build a mock Apify client whose actor.call → dataset.list_items returns items."""
    client = MagicMock()
    client.actor.return_value.call.return_value = {"defaultDatasetId": "ds-fake"}
    client.dataset.return_value.list_items.return_value = MagicMock(items=items)
    return client


def test_fetch_highlights_extracts_link_stickers():
    from fetchers.instagram_highlights import fetch_highlights
    items = [
        {
            "pk": "1",
            "taken_at": 1700000000,
            "media_type": 1,
            "story_link_stickers": [
                {"display_url": "https://onlyfans.com/kira",
                 "link_title": "OnlyFans",
                 "url": "https://onlyfans.com/kira"},
            ],
            "mentions": [],
        },
    ]
    client = _mk_apify_client(items)
    out = fetch_highlights(client, "kirapregiato")
    assert len(out) == 1
    assert isinstance(out[0], HighlightLink)
    assert out[0].source == "highlight_link_sticker"
    assert out[0].url == "https://onlyfans.com/kira"


def test_fetch_highlights_extracts_caption_mentions():
    from fetchers.instagram_highlights import fetch_highlights
    items = [
        {
            "pk": "2",
            "taken_at": 1700000000,
            "media_type": 1,
            "story_link_stickers": [],
            "mentions": [{"username": "kira_tt"}, {"username": "kira_yt"}],
        },
    ]
    client = _mk_apify_client(items)
    out = fetch_highlights(client, "kirapregiato")
    handles = sorted(h.handle for h in out if h.source == "highlight_caption_mention")
    # Both mentions surface, but platform must be None (caller's job to figure out
    # which platform — we don't guess).
    assert handles == ["kira_tt", "kira_yt"]
    for link in out:
        assert link.source == "highlight_caption_mention"
        assert link.platform is None  # platform inference deferred to caller


def test_fetch_highlights_returns_empty_for_empty_dataset():
    from fetchers.instagram_highlights import fetch_highlights
    client = _mk_apify_client([])
    assert fetch_highlights(client, "kirapregiato") == []


def test_fetch_highlights_skips_items_without_anything():
    from fetchers.instagram_highlights import fetch_highlights
    items = [
        {"pk": "3", "taken_at": 1, "media_type": 1,
         "story_link_stickers": [], "mentions": []},
        {"pk": "4", "taken_at": 1, "media_type": 1},  # missing both keys entirely
    ]
    client = _mk_apify_client(items)
    assert fetch_highlights(client, "kirapregiato") == []


def test_fetch_highlights_dedupes_within_run():
    from fetchers.instagram_highlights import fetch_highlights
    items = [
        {"pk": "5", "taken_at": 1, "media_type": 1,
         "story_link_stickers": [{"url": "https://onlyfans.com/kira"}],
         "mentions": []},
        {"pk": "6", "taken_at": 2, "media_type": 1,
         "story_link_stickers": [{"url": "https://onlyfans.com/kira"}],  # dup
                "mentions": []},
    ]
    client = _mk_apify_client(items)
    out = fetch_highlights(client, "kirapregiato")
    urls = [h.url for h in out]
    assert urls.count("https://onlyfans.com/kira") == 1


def test_fetch_highlights_returns_empty_on_apify_error():
    """Top-level exception handler: never raise, log and return []."""
    from fetchers.instagram_highlights import fetch_highlights
    client = MagicMock()
    client.actor.return_value.call.side_effect = RuntimeError("boom")
    out = fetch_highlights(client, "kirapregiato")
    assert out == []
