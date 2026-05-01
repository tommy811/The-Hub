# scripts/tests/fetchers/test_httpx_fetchers.py
from unittest.mock import patch, MagicMock
import pytest
from fetchers.base import EmptyDatasetError
from fetchers import patreon, fanvue, generic


_PATREON_HTML = b"""
<html><head>
<meta property="og:title" content="Alice | creating ASMR videos">
<meta property="og:description" content="Monthly ASMR subscriber community">
<meta property="og:image" content="https://patreon.cdn/avatar.jpg">
</head><body>
<script>{"creator":{"name":"Alice","campaign_pledge_sum":{"amount":500000}}}</script>
</body></html>
"""

_FANVUE_HTML = b"""
<html><head>
<meta property="og:title" content="Alice on Fanvue">
<meta property="og:description" content="spicy content subscription">
<meta property="og:image" content="https://fanvue.cdn/avatar.jpg">
</head></html>
"""

_GENERIC_HTML = b"""
<html><head>
<title>Alice's Coaching Site</title>
<meta name="description" content="1:1 content strategy coaching for creators">
<meta property="og:image" content="https://site.com/hero.jpg">
</head></html>
"""


@patch("fetchers.patreon.httpx.Client")
def test_patreon_fetch_parses_og_tags(mock_client_cls):
    mock_client = MagicMock()
    mock_client_cls.return_value.__enter__.return_value = mock_client
    resp = MagicMock()
    resp.status_code = 200
    resp.content = _PATREON_HTML
    mock_client.get.return_value = resp

    ctx = patreon.fetch("alice")

    assert ctx.platform == "patreon"
    assert ctx.handle == "alice"
    assert ctx.display_name == "Alice | creating ASMR videos"
    assert ctx.bio == "Monthly ASMR subscriber community"
    assert ctx.avatar_url == "https://patreon.cdn/avatar.jpg"


@patch("fetchers.patreon.httpx.Client")
def test_patreon_404_raises_empty(mock_client_cls):
    mock_client = MagicMock()
    mock_client_cls.return_value.__enter__.return_value = mock_client
    resp = MagicMock()
    resp.status_code = 404
    mock_client.get.return_value = resp

    with pytest.raises(EmptyDatasetError):
        patreon.fetch("nonexistent")


@patch("fetchers.fanvue.httpx.Client")
def test_fanvue_fetch_parses_og_tags(mock_client_cls):
    mock_client = MagicMock()
    mock_client_cls.return_value.__enter__.return_value = mock_client
    resp = MagicMock()
    resp.status_code = 200
    resp.content = _FANVUE_HTML
    mock_client.get.return_value = resp

    ctx = fanvue.fetch("alice")

    assert ctx.platform == "fanvue"
    assert ctx.display_name == "Alice on Fanvue"
    assert ctx.bio == "spicy content subscription"


@patch("fetchers.generic.httpx.Client")
def test_generic_fetch_parses_title_and_meta(mock_client_cls):
    mock_client = MagicMock()
    mock_client_cls.return_value.__enter__.return_value = mock_client
    resp = MagicMock()
    resp.status_code = 200
    resp.content = _GENERIC_HTML
    mock_client.get.return_value = resp

    ctx = generic.fetch_url("https://alice-coaching.example/")

    assert ctx.platform == "other"
    assert ctx.display_name == "Alice's Coaching Site"
    assert ctx.bio == "1:1 content strategy coaching for creators"
    assert ctx.avatar_url == "https://site.com/hero.jpg"


@patch("fetchers.generic.httpx.Client")
def test_generic_fetch_network_error_raises_empty(mock_client_cls):
    mock_client = MagicMock()
    mock_client_cls.return_value.__enter__.return_value = mock_client
    mock_client.get.side_effect = Exception("dns fail")

    with pytest.raises(EmptyDatasetError):
        generic.fetch_url("https://down.example/")
