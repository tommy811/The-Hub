# scripts/tests/fetchers/test_youtube.py
from unittest.mock import patch, MagicMock
import pytest
from fetchers.youtube import fetch
from fetchers.base import EmptyDatasetError


class TestYouTubeFetch:
    @patch("fetchers.youtube.yt_dlp.YoutubeDL")
    def test_returns_context_from_channel_info(self, mock_ydl_cls):
        ydl = MagicMock()
        mock_ydl_cls.return_value.__enter__.return_value = ydl
        ydl.extract_info.return_value = {
            "channel": "Alice Creator",
            "channel_id": "UC123",
            "description": "my tiktok @alice_cooks and linktr.ee/alice",
            "channel_follower_count": 50000,
            "uploader_url": "https://www.youtube.com/@alice",
            "thumbnails": [{"url": "https://yt3/avatar.jpg", "preference": 1}],
        }

        ctx = fetch("@alice")

        assert ctx.platform == "youtube"
        assert ctx.handle == "@alice"
        assert ctx.display_name == "Alice Creator"
        assert ctx.bio == "my tiktok @alice_cooks and linktr.ee/alice"
        assert ctx.follower_count == 50000
        assert ctx.avatar_url == "https://yt3/avatar.jpg"
        assert ctx.source_note == "yt-dlp channel info"

    @patch("fetchers.youtube.yt_dlp.YoutubeDL")
    def test_extracts_urls_from_description(self, mock_ydl_cls):
        ydl = MagicMock()
        mock_ydl_cls.return_value.__enter__.return_value = ydl
        ydl.extract_info.return_value = {
            "channel": "Alice",
            "description": "links: https://linktr.ee/alice and https://onlyfans.com/alice",
            "channel_follower_count": 1000,
        }

        ctx = fetch("@alice")

        assert "https://linktr.ee/alice" in ctx.external_urls
        assert "https://onlyfans.com/alice" in ctx.external_urls

    @patch("fetchers.youtube.yt_dlp.YoutubeDL")
    def test_raises_on_extraction_error(self, mock_ydl_cls):
        ydl = MagicMock()
        mock_ydl_cls.return_value.__enter__.return_value = ydl
        ydl.extract_info.side_effect = Exception("channel not found")

        with pytest.raises(EmptyDatasetError):
            fetch("@nonexistent")

    @patch("fetchers.youtube.yt_dlp.YoutubeDL")
    def test_raises_on_empty_info(self, mock_ydl_cls):
        ydl = MagicMock()
        mock_ydl_cls.return_value.__enter__.return_value = ydl
        ydl.extract_info.return_value = None

        with pytest.raises(EmptyDatasetError):
            fetch("@empty")
