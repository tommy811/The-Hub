# scripts/tests/harvester/test_canonicalize_extension.py
from pipeline.canonicalize import canonicalize_url


def test_strips_tapforallmylinks_l_param():
    url = "https://fanplace.com/esmaecursed?l_=fpHJS72TYFy2PGEZRf8k"
    assert canonicalize_url(url) == "https://fanplace.com/esmaecursed"


def test_strips_igsh_param():
    url = "https://www.instagram.com/gothasiansclub?igsh=MW9ob2ZpOGVwbHU"
    assert canonicalize_url(url) == "https://instagram.com/gothasiansclub"


def test_strips_twitter_s_share_param():
    url = "https://x.com/esmaecursed?s=21&t=abc123"
    assert canonicalize_url(url) == "https://x.com/esmaecursed"


def test_strips_aff_param():
    url = "https://amzn.to/3xY2z?aff=mycreator"
    assert canonicalize_url(url) == "https://amzn.to/3xy2z"


def test_preserves_meaningful_query_params():
    # ?p=123 on a generic site should be kept — not a known tracking param
    url = "https://example.com/page?p=123&utm_source=ig"
    assert canonicalize_url(url) == "https://example.com/page?p=123"
