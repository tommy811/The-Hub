# scripts/tests/test_link_in_bio.py
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from link_in_bio import resolve_link_in_bio, is_aggregator_url

FIXTURES = Path(__file__).parent / "fixtures"


def _mock_response(html: str, status_code: int = 200) -> MagicMock:
    resp = MagicMock()
    resp.status_code = status_code
    resp.text = html
    resp.raise_for_status = MagicMock()
    return resp


class TestIsAggregatorUrl:
    def test_linktree(self):
        assert is_aggregator_url("https://linktr.ee/foo") is True
        assert is_aggregator_url("https://www.linktr.ee/bar") is True

    def test_beacons(self):
        assert is_aggregator_url("https://beacons.ai/foo") is True
        assert is_aggregator_url("https://beacons.page/foo") is True

    def test_non_aggregator(self):
        assert is_aggregator_url("https://onlyfans.com/foo") is False
        assert is_aggregator_url("https://instagram.com/foo") is False


class TestResolveLinkInBio:
    def test_extracts_linktree_destinations(self):
        html = (FIXTURES / "linktree_sample.html").read_text()
        with patch("link_in_bio.httpx.get", return_value=_mock_response(html)):
            dests = resolve_link_in_bio("https://linktr.ee/gothgirlnatalie")
        assert "https://onlyfans.com/gothgirlnatalie" in dests
        assert "https://fanvue.com/gothgirlnatalie" in dests
        assert "https://instagram.com/gothgirlnatalie" in dests
        # Internal links and support pages excluded
        assert not any("linktr.ee" in d for d in dests)
        assert not any("mailto:" in d for d in dests)

    def test_extracts_beacons_destinations(self):
        html = (FIXTURES / "beacons_sample.html").read_text()
        with patch("link_in_bio.httpx.get", return_value=_mock_response(html)):
            dests = resolve_link_in_bio("https://beacons.ai/gothgirlnatalie")
        assert "https://onlyfans.com/gothgirlnatalie" in dests
        assert "https://patreon.com/gothgirlnatalie" in dests
        assert not any("beacons.ai" in d for d in dests)

    def test_returns_empty_on_non_aggregator_url(self):
        # We only resolve known aggregators; arbitrary personal domains are skipped
        dests = resolve_link_in_bio("https://example.com/me")
        assert dests == []

    def test_returns_empty_on_http_error(self):
        with patch("link_in_bio.httpx.get", side_effect=Exception("network")):
            dests = resolve_link_in_bio("https://linktr.ee/foo")
        assert dests == []

    def test_deduplicates(self):
        html = """<html><body>
            <a href="https://onlyfans.com/foo">1</a>
            <a href="https://onlyfans.com/foo">2</a>
        </body></html>"""
        with patch("link_in_bio.httpx.get", return_value=_mock_response(html)):
            dests = resolve_link_in_bio("https://linktr.ee/foo")
        assert dests.count("https://onlyfans.com/foo") == 1
