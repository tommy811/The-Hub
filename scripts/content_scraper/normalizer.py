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
