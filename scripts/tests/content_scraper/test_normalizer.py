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
