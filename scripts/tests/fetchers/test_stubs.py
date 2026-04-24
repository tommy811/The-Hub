# scripts/tests/fetchers/test_stubs.py
from fetchers import facebook, twitter


def test_facebook_stub_returns_empty_context_with_marker():
    ctx = facebook.fetch("alice")
    assert ctx.platform == "facebook"
    assert ctx.handle == "alice"
    assert ctx.is_empty() is True
    assert ctx.source_note == "stub:not_implemented"


def test_twitter_stub_returns_empty_context_with_marker():
    ctx = twitter.fetch("alice")
    assert ctx.platform == "twitter"
    assert ctx.handle == "alice"
    assert ctx.is_empty() is True
    assert ctx.source_note == "stub:not_implemented"
