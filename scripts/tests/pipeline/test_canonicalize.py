# scripts/tests/pipeline/test_canonicalize.py
import pytest
from unittest.mock import patch, MagicMock
from pipeline.canonicalize import canonicalize_url, resolve_short_url


class TestCanonicalizeUrl:
    def test_lowercases_host(self):
        # Instagram is in _SOCIAL_HANDLE_HOSTS so the handle is also lowercased
        assert canonicalize_url("HTTPS://WWW.Instagram.com/Alice") == \
            "https://instagram.com/alice"

    def test_strips_www_prefix(self):
        assert canonicalize_url("https://www.linktr.ee/alice") == \
            "https://linktr.ee/alice"

    def test_coerces_protocol_to_https(self):
        assert canonicalize_url("http://instagram.com/alice") == \
            "https://instagram.com/alice"

    def test_strips_trailing_slash(self):
        assert canonicalize_url("https://instagram.com/alice/") == \
            "https://instagram.com/alice"

    def test_strips_utm_params(self):
        assert canonicalize_url(
            "https://onlyfans.com/alice?utm_source=ig&utm_medium=bio&utm_campaign=x"
        ) == "https://onlyfans.com/alice"

    def test_strips_fbclid_gclid_igshid_ref(self):
        assert canonicalize_url(
            "https://instagram.com/alice?fbclid=abc&gclid=def&igshid=ghi&ref=jkl&ref_src=lmn"
        ) == "https://instagram.com/alice"

    def test_preserves_meaningful_query_params(self):
        # e.g. YouTube channel ID URL with v= must survive
        assert canonicalize_url(
            "https://youtube.com/watch?v=dQw4w9WgXcQ&utm_source=ig"
        ) == "https://youtube.com/watch?v=dQw4w9WgXcQ"

    def test_strips_about_and_home_suffixes_on_known_platforms(self):
        assert canonicalize_url("https://youtube.com/@alice/about") == \
            "https://youtube.com/@alice"
        assert canonicalize_url("https://facebook.com/alice/home") == \
            "https://facebook.com/alice"

    def test_is_idempotent(self):
        url = "https://www.Instagram.com/Alice/?utm_source=x"
        once = canonicalize_url(url)
        twice = canonicalize_url(once)
        assert once == twice

    def test_invalid_url_returns_input(self):
        # garbage URLs pass through unchanged — caller decides what to do
        assert canonicalize_url("not a url at all") == "not a url at all"


class TestResolveShortUrl:
    @patch("pipeline.canonicalize.httpx.Client")
    def test_follows_single_redirect(self, mock_client_cls):
        mock_client = MagicMock()
        mock_client_cls.return_value.__enter__.return_value = mock_client
        resp = MagicMock()
        resp.url = "https://onlyfans.com/alice"
        mock_client.head.return_value = resp

        result = resolve_short_url("https://bit.ly/abc")

        assert result == "https://onlyfans.com/alice"
        mock_client.head.assert_called_once()

    @patch("pipeline.canonicalize.httpx.Client")
    def test_caps_at_five_redirects(self, mock_client_cls):
        # httpx follows redirects itself up to max_redirects=5. If we hit that
        # cap, resolve_short_url returns what it has so far without error.
        mock_client = MagicMock()
        mock_client_cls.return_value.__enter__.return_value = mock_client
        resp = MagicMock()
        resp.url = "https://somewhere.com/final"
        mock_client.head.return_value = resp

        result = resolve_short_url("https://bit.ly/abc")

        # just verifying we pass max_redirects and handle the response
        call = mock_client_cls.call_args
        assert call.kwargs.get("max_redirects") == 5
        assert result == "https://somewhere.com/final"

    @patch("pipeline.canonicalize.httpx.Client")
    def test_returns_input_on_http_error(self, mock_client_cls):
        mock_client = MagicMock()
        mock_client_cls.return_value.__enter__.return_value = mock_client
        mock_client.head.side_effect = Exception("network down")

        result = resolve_short_url("https://bit.ly/abc")

        assert result == "https://bit.ly/abc"

    def test_non_short_url_passthrough(self):
        # not in known short-URL host list → return as-is without network
        assert resolve_short_url("https://instagram.com/alice") == \
            "https://instagram.com/alice"
