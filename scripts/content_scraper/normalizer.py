"""Pydantic models for content scraper.

`NormalizedPost` is the canonical shape one row of scraped_content takes.
Per-platform extractors (instagram_to_normalized, tiktok_to_normalized — added
in T4 and T5) turn raw Apify items into NormalizedPost instances.

`PlatformMetrics` is closed-shape (extra="forbid") so the jsonb column
stays disciplined — every key has a documented source field. New fields
go through schema review.

Spec: docs/superpowers/specs/2026-04-27-content-scraper-v1-design.md §3.3
"""
from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


PostType = Literal[
    "reel", "tiktok_video", "image", "carousel", "story",
    "story_highlight", "youtube_short", "youtube_long", "other",
]
ContentPlatform = Literal["instagram", "tiktok"]


class AudioInfo(BaseModel):
    model_config = ConfigDict(extra="forbid")
    signature: str | None = None
    artist: str | None = None
    title: str | None = None
    is_original: bool | None = None


class LocationInfo(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str | None = None
    id: str | None = None


class PlatformMetrics(BaseModel):
    model_config = ConfigDict(extra="forbid")
    audio: AudioInfo | None = None
    location: LocationInfo | None = None
    tagged_accounts: list[str] = []
    product_type: str | None = None
    effects: list[str] = []
    is_slideshow: bool | None = None
    is_muted: bool | None = None
    video_aspect_ratio: float | None = None
    video_resolution: str | None = None
    subtitles: str | None = None


class NormalizedPost(BaseModel):
    model_config = ConfigDict(extra="forbid")
    profile_id: UUID
    platform: ContentPlatform
    platform_post_id: str
    post_url: str
    post_type: PostType
    caption: str | None = None
    hook_text: str | None = None
    posted_at: datetime
    view_count: int = 0
    like_count: int = 0
    comment_count: int = 0
    share_count: int | None = None
    save_count: int | None = None
    is_pinned: bool = False
    is_sponsored: bool = False
    video_duration_seconds: float | None = None
    hashtags: list[str] = []
    mentions: list[str] = []
    media_urls: list[str] = []
    thumbnail_url: str | None = None
    platform_metrics: PlatformMetrics = PlatformMetrics()
    raw_apify_payload: dict = {}


def _ig_post_type(raw_type: str) -> PostType:
    t = (raw_type or "").lower()
    if "video" in t:
        return "reel"
    if "sidecar" in t or "carousel" in t:
        return "carousel"
    if "image" in t:
        return "image"
    return "other"


def instagram_to_normalized(item: dict, *, profile_id: UUID) -> NormalizedPost:
    """Convert a raw apify/instagram-scraper item to NormalizedPost.

    Field-source comments document which Apify field maps to which normalized
    field. Single source of truth for IG mapping.
    """
    caption = item.get("caption")
    hook_text = caption[:50] if caption else None

    music = item.get("musicInfo") or {}
    audio = AudioInfo(
        signature=str(music["audio_id"]) if music.get("audio_id") else None,
        artist=music.get("artist_name"),
        title=music.get("song_name"),
        is_original=music.get("uses_original_audio"),
    ) if music else None

    location_name = item.get("locationName")
    location_id = item.get("locationId")
    location = LocationInfo(
        name=location_name,
        id=str(location_id) if location_id else None,
    ) if (location_name or location_id) else None

    tagged = [
        u.get("username") for u in (item.get("taggedUsers") or [])
        if u.get("username")
    ]

    platform_metrics = PlatformMetrics(
        audio=audio,
        location=location,
        tagged_accounts=tagged,
        product_type=item.get("productType"),
    )

    images = item.get("images") or []
    if images:
        media_urls = [u for u in images if u]
    elif item.get("displayUrl"):
        media_urls = [item["displayUrl"]]
    else:
        media_urls = []

    view_count = (
        item.get("videoPlayCount")
        or item.get("videoViewCount")
        or 0
    )

    return NormalizedPost(
        profile_id=profile_id,
        platform="instagram",
        platform_post_id=str(item["id"]),
        post_url=item.get("url") or "",
        post_type=_ig_post_type(item.get("type", "")),
        caption=caption,
        hook_text=hook_text,
        posted_at=item["timestamp"],
        view_count=int(view_count),
        like_count=int(item.get("likesCount") or 0),
        comment_count=int(item.get("commentsCount") or 0),
        share_count=None,
        save_count=None,
        is_pinned=False,
        is_sponsored=bool(item.get("isSponsored", False)),
        video_duration_seconds=item.get("videoDuration"),
        hashtags=list(item.get("hashtags") or []),
        mentions=list(item.get("mentions") or []),
        media_urls=media_urls,
        thumbnail_url=item.get("displayUrl"),
        platform_metrics=platform_metrics,
        raw_apify_payload=item,
    )
