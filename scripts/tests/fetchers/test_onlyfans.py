# scripts/tests/fetchers/test_onlyfans.py
from unittest.mock import patch, MagicMock
import pytest
from fetchers.onlyfans import fetch
from fetchers.base import EmptyDatasetError


_OF_HTML = b"""
<html><head>
<meta property="og:title" content="Alice | OnlyFans">
<meta property="og:description" content="exclusive content daily">
<meta property="og:image" content="https://of.cdn/avatar.jpg">
</head></html>
"""


@patch("fetchers.onlyfans.requests.get")
def test_fetch_parses_og_tags(mock_get):
    resp = MagicMock()
    resp.status_code = 200
    resp.content = _OF_HTML
    mock_get.return_value = resp

    ctx = fetch("alice")

    assert ctx.platform == "onlyfans"
    assert ctx.handle == "alice"
    assert ctx.display_name == "Alice | OnlyFans"
    assert ctx.bio == "exclusive content daily"
    assert ctx.avatar_url == "https://of.cdn/avatar.jpg"
    # Confirm we're using chrome impersonation
    assert mock_get.call_args.kwargs.get("impersonate") == "chrome120"


@patch("fetchers.onlyfans.requests.get")
def test_fetch_404_raises_empty(mock_get):
    resp = MagicMock()
    resp.status_code = 404
    mock_get.return_value = resp

    with pytest.raises(EmptyDatasetError):
        fetch("nonexistent")


@patch("fetchers.onlyfans.requests.get")
def test_fetch_network_error_raises_empty(mock_get):
    mock_get.side_effect = Exception("TLS handshake failed")

    with pytest.raises(EmptyDatasetError):
        fetch("alice")
