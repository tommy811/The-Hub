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


def test_twitter_normalizes_to_x():
    assert canonicalize_url("https://twitter.com/itskirapregiato") == "https://x.com/itskirapregiato"


def test_mobile_twitter_normalizes_to_x():
    assert canonicalize_url("https://mobile.twitter.com/foo") == "https://x.com/foo"


def test_twitter_share_param_and_host_norm_combine():
    # both s=21 stripped AND host normalized
    assert canonicalize_url("https://twitter.com/itskirapregiato?s=21") == "https://x.com/itskirapregiato"


def test_lowercases_instagram_handle():
    assert canonicalize_url("https://instagram.com/UserName") == "https://instagram.com/username"


def test_lowercases_tiktok_handle():
    assert canonicalize_url("https://tiktok.com/@Kira") == "https://tiktok.com/@kira"


def test_strips_instagram_profilecard_suffix():
    assert canonicalize_url("https://instagram.com/kirapregiato/profilecard") == "https://instagram.com/kirapregiato"


def test_preserves_substack_path_case():
    # Substack is case-sensitive — handle case must NOT be lowered
    assert canonicalize_url("https://Foo.substack.com/p/Bar-Title") == "https://foo.substack.com/p/Bar-Title"


def test_strips_tiktok_r_param():
    assert canonicalize_url("https://tiktok.com/@kira?_r=1") == "https://tiktok.com/@kira"


def test_strips_lang_param():
    assert canonicalize_url("https://tiktok.com/@kirapregiato_backup?lang=en") == "https://tiktok.com/@kirapregiato_backup"


def test_strips_hl_param():
    assert canonicalize_url("https://instagram.com/shirleypunn/?hl=en") == "https://instagram.com/shirleypunn"
