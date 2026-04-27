"""Tests for NormalizedPost / PlatformMetrics Pydantic contracts.

These lock in the closed-shape promise: any field not explicitly named
in the model raises ValidationError instead of silently passing through.
"""
from datetime import datetime, timezone
from uuid import uuid4

import pytest
from pydantic import ValidationError

from content_scraper.normalizer import (
    NormalizedPost, PlatformMetrics, AudioInfo, LocationInfo,
)


def _minimal_post(**overrides) -> dict:
    base = {
        "profile_id": uuid4(),
        "platform": "instagram",
        "platform_post_id": "abc123",
        "post_url": "https://instagram.com/p/abc123",
        "post_type": "reel",
        "caption": "hello",
        "hook_text": "hello",
        "posted_at": datetime(2026, 4, 27, tzinfo=timezone.utc),
        "view_count": 100,
        "like_count": 10,
        "comment_count": 1,
        "share_count": None,
        "save_count": None,
        "media_urls": [],
        "thumbnail_url": None,
        "platform_metrics": PlatformMetrics(),
        "raw_apify_payload": {},
    }
    base.update(overrides)
    return base


def test_minimal_post_validates():
    post = NormalizedPost(**_minimal_post())
    assert post.is_pinned is False
    assert post.is_sponsored is False
    assert post.hashtags == []
    assert post.mentions == []
    assert post.video_duration_seconds is None


def test_post_type_must_be_enum_value():
    with pytest.raises(ValidationError):
        NormalizedPost(**_minimal_post(post_type="bogus_type"))


def test_platform_must_be_ig_or_tt():
    with pytest.raises(ValidationError):
        NormalizedPost(**_minimal_post(platform="youtube"))


def test_platform_metrics_forbids_extra_keys():
    with pytest.raises(ValidationError):
        PlatformMetrics(unexpected_field="oops")


def test_platform_metrics_default_empty():
    pm = PlatformMetrics()
    assert pm.audio is None
    assert pm.location is None
    assert pm.tagged_accounts == []
    assert pm.effects == []
    assert pm.is_slideshow is None


def test_audio_info_optional_fields():
    audio = AudioInfo(signature="abc", artist=None, title="song", is_original=True)
    assert audio.signature == "abc"
    assert audio.artist is None


def test_location_info_optional_fields():
    loc = LocationInfo(name="Tokyo", id=None)
    assert loc.name == "Tokyo"
    assert loc.id is None


def test_post_with_full_platform_metrics():
    pm = PlatformMetrics(
        audio=AudioInfo(signature="x", artist="a", title="t", is_original=False),
        location=LocationInfo(name="LA", id="123"),
        tagged_accounts=["foo", "bar"],
        product_type="clips",
        effects=["effect_a"],
        is_slideshow=False,
        is_muted=False,
        video_aspect_ratio=0.5625,
        video_resolution="1080x1920",
        subtitles="hello world",
    )
    post = NormalizedPost(**_minimal_post(platform_metrics=pm))
    assert post.platform_metrics.audio.signature == "x"
    assert post.platform_metrics.tagged_accounts == ["foo", "bar"]


import json
from pathlib import Path
from content_scraper.normalizer import instagram_to_normalized

FIXTURE_DIR = Path(__file__).parent / "fixtures"


def _load_fixture(name: str) -> dict:
    return json.loads((FIXTURE_DIR / name).read_text())


def test_instagram_to_normalized_basic_fields():
    pid = uuid4()
    raw = _load_fixture("instagram_post.json")
    post = instagram_to_normalized(raw, profile_id=pid)
    assert post.profile_id == pid
    assert post.platform == "instagram"
    assert post.platform_post_id == "3567890123"
    assert post.post_url == "https://www.instagram.com/p/C-AbCdEf/"
    assert post.post_type == "reel"
    assert post.caption == "summer vibes ☀️ #beach #vacay"
    assert post.posted_at.year == 2026


def test_instagram_to_normalized_engagement():
    raw = _load_fixture("instagram_post.json")
    post = instagram_to_normalized(raw, profile_id=uuid4())
    assert post.view_count == 18000
    assert post.like_count == 850
    assert post.comment_count == 42
    assert post.share_count is None
    assert post.save_count is None


def test_instagram_to_normalized_structural_flags():
    raw = _load_fixture("instagram_post.json")
    post = instagram_to_normalized(raw, profile_id=uuid4())
    assert post.is_pinned is False
    assert post.is_sponsored is False
    assert post.video_duration_seconds == 28.5
    assert post.hashtags == ["beach", "vacay"]
    assert post.mentions == ["friendhandle"]


def test_instagram_to_normalized_platform_metrics():
    raw = _load_fixture("instagram_post.json")
    post = instagram_to_normalized(raw, profile_id=uuid4())
    pm = post.platform_metrics
    assert pm.audio.signature == "987654321"
    assert pm.audio.artist == "Some Artist"
    assert pm.audio.title == "Summer Song"
    assert pm.audio.is_original is False
    assert pm.location.name == "Malibu Beach"
    assert pm.location.id == "12345"
    assert pm.tagged_accounts == ["friend1", "friend2"]
    assert pm.product_type == "clips"


def test_instagram_to_normalized_carousel_post_type():
    raw = _load_fixture("instagram_post.json")
    raw["type"] = "Sidecar"
    raw["images"] = ["https://a.jpg", "https://b.jpg", "https://c.jpg"]
    post = instagram_to_normalized(raw, profile_id=uuid4())
    assert post.post_type == "carousel"
    assert post.media_urls == ["https://a.jpg", "https://b.jpg", "https://c.jpg"]


def test_instagram_to_normalized_image_post_type():
    raw = _load_fixture("instagram_post.json")
    raw["type"] = "Image"
    raw["images"] = []
    raw.pop("videoViewCount", None)
    raw.pop("videoPlayCount", None)
    post = instagram_to_normalized(raw, profile_id=uuid4())
    assert post.post_type == "image"
    assert post.view_count == 0
    assert post.media_urls == ["https://scontent.cdninstagram.com/v/thumb.jpg"]


def test_instagram_to_normalized_hook_text_first_50_chars():
    raw = _load_fixture("instagram_post.json")
    raw["caption"] = "x" * 100
    post = instagram_to_normalized(raw, profile_id=uuid4())
    assert post.hook_text == "x" * 50


def test_instagram_to_normalized_caption_none():
    raw = _load_fixture("instagram_post.json")
    raw["caption"] = None
    post = instagram_to_normalized(raw, profile_id=uuid4())
    assert post.caption is None
    assert post.hook_text is None


def test_instagram_to_normalized_raw_payload_preserved():
    raw = _load_fixture("instagram_post.json")
    post = instagram_to_normalized(raw, profile_id=uuid4())
    assert post.raw_apify_payload == raw


from content_scraper.normalizer import tiktok_to_normalized


def test_tiktok_to_normalized_basic_fields():
    pid = uuid4()
    raw = _load_fixture("tiktok_post.json")
    post = tiktok_to_normalized(raw, profile_id=pid)
    assert post.profile_id == pid
    assert post.platform == "tiktok"
    assert post.platform_post_id == "7234567890123456789"
    assert post.post_url == "https://www.tiktok.com/@kira/video/7234567890123456789"
    assert post.post_type == "tiktok_video"
    assert post.caption == "follow my links pls #fyp #foryou"


def test_tiktok_to_normalized_engagement():
    raw = _load_fixture("tiktok_post.json")
    post = tiktok_to_normalized(raw, profile_id=uuid4())
    assert post.view_count == 250000
    assert post.like_count == 18500
    assert post.comment_count == 320
    assert post.share_count == 1100
    assert post.save_count == 6700


def test_tiktok_to_normalized_structural_flags():
    raw = _load_fixture("tiktok_post.json")
    post = tiktok_to_normalized(raw, profile_id=uuid4())
    assert post.is_pinned is True
    assert post.is_sponsored is False
    assert post.video_duration_seconds == 22
    assert post.hashtags == ["fyp", "foryou"]
    assert post.mentions == []


def test_tiktok_to_normalized_platform_metrics():
    raw = _load_fixture("tiktok_post.json")
    post = tiktok_to_normalized(raw, profile_id=uuid4())
    pm = post.platform_metrics
    assert pm.audio.signature == "7100000000000000000"
    assert pm.audio.artist == "kira"
    assert pm.audio.title == "original sound"
    assert pm.audio.is_original is True
    assert pm.effects == ["Sparkle Filter", "Beauty"]
    assert pm.is_slideshow is False
    assert pm.is_muted is False
    assert pm.video_aspect_ratio == 0.5625
    assert pm.video_resolution == "1080x1920"
    assert pm.subtitles == "follow my links please"


def test_tiktok_to_normalized_thumbnail_from_videometa_cover():
    raw = _load_fixture("tiktok_post.json")
    post = tiktok_to_normalized(raw, profile_id=uuid4())
    assert post.thumbnail_url == "https://p.tiktokcdn.com/cover.jpg"


def test_tiktok_to_normalized_raw_payload_preserved():
    raw = _load_fixture("tiktok_post.json")
    post = tiktok_to_normalized(raw, profile_id=uuid4())
    assert post.raw_apify_payload == raw
