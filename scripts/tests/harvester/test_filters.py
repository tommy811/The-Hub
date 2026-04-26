# scripts/tests/harvester/test_filters.py
import pytest

from harvester.filters import is_noise_url, base_domain, same_base_domain


@pytest.mark.parametrize("url", [
    "https://api.linkme.global",
    "https://commerce-service.api.linkme.global",
    "https://stripe-prod.api.linkme.global",
    "https://auth-service.api.linkme.global",
    "https://chat-v1.api.linkme.global",
    "https://config.link.me",
    "https://media.link.me",
    "https://agent.worker.link.me",
    "https://ig-compliance.worker.link.me",
    "https://d1yf24qmkrhwez.cloudfront.net",
    "https://meglobalapp.page.link",
    "https://meglobalapp.page.link/FGdpkQAUp1R8y3sv9",
])
def test_noise_hosts_dropped(url):
    assert is_noise_url(url) is True, f"{url} should be filtered as noise"


@pytest.mark.parametrize("url", [
    "https://about.link.me/privacypolicy",
    "https://about.link.me/termsandconditions",
    "https://example.com/terms",
    "https://example.com/privacy-policy",
    "https://example.com/legal/dmca",
    "https://example.com/contact",
])
def test_legal_paths_dropped(url):
    assert is_noise_url(url) is True


@pytest.mark.parametrize("url", [
    "https://instagram.com/",
    "https://tiktok.com/",
    "https://twitter.com/",
])
def test_empty_path_dropped(url):
    assert is_noise_url(url) is True


@pytest.mark.parametrize("url", [
    "https://instagram.com/kirapregiato",
    "https://onlyfans.com/x",
    "https://t.me/esmaeiscursed",
    "https://buymeacoffee.com/example",
    "https://substack.com/@author",
])
def test_real_destinations_kept(url):
    assert is_noise_url(url) is False, f"{url} should NOT be filtered"


def test_base_domain():
    assert base_domain("foo.bar.example.com") == "example.com"
    assert base_domain("api.link.me") == "link.me"
    assert base_domain("example.com") == "example.com"
    assert base_domain("foo.example.co.uk") == "example.co.uk"


def test_same_base_domain():
    assert same_base_domain("https://link.me/x", "https://api.link.me") is True
    assert same_base_domain("https://link.me/x", "https://config.link.me") is True
    assert same_base_domain("https://link.me/x", "https://about.link.me/privacy") is True
    assert same_base_domain("https://link.me/x", "https://onlyfans.com/y") is False
    assert same_base_domain("https://example.co.uk", "https://foo.example.co.uk") is True
