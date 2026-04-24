# scripts/tests/aggregators/test_custom_domain.py
from unittest.mock import patch, MagicMock
from aggregators.custom_domain import resolve


_HTML_WITH_LINKS = b"""
<html><body>
<a href="https://onlyfans.com/alice">My OF</a>
<a href="https://instagram.com/alice_backup">IG backup</a>
<a href="mailto:alice@example.com">email</a>
<a href="https://amazon.com/shop/alice">Shop</a>
</body></html>
"""


@patch("aggregators.custom_domain.httpx.Client")
def test_resolve_follows_redirects_and_extracts_links(mock_client_cls):
    mock_client = MagicMock()
    mock_client_cls.return_value.__enter__.return_value = mock_client
    resp = MagicMock()
    resp.status_code = 200
    resp.text = _HTML_WITH_LINKS.decode()
    resp.url = "https://creator-funnel.example/alice"  # final redirect target
    mock_client.get.return_value = resp

    destinations = resolve("https://mylink.link/alice")

    assert "https://onlyfans.com/alice" in destinations
    assert "https://instagram.com/alice_backup" in destinations
    assert "https://amazon.com/shop/alice" in destinations
    assert not any("mailto:" in d for d in destinations)


@patch("aggregators.custom_domain.httpx.Client")
def test_resolve_returns_empty_on_error(mock_client_cls):
    mock_client = MagicMock()
    mock_client_cls.return_value.__enter__.return_value = mock_client
    mock_client.get.side_effect = Exception("timeout")

    destinations = resolve("https://down.example/")
    assert destinations == []


@patch("aggregators.custom_domain.httpx.Client")
def test_resolve_returns_empty_on_404(mock_client_cls):
    mock_client = MagicMock()
    mock_client_cls.return_value.__enter__.return_value = mock_client
    resp = MagicMock()
    resp.status_code = 404
    mock_client.get.return_value = resp

    destinations = resolve("https://gone.example/")
    assert destinations == []
