# Content Scraper v1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship a manual-trigger CLI that scrapes the last 30 days of Instagram and TikTok content for selected creators, writes structured rows to `scraped_content` + `content_metrics_snapshots` + `profile_metrics_snapshots`, and runs `flag_outliers` per profile.

**Architecture:** New `scripts/content_scraper/` package mirroring discovery v2's shape. CLI entry → orchestrator → batched per-platform fetchers → normalizers → transactional `commit_scrape_result` RPC → `flag_outliers` → profile snapshot. Fully Pydantic-typed, async, with dead-letter on per-profile failure.

**Tech Stack:** Python 3.11, Pydantic v2, supabase-py, apify-client, tenacity, asyncio, pytest. Postgres 17 (Supabase) for migrations + RPC.

**Spec:** `docs/superpowers/specs/2026-04-27-content-scraper-v1-design.md`

---

## File Structure

**Created:**

| File | Responsibility |
|---|---|
| `scripts/content_scraper/__init__.py` | Package marker |
| `scripts/content_scraper/normalizer.py` | `NormalizedPost`, `PlatformMetrics`, `AudioInfo`, `LocationInfo` Pydantic models + per-platform extractors |
| `scripts/content_scraper/fetchers/__init__.py` | Package marker |
| `scripts/content_scraper/fetchers/base.py` | `BaseContentFetcher` abstract contract |
| `scripts/content_scraper/fetchers/instagram.py` | `apify/instagram-scraper` driver, batched directUrls |
| `scripts/content_scraper/fetchers/tiktok.py` | `clockworks/tiktok-scraper` driver, batched profiles[] |
| `scripts/content_scraper/orchestrator.py` | Creator → profile fanout, commit, flag_outliers, snapshot, dead-letter |
| `scripts/scrape_content.py` | CLI entry point |
| `scripts/tests/content_scraper/__init__.py` | Test package marker |
| `scripts/tests/content_scraper/test_normalizer.py` | Extractor + model tests |
| `scripts/tests/content_scraper/test_fetcher_instagram.py` | Mocked IG fetcher tests |
| `scripts/tests/content_scraper/test_fetcher_tiktok.py` | Mocked TT fetcher tests |
| `scripts/tests/content_scraper/test_orchestrator.py` | Orchestrator flow tests |
| `scripts/tests/content_scraper/fixtures/instagram_post.json` | Representative IG post payload |
| `scripts/tests/content_scraper/fixtures/tiktok_post.json` | Representative TT post payload |
| `supabase/migrations/20260427000000_scraped_content_v1_columns.sql` | Schema migration 1 |
| `supabase/migrations/20260427000100_commit_scrape_result.sql` | Schema migration 2 (RPC) |

**Modified:**

| File | Reason |
|---|---|
| `PROJECT_STATE.md` | §4.1 schema (new columns), §6 (new RPC), §14 (build status), §20 (known limits — content scraper dead-letter replay), §21 (new invariants if applicable) |

**Deleted:**

| File | Reason |
|---|---|
| `scripts/apify_scraper.py` | Unintegrated sketch, superseded by content_scraper package |

---

## Task 1: Migration 1 — scraped_content v1 columns

**Files:**
- Create: `supabase/migrations/20260427000000_scraped_content_v1_columns.sql`

- [ ] **Step 1: Write the migration SQL**

Create `supabase/migrations/20260427000000_scraped_content_v1_columns.sql`:

```sql
-- Content Scraper v1 — quality_flag enum + new structural/analytical columns on scraped_content.
-- Spec: docs/superpowers/specs/2026-04-27-content-scraper-v1-design.md §3.6

-- Quality flag (anticipates §15.2 watchdog; v1 always writes 'clean')
CREATE TYPE quality_flag AS ENUM ('clean', 'suspicious', 'rejected');

ALTER TABLE scraped_content
  ADD COLUMN quality_flag quality_flag NOT NULL DEFAULT 'clean',
  ADD COLUMN quality_reason text;

CREATE INDEX scraped_content_quality_flag_idx
  ON scraped_content (profile_id, quality_flag)
  WHERE quality_flag <> 'clean';

-- Structural / analytical columns surfaced from Apify payloads
ALTER TABLE scraped_content
  ADD COLUMN is_pinned boolean NOT NULL DEFAULT false,
  ADD COLUMN is_sponsored boolean NOT NULL DEFAULT false,
  ADD COLUMN video_duration_seconds numeric,
  ADD COLUMN hashtags text[] NOT NULL DEFAULT '{}',
  ADD COLUMN mentions text[] NOT NULL DEFAULT '{}';

-- GIN indexes for array contains queries
CREATE INDEX scraped_content_hashtags_gin ON scraped_content USING GIN (hashtags);
CREATE INDEX scraped_content_mentions_gin ON scraped_content USING GIN (mentions);

-- Btree partial indexes on common filter axes (zero cost on common path)
CREATE INDEX scraped_content_is_pinned_idx ON scraped_content (profile_id, is_pinned)
  WHERE is_pinned = true;
CREATE INDEX scraped_content_is_sponsored_idx ON scraped_content (profile_id, is_sponsored)
  WHERE is_sponsored = true;
```

- [ ] **Step 2: Apply via Supabase MCP**

Use the `mcp__claude_ai_Supabase__apply_migration` tool with:
- `name`: `scraped_content_v1_columns`
- `query`: full SQL from Step 1

- [ ] **Step 3: Verify schema after apply**

Use `mcp__claude_ai_Supabase__execute_sql`:

```sql
SELECT column_name, data_type, column_default, is_nullable
FROM information_schema.columns
WHERE table_name = 'scraped_content'
  AND column_name IN ('quality_flag', 'quality_reason', 'is_pinned', 'is_sponsored',
                      'video_duration_seconds', 'hashtags', 'mentions')
ORDER BY column_name;
```

Expected: 7 rows. `quality_flag`: `USER-DEFINED`, default `'clean'::quality_flag`, NOT NULL. `is_pinned` / `is_sponsored`: `boolean`, default `false`, NOT NULL. `hashtags` / `mentions`: `ARRAY`, default `'{}'::text[]`, NOT NULL. `video_duration_seconds`: `numeric`, nullable. `quality_reason`: `text`, nullable.

- [ ] **Step 4: Commit**

```bash
git add supabase/migrations/20260427000000_scraped_content_v1_columns.sql
git commit -m "migration: scraped_content v1 columns (quality_flag, is_pinned, is_sponsored, video_duration_seconds, hashtags, mentions)"
```

---

## Task 2: Migration 2 — commit_scrape_result RPC

**Files:**
- Create: `supabase/migrations/20260427000100_commit_scrape_result.sql`

- [ ] **Step 1: Write the migration SQL**

Create `supabase/migrations/20260427000100_commit_scrape_result.sql`:

```sql
-- Content Scraper v1 — transactional commit RPC.
-- Writes scraped_content rows + content_metrics_snapshots in one transaction.
-- Spec: docs/superpowers/specs/2026-04-27-content-scraper-v1-design.md §3.4

CREATE OR REPLACE FUNCTION commit_scrape_result(
  p_profile_id uuid,
  p_posts jsonb
) RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER
AS $$
DECLARE
  v_workspace_id uuid;
  v_posts_upserted int := 0;
  v_snapshots_written int := 0;
  v_today date := CURRENT_DATE;
  v_post jsonb;
  v_content_id uuid;
BEGIN
  SELECT workspace_id INTO v_workspace_id
  FROM profiles WHERE id = p_profile_id;
  IF v_workspace_id IS NULL THEN
    RAISE EXCEPTION 'profile not found: %', p_profile_id;
  END IF;

  FOR v_post IN SELECT * FROM jsonb_array_elements(p_posts) LOOP
    INSERT INTO scraped_content (
      profile_id, platform, platform_post_id, post_url, post_type,
      caption, hook_text, posted_at,
      view_count, like_count, comment_count, share_count, save_count,
      is_pinned, is_sponsored, video_duration_seconds,
      hashtags, mentions,
      media_urls, thumbnail_url, platform_metrics, raw_apify_payload,
      quality_flag
    )
    VALUES (
      p_profile_id,
      (v_post->>'platform')::platform,
      v_post->>'platform_post_id',
      v_post->>'post_url',
      (v_post->>'post_type')::post_type,
      v_post->>'caption',
      v_post->>'hook_text',
      (v_post->>'posted_at')::timestamptz,
      COALESCE((v_post->>'view_count')::bigint, 0),
      COALESCE((v_post->>'like_count')::bigint, 0),
      COALESCE((v_post->>'comment_count')::bigint, 0),
      (v_post->>'share_count')::bigint,
      (v_post->>'save_count')::bigint,
      COALESCE((v_post->>'is_pinned')::bool, false),
      COALESCE((v_post->>'is_sponsored')::bool, false),
      (v_post->>'video_duration_seconds')::numeric,
      ARRAY(SELECT jsonb_array_elements_text(v_post->'hashtags')),
      ARRAY(SELECT jsonb_array_elements_text(v_post->'mentions')),
      ARRAY(SELECT jsonb_array_elements_text(v_post->'media_urls')),
      v_post->>'thumbnail_url',
      v_post->'platform_metrics',
      v_post->'raw_apify_payload',
      'clean'
    )
    ON CONFLICT (platform, platform_post_id) DO UPDATE SET
      view_count = EXCLUDED.view_count,
      like_count = EXCLUDED.like_count,
      comment_count = EXCLUDED.comment_count,
      share_count = EXCLUDED.share_count,
      save_count = EXCLUDED.save_count,
      is_pinned = EXCLUDED.is_pinned,
      is_sponsored = EXCLUDED.is_sponsored,
      hashtags = EXCLUDED.hashtags,
      mentions = EXCLUDED.mentions,
      caption = EXCLUDED.caption,
      platform_metrics = EXCLUDED.platform_metrics,
      raw_apify_payload = EXCLUDED.raw_apify_payload,
      updated_at = NOW()
    RETURNING id INTO v_content_id;

    v_posts_upserted := v_posts_upserted + 1;

    INSERT INTO content_metrics_snapshots (
      content_id, snapshot_date,
      view_count, like_count, comment_count, share_count, save_count
    )
    VALUES (
      v_content_id, v_today,
      COALESCE((v_post->>'view_count')::bigint, 0),
      COALESCE((v_post->>'like_count')::bigint, 0),
      COALESCE((v_post->>'comment_count')::bigint, 0),
      (v_post->>'share_count')::bigint,
      (v_post->>'save_count')::bigint
    )
    ON CONFLICT (content_id, snapshot_date) DO UPDATE SET
      view_count = EXCLUDED.view_count,
      like_count = EXCLUDED.like_count,
      comment_count = EXCLUDED.comment_count,
      share_count = EXCLUDED.share_count,
      save_count = EXCLUDED.save_count;

    v_snapshots_written := v_snapshots_written + 1;
  END LOOP;

  RETURN jsonb_build_object(
    'posts_upserted', v_posts_upserted,
    'snapshots_written', v_snapshots_written
  );
END;
$$;
```

- [ ] **Step 2: Apply via Supabase MCP**

Use `mcp__claude_ai_Supabase__apply_migration`:
- `name`: `commit_scrape_result`
- `query`: full SQL from Step 1

- [ ] **Step 3: Smoke-test the RPC**

Use `mcp__claude_ai_Supabase__execute_sql` with a real profile_id from your workspace (replace `<PROFILE_ID>` and `<UNIQUE_TEST_ID>`):

```sql
SELECT commit_scrape_result(
  '<PROFILE_ID>'::uuid,
  '[{
    "platform": "instagram",
    "platform_post_id": "rpc_smoke_<UNIQUE_TEST_ID>",
    "post_url": "https://instagram.com/p/smoke",
    "post_type": "reel",
    "caption": "smoke test",
    "hook_text": "smoke test",
    "posted_at": "2026-04-27T00:00:00Z",
    "view_count": 100,
    "like_count": 10,
    "comment_count": 1,
    "share_count": null,
    "save_count": null,
    "is_pinned": false,
    "is_sponsored": false,
    "video_duration_seconds": 15.5,
    "hashtags": ["test", "smoke"],
    "mentions": ["someone"],
    "media_urls": ["https://example.com/img.jpg"],
    "thumbnail_url": "https://example.com/thumb.jpg",
    "platform_metrics": {"audio": {"signature": "abc", "artist": "x", "title": "y", "is_original": false}},
    "raw_apify_payload": {"raw": true}
  }]'::jsonb
);
```

Expected return: `{"posts_upserted": 1, "snapshots_written": 1}`.

Verify side-effects:
```sql
SELECT id, hashtags, mentions, video_duration_seconds, quality_flag
FROM scraped_content WHERE platform_post_id = 'rpc_smoke_<UNIQUE_TEST_ID>';

SELECT * FROM content_metrics_snapshots
WHERE content_id = (SELECT id FROM scraped_content WHERE platform_post_id = 'rpc_smoke_<UNIQUE_TEST_ID>');
```

Expected: 1 scraped_content row with `hashtags={'test','smoke'}`, `mentions={'someone'}`, `video_duration_seconds=15.5`, `quality_flag='clean'`. 1 content_metrics_snapshots row for today.

- [ ] **Step 4: Re-run idempotency check**

Re-run the `SELECT commit_scrape_result(...)` from Step 3 with `view_count: 200` instead of 100. Verify:

```sql
SELECT view_count FROM scraped_content WHERE platform_post_id = 'rpc_smoke_<UNIQUE_TEST_ID>';
SELECT view_count FROM content_metrics_snapshots
WHERE content_id = (SELECT id FROM scraped_content WHERE platform_post_id = 'rpc_smoke_<UNIQUE_TEST_ID>');
```

Both should now read `200`. (Same-day re-run overwrites the snapshot.)

- [ ] **Step 5: Cleanup smoke row**

```sql
DELETE FROM scraped_content WHERE platform_post_id = 'rpc_smoke_<UNIQUE_TEST_ID>';
```

(`content_metrics_snapshots` row cascades on `content_id` FK.)

- [ ] **Step 6: Commit**

```bash
git add supabase/migrations/20260427000100_commit_scrape_result.sql
git commit -m "migration: commit_scrape_result RPC for transactional content + snapshot writes"
```

---

## Task 3: Pydantic models — NormalizedPost + PlatformMetrics

**Files:**
- Create: `scripts/content_scraper/__init__.py`
- Create: `scripts/content_scraper/normalizer.py`
- Create: `scripts/tests/content_scraper/__init__.py`
- Create: `scripts/tests/content_scraper/test_normalizer.py`

- [ ] **Step 1: Create package marker**

Create `scripts/content_scraper/__init__.py` (empty file).

- [ ] **Step 2: Create test package marker**

Create `scripts/tests/content_scraper/__init__.py` (empty file).

- [ ] **Step 3: Write the failing model tests**

Create `scripts/tests/content_scraper/test_normalizer.py`:

```python
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
```

- [ ] **Step 4: Run the tests to verify they fail**

```bash
cd "/Users/simon/OS/Living VAULT/Content OS/The Hub"
python -m pytest scripts/tests/content_scraper/test_normalizer.py -v
```

Expected: `ImportError: No module named 'content_scraper.normalizer'`.

- [ ] **Step 5: Implement the models**

Create `scripts/content_scraper/normalizer.py`:

```python
"""Pydantic models for content scraper.

`NormalizedPost` is the canonical shape one row of scraped_content takes.
Per-platform extractors (instagram_to_normalized, tiktok_to_normalized)
turn raw Apify items into NormalizedPost instances.

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
    signature: str | None = None     # platform-stable audio ID
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
    product_type: str | None = None       # IG: clips | feed | igtv
    effects: list[str] = []                # TT effect stickers
    is_slideshow: bool | None = None       # TT
    is_muted: bool | None = None           # TT
    video_aspect_ratio: float | None = None
    video_resolution: str | None = None    # e.g. "1080x1920"
    subtitles: str | None = None           # TT auto-generated subtitles


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
```

- [ ] **Step 6: Run the tests to verify they pass**

```bash
python -m pytest scripts/tests/content_scraper/test_normalizer.py -v
```

Expected: 8 passed.

- [ ] **Step 7: Commit**

```bash
git add scripts/content_scraper/ scripts/tests/content_scraper/
git commit -m "feat(content_scraper): NormalizedPost + PlatformMetrics Pydantic models"
```

---

## Task 4: Instagram extractor

**Files:**
- Modify: `scripts/content_scraper/normalizer.py` (add `instagram_to_normalized`)
- Modify: `scripts/tests/content_scraper/test_normalizer.py` (add IG fixture tests)
- Create: `scripts/tests/content_scraper/fixtures/instagram_post.json`

- [ ] **Step 1: Create the IG fixture**

Create `scripts/tests/content_scraper/fixtures/instagram_post.json`:

```json
{
  "id": "3567890123",
  "shortCode": "C-AbCdEf",
  "url": "https://www.instagram.com/p/C-AbCdEf/",
  "type": "Video",
  "productType": "clips",
  "caption": "summer vibes ☀️ #beach #vacay",
  "timestamp": "2026-04-15T14:30:00.000Z",
  "videoViewCount": 12500,
  "videoPlayCount": 18000,
  "likesCount": 850,
  "commentsCount": 42,
  "videoDuration": 28.5,
  "displayUrl": "https://scontent.cdninstagram.com/v/thumb.jpg",
  "videoUrl": "https://scontent.cdninstagram.com/v/video.mp4",
  "images": [],
  "isSponsored": false,
  "hashtags": ["beach", "vacay"],
  "mentions": ["friendhandle"],
  "musicInfo": {
    "audio_id": "987654321",
    "artist_name": "Some Artist",
    "song_name": "Summer Song",
    "uses_original_audio": false
  },
  "locationName": "Malibu Beach",
  "locationId": "12345",
  "taggedUsers": [{"username": "friend1"}, {"username": "friend2"}]
}
```

- [ ] **Step 2: Write the failing IG extractor tests**

Append to `scripts/tests/content_scraper/test_normalizer.py`:

```python
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
    assert post.post_type == "reel"  # "Video" → "reel"
    assert post.caption == "summer vibes ☀️ #beach #vacay"
    assert post.posted_at.year == 2026


def test_instagram_to_normalized_engagement():
    raw = _load_fixture("instagram_post.json")
    post = instagram_to_normalized(raw, profile_id=uuid4())
    # Prefer videoPlayCount over videoViewCount when both present
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
    assert post.view_count == 0  # static IG post has no view count
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
```

- [ ] **Step 3: Run the tests to verify they fail**

```bash
python -m pytest scripts/tests/content_scraper/test_normalizer.py -v
```

Expected: 9 new tests fail with `ImportError: cannot import name 'instagram_to_normalized'`.

- [ ] **Step 4: Implement the IG extractor**

Append to `scripts/content_scraper/normalizer.py`:

```python
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

    # Media URLs: carousel uses images[]; otherwise fall back to displayUrl
    images = item.get("images") or []
    if images:
        media_urls = [u for u in images if u]
    elif item.get("displayUrl"):
        media_urls = [item["displayUrl"]]
    else:
        media_urls = []

    # View count: prefer videoPlayCount (more reliable), fall back to videoViewCount, else 0
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
        posted_at=item["timestamp"],  # Pydantic parses ISO 8601
        view_count=int(view_count),
        like_count=int(item.get("likesCount") or 0),
        comment_count=int(item.get("commentsCount") or 0),
        share_count=None,  # IG doesn't expose
        save_count=None,
        is_pinned=False,  # IG actor doesn't expose pinned state
        is_sponsored=bool(item.get("isSponsored", False)),
        video_duration_seconds=item.get("videoDuration"),
        hashtags=list(item.get("hashtags") or []),
        mentions=list(item.get("mentions") or []),
        media_urls=media_urls,
        thumbnail_url=item.get("displayUrl"),
        platform_metrics=platform_metrics,
        raw_apify_payload=item,
    )
```

- [ ] **Step 5: Run the tests to verify they pass**

```bash
python -m pytest scripts/tests/content_scraper/test_normalizer.py -v
```

Expected: 17 passed (8 from Task 3 + 9 new).

- [ ] **Step 6: Commit**

```bash
git add scripts/content_scraper/normalizer.py scripts/tests/content_scraper/test_normalizer.py scripts/tests/content_scraper/fixtures/instagram_post.json
git commit -m "feat(content_scraper): instagram_to_normalized extractor + fixture"
```

---

## Task 5: TikTok extractor

**Files:**
- Modify: `scripts/content_scraper/normalizer.py` (add `tiktok_to_normalized`)
- Modify: `scripts/tests/content_scraper/test_normalizer.py` (add TT tests)
- Create: `scripts/tests/content_scraper/fixtures/tiktok_post.json`

- [ ] **Step 1: Create the TT fixture**

Create `scripts/tests/content_scraper/fixtures/tiktok_post.json`:

```json
{
  "id": "7234567890123456789",
  "webVideoUrl": "https://www.tiktok.com/@kira/video/7234567890123456789",
  "videoUrl": "https://v.tiktokcdn.com/video.mp4",
  "text": "follow my links pls #fyp #foryou",
  "createTimeISO": "2026-04-20T10:00:00.000Z",
  "playCount": 250000,
  "diggCount": 18500,
  "commentCount": 320,
  "shareCount": 1100,
  "collectCount": 6700,
  "videoMeta": {
    "duration": 22,
    "height": 1920,
    "width": 1080,
    "ratio": 0.5625,
    "originalCoverUrl": "https://p.tiktokcdn.com/cover.jpg"
  },
  "musicMeta": {
    "musicId": "7100000000000000000",
    "musicName": "original sound",
    "musicAuthor": "kira",
    "musicAlbum": "",
    "musicOriginal": true,
    "playUrl": "https://music.tiktokcdn.com/audio.mp3",
    "coverThumb": "https://music.tiktokcdn.com/thumb.jpg"
  },
  "hashtags": [{"name": "fyp"}, {"name": "foryou"}],
  "mentions": [],
  "effectStickers": [{"name": "Sparkle Filter"}, {"name": "Beauty"}],
  "isAd": false,
  "isMuted": false,
  "isSlideshow": false,
  "isPinned": true,
  "subtitles": "follow my links please"
}
```

- [ ] **Step 2: Write the failing TT extractor tests**

Append to `scripts/tests/content_scraper/test_normalizer.py`:

```python
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
```

- [ ] **Step 3: Run the tests to verify they fail**

```bash
python -m pytest scripts/tests/content_scraper/test_normalizer.py -v
```

Expected: 6 new tests fail with `ImportError: cannot import name 'tiktok_to_normalized'`.

- [ ] **Step 4: Implement the TT extractor**

Append to `scripts/content_scraper/normalizer.py`:

```python
def tiktok_to_normalized(item: dict, *, profile_id: UUID) -> NormalizedPost:
    """Convert a raw clockworks/tiktok-scraper item to NormalizedPost."""
    caption = item.get("text")
    hook_text = caption[:50] if caption else None

    music = item.get("musicMeta") or {}
    audio = AudioInfo(
        signature=str(music["musicId"]) if music.get("musicId") else None,
        artist=music.get("musicAuthor"),
        title=music.get("musicName"),
        is_original=music.get("musicOriginal"),
    ) if music else None

    video_meta = item.get("videoMeta") or {}
    width = video_meta.get("width")
    height = video_meta.get("height")
    resolution = f"{width}x{height}" if width and height else None

    effects = [
        e.get("name") for e in (item.get("effectStickers") or [])
        if e.get("name")
    ]

    platform_metrics = PlatformMetrics(
        audio=audio,
        location=None,  # TT actor doesn't expose location reliably
        tagged_accounts=[],  # TT mentions go in top-level mentions[]
        product_type=None,
        effects=effects,
        is_slideshow=item.get("isSlideshow"),
        is_muted=item.get("isMuted"),
        video_aspect_ratio=video_meta.get("ratio"),
        video_resolution=resolution,
        subtitles=item.get("subtitles"),
    )

    hashtags_raw = item.get("hashtags") or []
    hashtags = [
        h.get("name") for h in hashtags_raw if h.get("name")
    ] if hashtags_raw else []

    media_urls = item.get("mediaUrls") or (
        [item["videoUrl"]] if item.get("videoUrl") else []
    )

    return NormalizedPost(
        profile_id=profile_id,
        platform="tiktok",
        platform_post_id=str(item["id"]),
        post_url=item.get("webVideoUrl") or "",
        post_type="tiktok_video",
        caption=caption,
        hook_text=hook_text,
        posted_at=item["createTimeISO"],
        view_count=int(item.get("playCount") or 0),
        like_count=int(item.get("diggCount") or 0),
        comment_count=int(item.get("commentCount") or 0),
        share_count=int(item["shareCount"]) if item.get("shareCount") is not None else None,
        save_count=int(item["collectCount"]) if item.get("collectCount") is not None else None,
        is_pinned=bool(item.get("isPinned", False)),
        is_sponsored=bool(item.get("isAd", False)),
        video_duration_seconds=video_meta.get("duration"),
        hashtags=hashtags,
        mentions=list(item.get("mentions") or []),
        media_urls=media_urls,
        thumbnail_url=video_meta.get("originalCoverUrl"),
        platform_metrics=platform_metrics,
        raw_apify_payload=item,
    )
```

- [ ] **Step 5: Run the tests to verify they pass**

```bash
python -m pytest scripts/tests/content_scraper/test_normalizer.py -v
```

Expected: 23 passed (17 previous + 6 new).

- [ ] **Step 6: Commit**

```bash
git add scripts/content_scraper/normalizer.py scripts/tests/content_scraper/test_normalizer.py scripts/tests/content_scraper/fixtures/tiktok_post.json
git commit -m "feat(content_scraper): tiktok_to_normalized extractor + fixture"
```

---

## Task 6: Instagram fetcher

**Files:**
- Create: `scripts/content_scraper/fetchers/__init__.py`
- Create: `scripts/content_scraper/fetchers/base.py`
- Create: `scripts/content_scraper/fetchers/instagram.py`
- Create: `scripts/tests/content_scraper/test_fetcher_instagram.py`

- [ ] **Step 1: Create package marker**

Create `scripts/content_scraper/fetchers/__init__.py` (empty file).

- [ ] **Step 2: Write the BaseContentFetcher contract**

Create `scripts/content_scraper/fetchers/base.py`:

```python
"""Base contract for platform content fetchers.

Each subclass implements `fetch(profiles, since)` and returns a dict
mapping profile_id → list of NormalizedPost. The orchestrator calls one
fetcher per platform per CLI run, batching all profiles for that platform
into one Apify call (cost optimization — see spec Appendix C).
"""
from __future__ import annotations
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Iterable
from uuid import UUID

from content_scraper.normalizer import NormalizedPost


class ProfileTarget:
    """A single profile to scrape, plus the inputs the fetcher needs."""
    def __init__(self, *, profile_id: UUID, handle: str, profile_url: str | None = None):
        self.profile_id = profile_id
        self.handle = handle
        self.profile_url = profile_url

    def __repr__(self) -> str:
        return f"ProfileTarget({self.handle!r}, {self.profile_id})"


class BaseContentFetcher(ABC):
    """Platform-agnostic content fetcher contract.

    Subclasses are responsible for:
      - Translating ProfileTargets into the Apify actor's input shape
      - Issuing ONE actor call covering all targets
      - Disaggregating results back to per-profile lists
      - Calling the right normalizer (instagram_to_normalized / tiktok_to_normalized)
      - Wrapping transient errors with tenacity (use is_transient_apify_error)
    """

    @abstractmethod
    async def fetch(
        self,
        profiles: Iterable[ProfileTarget],
        *,
        since: datetime,
    ) -> dict[UUID, list[NormalizedPost]]:
        """Fetch posts for the given profiles since the given datetime.

        Returns a dict keyed by profile_id. Profiles that returned no posts
        (private, login wall, captcha, no posts in window) are absent from
        the dict — the orchestrator treats absence as "skip with warning."
        """
```

- [ ] **Step 3: Write the failing IG fetcher tests**

Create `scripts/tests/content_scraper/test_fetcher_instagram.py`:

```python
"""Tests for InstagramContentFetcher.

Mocks the ApifyClient so we can assert on the actor input shape and the
return-disaggregation logic without burning real Apify credits.
"""
import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from content_scraper.fetchers.base import ProfileTarget
from content_scraper.fetchers.instagram import InstagramContentFetcher

FIXTURE_DIR = Path(__file__).parent / "fixtures"


def _load_fixture(name: str) -> dict:
    return json.loads((FIXTURE_DIR / name).read_text())


def _make_apify_mock(items: list[dict]) -> MagicMock:
    """Mock an ApifyClient where actor(...).call(...) returns a run dict
    and dataset(...).list_items() returns the given items.
    """
    apify = MagicMock()
    actor = MagicMock()
    actor.call.return_value = {"defaultDatasetId": "ds_test"}
    apify.actor.return_value = actor
    dataset = MagicMock()
    dataset_items_result = MagicMock()
    dataset_items_result.items = items
    dataset.list_items.return_value = dataset_items_result
    apify.dataset.return_value = dataset
    return apify


def test_instagram_fetcher_passes_directUrls_for_all_profiles():
    pid_a, pid_b = uuid4(), uuid4()
    apify = _make_apify_mock([])
    fetcher = InstagramContentFetcher(apify_client=apify)

    profiles = [
        ProfileTarget(profile_id=pid_a, handle="creator_a"),
        ProfileTarget(profile_id=pid_b, handle="creator_b"),
    ]
    asyncio.run(fetcher.fetch(profiles, since=datetime(2026, 4, 1, tzinfo=timezone.utc)))

    # Assert one actor call with both URLs
    apify.actor.assert_called_once_with("apify/instagram-scraper")
    call_input = apify.actor.return_value.call.call_args.kwargs["run_input"]
    assert call_input["directUrls"] == [
        "https://www.instagram.com/creator_a/",
        "https://www.instagram.com/creator_b/",
    ]
    assert call_input["resultsType"] == "posts"


def test_instagram_fetcher_passes_since_filter():
    apify = _make_apify_mock([])
    fetcher = InstagramContentFetcher(apify_client=apify)
    since = datetime(2026, 4, 1, tzinfo=timezone.utc)
    asyncio.run(fetcher.fetch(
        [ProfileTarget(profile_id=uuid4(), handle="x")],
        since=since,
    ))
    call_input = apify.actor.return_value.call.call_args.kwargs["run_input"]
    assert call_input["onlyPostsNewerThan"] == "2026-04-01"


def test_instagram_fetcher_disaggregates_by_owner_username():
    pid_a, pid_b = uuid4(), uuid4()
    raw = _load_fixture("instagram_post.json")
    item_a = {**raw, "id": "post_a_1", "ownerUsername": "creator_a"}
    item_b1 = {**raw, "id": "post_b_1", "ownerUsername": "creator_b"}
    item_b2 = {**raw, "id": "post_b_2", "ownerUsername": "creator_b"}
    apify = _make_apify_mock([item_a, item_b1, item_b2])
    fetcher = InstagramContentFetcher(apify_client=apify)

    result = asyncio.run(fetcher.fetch(
        [
            ProfileTarget(profile_id=pid_a, handle="creator_a"),
            ProfileTarget(profile_id=pid_b, handle="creator_b"),
        ],
        since=datetime(2026, 4, 1, tzinfo=timezone.utc),
    ))

    assert pid_a in result
    assert pid_b in result
    assert len(result[pid_a]) == 1
    assert len(result[pid_b]) == 2
    assert result[pid_a][0].platform_post_id == "post_a_1"
    assert {p.platform_post_id for p in result[pid_b]} == {"post_b_1", "post_b_2"}


def test_instagram_fetcher_omits_profiles_with_zero_posts():
    pid_a, pid_b = uuid4(), uuid4()
    raw = _load_fixture("instagram_post.json")
    item_a = {**raw, "id": "post_a", "ownerUsername": "creator_a"}
    apify = _make_apify_mock([item_a])  # only creator_a has posts
    fetcher = InstagramContentFetcher(apify_client=apify)

    result = asyncio.run(fetcher.fetch(
        [
            ProfileTarget(profile_id=pid_a, handle="creator_a"),
            ProfileTarget(profile_id=pid_b, handle="creator_b"),
        ],
        since=datetime(2026, 4, 1, tzinfo=timezone.utc),
    ))

    assert pid_a in result
    assert pid_b not in result  # absent = "skip with warning" in orchestrator


def test_instagram_fetcher_skips_unmapped_owner():
    """An item whose ownerUsername doesn't match any profile target is dropped."""
    pid_a = uuid4()
    raw = _load_fixture("instagram_post.json")
    item_orphan = {**raw, "id": "orphan", "ownerUsername": "totally_other"}
    apify = _make_apify_mock([item_orphan])
    fetcher = InstagramContentFetcher(apify_client=apify)
    result = asyncio.run(fetcher.fetch(
        [ProfileTarget(profile_id=pid_a, handle="creator_a")],
        since=datetime(2026, 4, 1, tzinfo=timezone.utc),
    ))
    assert result == {}


def test_instagram_fetcher_empty_profile_list_makes_no_apify_call():
    apify = _make_apify_mock([])
    fetcher = InstagramContentFetcher(apify_client=apify)
    result = asyncio.run(fetcher.fetch([], since=datetime(2026, 4, 1, tzinfo=timezone.utc)))
    assert result == {}
    apify.actor.assert_not_called()
```

- [ ] **Step 4: Run the tests to verify they fail**

```bash
python -m pytest scripts/tests/content_scraper/test_fetcher_instagram.py -v
```

Expected: 6 tests fail with `ImportError: cannot import name 'InstagramContentFetcher'`.

- [ ] **Step 5: Implement the IG fetcher**

Create `scripts/content_scraper/fetchers/instagram.py`:

```python
"""Instagram content fetcher — apify/instagram-scraper, batched directUrls."""
from __future__ import annotations
import asyncio
import logging
from datetime import datetime
from typing import Iterable
from uuid import UUID

from apify_client import ApifyClient
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception

from content_scraper.fetchers.base import BaseContentFetcher, ProfileTarget
from content_scraper.normalizer import NormalizedPost, instagram_to_normalized
from fetchers.base import is_transient_apify_error  # reuse discovery v2 predicate

_log = logging.getLogger(__name__)
_ACTOR_ID = "apify/instagram-scraper"


class InstagramContentFetcher(BaseContentFetcher):
    def __init__(self, *, apify_client: ApifyClient):
        self._apify = apify_client

    async def fetch(
        self,
        profiles: Iterable[ProfileTarget],
        *,
        since: datetime,
    ) -> dict[UUID, list[NormalizedPost]]:
        targets = list(profiles)
        if not targets:
            return {}

        handle_to_pid: dict[str, UUID] = {p.handle.lower(): p.profile_id for p in targets}
        items = await asyncio.to_thread(
            self._call_actor,
            direct_urls=[f"https://www.instagram.com/{p.handle}/" for p in targets],
            since=since,
        )

        out: dict[UUID, list[NormalizedPost]] = {}
        for item in items:
            owner = (item.get("ownerUsername") or "").lower()
            pid = handle_to_pid.get(owner)
            if pid is None:
                continue
            try:
                normalized = instagram_to_normalized(item, profile_id=pid)
            except Exception as exc:
                _log.warning("ig_normalize_failed id=%s err=%s", item.get("id"), exc)
                continue
            out.setdefault(pid, []).append(normalized)
        return out

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=2, min=3, max=15),
        retry=retry_if_exception(is_transient_apify_error),
        reraise=True,
    )
    def _call_actor(self, *, direct_urls: list[str], since: datetime) -> list[dict]:
        run_input = {
            "directUrls": direct_urls,
            "resultsType": "posts",
            "resultsLimit": 200,  # cap per-profile; 30d typically yields <60 for most creators
            "onlyPostsNewerThan": since.date().isoformat(),
            "addParentData": False,
        }
        run = self._apify.actor(_ACTOR_ID).call(run_input=run_input)
        ds_id = run["defaultDatasetId"]
        return self._apify.dataset(ds_id).list_items().items
```

- [ ] **Step 6: Run the tests to verify they pass**

```bash
python -m pytest scripts/tests/content_scraper/test_fetcher_instagram.py -v
```

Expected: 6 passed.

- [ ] **Step 7: Commit**

```bash
git add scripts/content_scraper/fetchers/ scripts/tests/content_scraper/test_fetcher_instagram.py
git commit -m "feat(content_scraper): InstagramContentFetcher with batched directUrls + per-owner disaggregation"
```

---

## Task 7: TikTok fetcher

**Files:**
- Create: `scripts/content_scraper/fetchers/tiktok.py`
- Create: `scripts/tests/content_scraper/test_fetcher_tiktok.py`

- [ ] **Step 1: Write the failing TT fetcher tests**

Create `scripts/tests/content_scraper/test_fetcher_tiktok.py`:

```python
"""Tests for TikTokContentFetcher."""
import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock
from uuid import uuid4

from content_scraper.fetchers.base import ProfileTarget
from content_scraper.fetchers.tiktok import TikTokContentFetcher

FIXTURE_DIR = Path(__file__).parent / "fixtures"


def _load_fixture(name: str) -> dict:
    return json.loads((FIXTURE_DIR / name).read_text())


def _make_apify_mock(items: list[dict]) -> MagicMock:
    apify = MagicMock()
    actor = MagicMock()
    actor.call.return_value = {"defaultDatasetId": "ds_test"}
    apify.actor.return_value = actor
    dataset = MagicMock()
    items_result = MagicMock()
    items_result.items = items
    dataset.list_items.return_value = items_result
    apify.dataset.return_value = dataset
    return apify


def test_tiktok_fetcher_passes_profiles_for_all_targets():
    apify = _make_apify_mock([])
    fetcher = TikTokContentFetcher(apify_client=apify)
    asyncio.run(fetcher.fetch(
        [
            ProfileTarget(profile_id=uuid4(), handle="kira"),
            ProfileTarget(profile_id=uuid4(), handle="esmae"),
        ],
        since=datetime(2026, 4, 1, tzinfo=timezone.utc),
    ))
    apify.actor.assert_called_once_with("clockworks/tiktok-scraper")
    call_input = apify.actor.return_value.call.call_args.kwargs["run_input"]
    assert call_input["profiles"] == ["kira", "esmae"]


def test_tiktok_fetcher_passes_since_via_oldestpostdate():
    apify = _make_apify_mock([])
    fetcher = TikTokContentFetcher(apify_client=apify)
    since = datetime(2026, 4, 1, tzinfo=timezone.utc)
    asyncio.run(fetcher.fetch(
        [ProfileTarget(profile_id=uuid4(), handle="x")],
        since=since,
    ))
    call_input = apify.actor.return_value.call.call_args.kwargs["run_input"]
    assert call_input["oldestPostDate"] == "2026-04-01"


def test_tiktok_fetcher_disaggregates_by_authormeta_name():
    pid_a, pid_b = uuid4(), uuid4()
    raw = _load_fixture("tiktok_post.json")
    item_a = {**raw, "id": "tt_a", "authorMeta": {"name": "kira"}}
    item_b = {**raw, "id": "tt_b", "authorMeta": {"name": "esmae"}}
    apify = _make_apify_mock([item_a, item_b])
    fetcher = TikTokContentFetcher(apify_client=apify)
    result = asyncio.run(fetcher.fetch(
        [
            ProfileTarget(profile_id=pid_a, handle="kira"),
            ProfileTarget(profile_id=pid_b, handle="esmae"),
        ],
        since=datetime(2026, 4, 1, tzinfo=timezone.utc),
    ))
    assert pid_a in result and pid_b in result
    assert result[pid_a][0].platform_post_id == "tt_a"
    assert result[pid_b][0].platform_post_id == "tt_b"


def test_tiktok_fetcher_handles_authormeta_missing():
    """Posts without authorMeta should be dropped, not crash."""
    pid_a = uuid4()
    raw = _load_fixture("tiktok_post.json")
    item_no_author = {**raw, "id": "no_author"}
    item_no_author.pop("authorMeta", None)
    apify = _make_apify_mock([item_no_author])
    fetcher = TikTokContentFetcher(apify_client=apify)
    result = asyncio.run(fetcher.fetch(
        [ProfileTarget(profile_id=pid_a, handle="kira")],
        since=datetime(2026, 4, 1, tzinfo=timezone.utc),
    ))
    assert result == {}


def test_tiktok_fetcher_empty_profile_list_makes_no_apify_call():
    apify = _make_apify_mock([])
    fetcher = TikTokContentFetcher(apify_client=apify)
    result = asyncio.run(fetcher.fetch([], since=datetime(2026, 4, 1, tzinfo=timezone.utc)))
    assert result == {}
    apify.actor.assert_not_called()
```

- [ ] **Step 2: Run the tests to verify they fail**

```bash
python -m pytest scripts/tests/content_scraper/test_fetcher_tiktok.py -v
```

Expected: 5 tests fail with `ImportError: cannot import name 'TikTokContentFetcher'`.

- [ ] **Step 3: Implement the TT fetcher**

Create `scripts/content_scraper/fetchers/tiktok.py`:

```python
"""TikTok content fetcher — clockworks/tiktok-scraper, batched profiles[]."""
from __future__ import annotations
import asyncio
import logging
from datetime import datetime
from typing import Iterable
from uuid import UUID

from apify_client import ApifyClient
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception

from content_scraper.fetchers.base import BaseContentFetcher, ProfileTarget
from content_scraper.normalizer import NormalizedPost, tiktok_to_normalized
from fetchers.base import is_transient_apify_error

_log = logging.getLogger(__name__)
_ACTOR_ID = "clockworks/tiktok-scraper"


class TikTokContentFetcher(BaseContentFetcher):
    def __init__(self, *, apify_client: ApifyClient):
        self._apify = apify_client

    async def fetch(
        self,
        profiles: Iterable[ProfileTarget],
        *,
        since: datetime,
    ) -> dict[UUID, list[NormalizedPost]]:
        targets = list(profiles)
        if not targets:
            return {}

        handle_to_pid: dict[str, UUID] = {p.handle.lower(): p.profile_id for p in targets}
        items = await asyncio.to_thread(
            self._call_actor,
            handles=[p.handle for p in targets],
            since=since,
        )

        out: dict[UUID, list[NormalizedPost]] = {}
        for item in items:
            author = (item.get("authorMeta") or {}).get("name")
            if not author:
                continue
            pid = handle_to_pid.get(author.lower())
            if pid is None:
                continue
            try:
                normalized = tiktok_to_normalized(item, profile_id=pid)
            except Exception as exc:
                _log.warning("tt_normalize_failed id=%s err=%s", item.get("id"), exc)
                continue
            out.setdefault(pid, []).append(normalized)
        return out

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=2, min=3, max=15),
        retry=retry_if_exception(is_transient_apify_error),
        reraise=True,
    )
    def _call_actor(self, *, handles: list[str], since: datetime) -> list[dict]:
        run_input = {
            "profiles": handles,
            "resultsPerPage": 200,
            "shouldDownloadVideos": False,
            "shouldDownloadCovers": False,
            "shouldDownloadSubtitles": False,
            "oldestPostDate": since.date().isoformat(),
        }
        run = self._apify.actor(_ACTOR_ID).call(run_input=run_input)
        ds_id = run["defaultDatasetId"]
        return self._apify.dataset(ds_id).list_items().items
```

- [ ] **Step 4: Run the tests to verify they pass**

```bash
python -m pytest scripts/tests/content_scraper/test_fetcher_tiktok.py -v
```

Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add scripts/content_scraper/fetchers/tiktok.py scripts/tests/content_scraper/test_fetcher_tiktok.py
git commit -m "feat(content_scraper): TikTokContentFetcher with batched profiles[] + per-author disaggregation"
```

---

## Task 8: Orchestrator — happy path

**Files:**
- Create: `scripts/content_scraper/orchestrator.py`
- Create: `scripts/tests/content_scraper/test_orchestrator.py`

- [ ] **Step 1: Write the failing orchestrator tests**

Create `scripts/tests/content_scraper/test_orchestrator.py`:

```python
"""Tests for the content scraper orchestrator.

Mocks fetchers + supabase RPCs; asserts the per-profile sequence
commit_scrape_result → flag_outliers → profile_metrics_snapshots is
emitted in the right order with the right inputs.
"""
import asyncio
from datetime import datetime, timezone
from unittest.mock import MagicMock, call
from uuid import uuid4

import pytest

from content_scraper.fetchers.base import ProfileTarget
from content_scraper.normalizer import NormalizedPost, PlatformMetrics
from content_scraper.orchestrator import ScrapeOrchestrator, ProfileScope


def _make_post(profile_id, post_id="p1", view_count=100) -> NormalizedPost:
    return NormalizedPost(
        profile_id=profile_id,
        platform="instagram",
        platform_post_id=post_id,
        post_url=f"https://instagram.com/p/{post_id}",
        post_type="reel",
        caption="x",
        hook_text="x",
        posted_at=datetime(2026, 4, 27, tzinfo=timezone.utc),
        view_count=view_count,
        like_count=10,
        comment_count=1,
        platform_metrics=PlatformMetrics(),
        raw_apify_payload={},
    )


def _supabase_mock_with_outlier_query(outlier_count: int = 0) -> MagicMock:
    """Build a supabase mock where the post-flag query returns `outlier_count` rows."""
    sb = MagicMock()
    rpc_chain = MagicMock()
    rpc_chain.execute.return_value = MagicMock(data={"posts_upserted": 1, "snapshots_written": 1})
    sb.rpc.return_value = rpc_chain

    # profile_metrics_snapshots upsert chain
    table_chain = MagicMock()
    table_chain.upsert.return_value = table_chain
    table_chain.execute.return_value = MagicMock(data=[{}])

    # scraped_content select for outlier count + median view
    sc_select_chain = MagicMock()
    sc_select_chain.eq.return_value = sc_select_chain
    sc_select_chain.execute.return_value = MagicMock(
        data=[{"view_count": 100, "is_outlier": i < outlier_count} for i in range(5)]
    )
    sb.table.side_effect = lambda name: {
        "profile_metrics_snapshots": table_chain,
        "scraped_content": MagicMock(select=lambda *a, **k: sc_select_chain),
    }.get(name, MagicMock())
    return sb


def test_orchestrator_calls_commit_then_flag_outliers_per_profile():
    pid = uuid4()
    post = _make_post(pid)
    ig_fetcher = MagicMock()
    ig_fetcher.fetch = MagicMock(return_value=_async_return({pid: [post]}))
    tt_fetcher = MagicMock()
    tt_fetcher.fetch = MagicMock(return_value=_async_return({}))

    sb = _supabase_mock_with_outlier_query()
    orch = ScrapeOrchestrator(
        supabase=sb,
        ig_fetcher=ig_fetcher,
        tt_fetcher=tt_fetcher,
        dead_letter_path=None,
    )
    asyncio.run(orch.run([
        ProfileScope(profile_id=pid, handle="x", platform="instagram", creator_id=uuid4()),
    ], since=datetime(2026, 4, 1, tzinfo=timezone.utc)))

    rpc_calls = sb.rpc.call_args_list
    assert any(c.args[0] == "commit_scrape_result" for c in rpc_calls)
    assert any(c.args[0] == "flag_outliers" for c in rpc_calls)

    # commit_scrape_result is called BEFORE flag_outliers
    rpc_names = [c.args[0] for c in rpc_calls]
    commit_idx = rpc_names.index("commit_scrape_result")
    flag_idx = rpc_names.index("flag_outliers")
    assert commit_idx < flag_idx


def test_orchestrator_skips_profiles_with_zero_posts():
    pid = uuid4()
    ig_fetcher = MagicMock()
    ig_fetcher.fetch = MagicMock(return_value=_async_return({}))  # empty
    tt_fetcher = MagicMock()
    tt_fetcher.fetch = MagicMock(return_value=_async_return({}))

    sb = _supabase_mock_with_outlier_query()
    orch = ScrapeOrchestrator(
        supabase=sb,
        ig_fetcher=ig_fetcher,
        tt_fetcher=tt_fetcher,
        dead_letter_path=None,
    )
    asyncio.run(orch.run([
        ProfileScope(profile_id=pid, handle="x", platform="instagram", creator_id=uuid4()),
    ], since=datetime(2026, 4, 1, tzinfo=timezone.utc)))

    # No commit / flag_outliers because no posts
    sb.rpc.assert_not_called()


def test_orchestrator_groups_by_platform_and_calls_each_fetcher_once():
    pid_ig, pid_tt = uuid4(), uuid4()
    post_ig = _make_post(pid_ig, post_id="ig1")
    post_tt = _make_post(pid_tt, post_id="tt1")
    post_tt = post_tt.model_copy(update={"platform": "tiktok", "post_type": "tiktok_video"})

    ig_fetcher = MagicMock()
    ig_fetcher.fetch = MagicMock(return_value=_async_return({pid_ig: [post_ig]}))
    tt_fetcher = MagicMock()
    tt_fetcher.fetch = MagicMock(return_value=_async_return({pid_tt: [post_tt]}))

    sb = _supabase_mock_with_outlier_query()
    orch = ScrapeOrchestrator(
        supabase=sb, ig_fetcher=ig_fetcher, tt_fetcher=tt_fetcher,
        dead_letter_path=None,
    )
    asyncio.run(orch.run([
        ProfileScope(profile_id=pid_ig, handle="x", platform="instagram", creator_id=uuid4()),
        ProfileScope(profile_id=pid_tt, handle="y", platform="tiktok", creator_id=uuid4()),
    ], since=datetime(2026, 4, 1, tzinfo=timezone.utc)))

    ig_fetcher.fetch.assert_called_once()
    tt_fetcher.fetch.assert_called_once()


def _async_return(value):
    """Helper: make a MagicMock return an awaitable that resolves to `value`."""
    async def _r(*args, **kwargs):
        return value
    return _r()
```

- [ ] **Step 2: Run the tests to verify they fail**

```bash
python -m pytest scripts/tests/content_scraper/test_orchestrator.py -v
```

Expected: 3 tests fail with `ImportError`.

- [ ] **Step 3: Implement the orchestrator (happy path)**

Create `scripts/content_scraper/orchestrator.py`:

```python
"""Content scraper orchestrator.

Resolves the per-platform fetcher dispatch, calls commit_scrape_result,
runs flag_outliers per profile, and writes the daily profile metrics
snapshot. Error handling + dead-letter come in Task 9.
"""
from __future__ import annotations
import asyncio
import logging
import statistics
from dataclasses import dataclass
from datetime import datetime, date
from typing import Iterable
from uuid import UUID

from supabase import Client

from content_scraper.fetchers.base import BaseContentFetcher, ProfileTarget
from content_scraper.normalizer import NormalizedPost

_log = logging.getLogger(__name__)


@dataclass
class ProfileScope:
    profile_id: UUID
    handle: str
    platform: str  # "instagram" | "tiktok"
    creator_id: UUID


@dataclass
class ScrapeRunSummary:
    profiles_scraped: int = 0
    profiles_skipped: int = 0
    posts_upserted: int = 0
    outliers_flagged: int = 0
    failures: int = 0


class ScrapeOrchestrator:
    def __init__(
        self,
        *,
        supabase: Client,
        ig_fetcher: BaseContentFetcher,
        tt_fetcher: BaseContentFetcher,
        dead_letter_path: str | None,
    ):
        self._sb = supabase
        self._ig = ig_fetcher
        self._tt = tt_fetcher
        self._dead_letter_path = dead_letter_path

    async def run(
        self,
        scopes: Iterable[ProfileScope],
        *,
        since: datetime,
    ) -> ScrapeRunSummary:
        scope_list = list(scopes)
        ig_targets, tt_targets = [], []
        scope_by_pid: dict[UUID, ProfileScope] = {}
        for s in scope_list:
            scope_by_pid[s.profile_id] = s
            target = ProfileTarget(profile_id=s.profile_id, handle=s.handle)
            if s.platform == "instagram":
                ig_targets.append(target)
            elif s.platform == "tiktok":
                tt_targets.append(target)

        ig_result, tt_result = await asyncio.gather(
            self._ig.fetch(ig_targets, since=since),
            self._tt.fetch(tt_targets, since=since),
        )

        per_profile: dict[UUID, list[NormalizedPost]] = {}
        per_profile.update(ig_result)
        per_profile.update(tt_result)

        summary = ScrapeRunSummary()
        for s in scope_list:
            posts = per_profile.get(s.profile_id, [])
            if not posts:
                summary.profiles_skipped += 1
                _log.info("scrape_skip profile_id=%s handle=%s reason=no_posts",
                          s.profile_id, s.handle)
                continue
            await self._commit_one_profile(s, posts, summary)
        return summary

    async def _commit_one_profile(
        self,
        scope: ProfileScope,
        posts: list[NormalizedPost],
        summary: ScrapeRunSummary,
    ) -> None:
        # commit_scrape_result (transactional posts + snapshots)
        payload = [p.model_dump(mode="json") for p in posts]
        commit_resp = await asyncio.to_thread(
            lambda: self._sb.rpc("commit_scrape_result", {
                "p_profile_id": str(scope.profile_id),
                "p_posts": payload,
            }).execute()
        )
        commit_data = commit_resp.data or {}
        summary.posts_upserted += int(commit_data.get("posts_upserted", 0))

        # flag_outliers per profile
        await asyncio.to_thread(
            lambda: self._sb.rpc("flag_outliers", {
                "p_profile_id": str(scope.profile_id),
            }).execute()
        )

        # profile_metrics_snapshots
        await self._write_profile_snapshot(scope, posts, summary)
        summary.profiles_scraped += 1

    async def _write_profile_snapshot(
        self,
        scope: ProfileScope,
        posts: list[NormalizedPost],
        summary: ScrapeRunSummary,
    ) -> None:
        # Read view counts + is_outlier from DB after flag_outliers ran
        rows_resp = await asyncio.to_thread(
            lambda: self._sb.table("scraped_content")
                .select("view_count,is_outlier")
                .eq("profile_id", str(scope.profile_id))
                .execute()
        )
        rows = rows_resp.data or []
        view_counts = [r.get("view_count") or 0 for r in rows]
        outlier_count = sum(1 for r in rows if r.get("is_outlier"))
        median_views = int(statistics.median(view_counts)) if view_counts else 0
        summary.outliers_flagged += outlier_count

        # follower_count from profiles row
        prof_resp = await asyncio.to_thread(
            lambda: self._sb.table("profiles")
                .select("follower_count")
                .eq("id", str(scope.profile_id))
                .single()
                .execute()
        )
        follower_count = (prof_resp.data or {}).get("follower_count")

        await asyncio.to_thread(
            lambda: self._sb.table("profile_metrics_snapshots").upsert({
                "profile_id": str(scope.profile_id),
                "snapshot_date": date.today().isoformat(),
                "follower_count": follower_count,
                "median_views": median_views,
                "outlier_count": outlier_count,
                # avg_engagement_rate left NULL in v1 (depends on engagement_rate generated col)
                # quality_score left NULL (Phase 3 content_analysis)
            }, on_conflict="profile_id,snapshot_date").execute()
        )
```

- [ ] **Step 4: Run the tests to verify they pass**

```bash
python -m pytest scripts/tests/content_scraper/test_orchestrator.py -v
```

Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add scripts/content_scraper/orchestrator.py scripts/tests/content_scraper/test_orchestrator.py
git commit -m "feat(content_scraper): orchestrator happy path — commit + flag_outliers + profile snapshot"
```

---

## Task 9: Orchestrator — error handling + dead-letter

**Files:**
- Modify: `scripts/content_scraper/orchestrator.py`
- Modify: `scripts/tests/content_scraper/test_orchestrator.py`

- [ ] **Step 1: Add the failing dead-letter tests**

Append to `scripts/tests/content_scraper/test_orchestrator.py`:

```python
import json
import tempfile
from pathlib import Path


def test_orchestrator_dead_letters_rpc_failure_and_continues():
    pid_a, pid_b = uuid4(), uuid4()
    post_a = _make_post(pid_a, "a1")
    post_b = _make_post(pid_b, "b1")
    ig_fetcher = MagicMock()
    ig_fetcher.fetch = MagicMock(return_value=_async_return({pid_a: [post_a], pid_b: [post_b]}))
    tt_fetcher = MagicMock()
    tt_fetcher.fetch = MagicMock(return_value=_async_return({}))

    # First commit succeeds, second raises
    sb = _supabase_mock_with_outlier_query()
    call_count = {"n": 0}

    def rpc_side_effect(name, args):
        call_count["n"] += 1
        chain = MagicMock()
        if name == "commit_scrape_result" and args["p_profile_id"] == str(pid_b):
            chain.execute.side_effect = RuntimeError("rpc exploded")
        else:
            chain.execute.return_value = MagicMock(data={"posts_upserted": 1, "snapshots_written": 1})
        return chain
    sb.rpc.side_effect = rpc_side_effect

    with tempfile.TemporaryDirectory() as tmpdir:
        dl_path = str(Path(tmpdir) / "dead_letter.jsonl")
        orch = ScrapeOrchestrator(
            supabase=sb, ig_fetcher=ig_fetcher, tt_fetcher=tt_fetcher,
            dead_letter_path=dl_path,
        )
        summary = asyncio.run(orch.run([
            ProfileScope(profile_id=pid_a, handle="a", platform="instagram", creator_id=uuid4()),
            ProfileScope(profile_id=pid_b, handle="b", platform="instagram", creator_id=uuid4()),
        ], since=datetime(2026, 4, 1, tzinfo=timezone.utc)))

        assert summary.profiles_scraped == 1
        assert summary.failures == 1

        dl_lines = Path(dl_path).read_text().strip().splitlines()
        assert len(dl_lines) == 1
        entry = json.loads(dl_lines[0])
        assert entry["profile_id"] == str(pid_b)
        assert entry["platform"] == "instagram"
        assert "rpc exploded" in entry["error"]


def test_orchestrator_no_dead_letter_path_logs_only():
    """When dead_letter_path is None, failures still don't crash the run."""
    pid = uuid4()
    post = _make_post(pid)
    ig_fetcher = MagicMock()
    ig_fetcher.fetch = MagicMock(return_value=_async_return({pid: [post]}))
    tt_fetcher = MagicMock()
    tt_fetcher.fetch = MagicMock(return_value=_async_return({}))

    sb = MagicMock()
    chain = MagicMock()
    chain.execute.side_effect = RuntimeError("boom")
    sb.rpc.return_value = chain

    orch = ScrapeOrchestrator(
        supabase=sb, ig_fetcher=ig_fetcher, tt_fetcher=tt_fetcher,
        dead_letter_path=None,
    )
    summary = asyncio.run(orch.run([
        ProfileScope(profile_id=pid, handle="a", platform="instagram", creator_id=uuid4()),
    ], since=datetime(2026, 4, 1, tzinfo=timezone.utc)))
    assert summary.failures == 1
```

- [ ] **Step 2: Run the tests to verify they fail**

```bash
python -m pytest scripts/tests/content_scraper/test_orchestrator.py -v
```

Expected: 2 new tests fail (RuntimeError propagates instead of being caught + dead-lettered).

- [ ] **Step 3: Wrap `_commit_one_profile` in try/except + dead-letter writer**

In `scripts/content_scraper/orchestrator.py`:

Replace the `_commit_one_profile` method with this guarded version, and add a `_dead_letter` helper:

```python
    async def _commit_one_profile(
        self,
        scope: ProfileScope,
        posts: list[NormalizedPost],
        summary: ScrapeRunSummary,
    ) -> None:
        try:
            payload = [p.model_dump(mode="json") for p in posts]
            commit_resp = await asyncio.to_thread(
                lambda: self._sb.rpc("commit_scrape_result", {
                    "p_profile_id": str(scope.profile_id),
                    "p_posts": payload,
                }).execute()
            )
            commit_data = commit_resp.data or {}
            summary.posts_upserted += int(commit_data.get("posts_upserted", 0))

            await asyncio.to_thread(
                lambda: self._sb.rpc("flag_outliers", {
                    "p_profile_id": str(scope.profile_id),
                }).execute()
            )

            await self._write_profile_snapshot(scope, posts, summary)
            summary.profiles_scraped += 1
        except Exception as exc:
            summary.failures += 1
            _log.error("scrape_failed profile_id=%s handle=%s err=%s",
                       scope.profile_id, scope.handle, exc)
            self._dead_letter(scope, exc)

    def _dead_letter(self, scope: ProfileScope, exc: BaseException) -> None:
        if not self._dead_letter_path:
            return
        import json
        from pathlib import Path
        entry = {
            "profile_id": str(scope.profile_id),
            "creator_id": str(scope.creator_id),
            "handle": scope.handle,
            "platform": scope.platform,
            "error": str(exc),
            "ts": datetime.utcnow().isoformat() + "Z",
        }
        Path(self._dead_letter_path).parent.mkdir(parents=True, exist_ok=True)
        with open(self._dead_letter_path, "a") as f:
            f.write(json.dumps(entry) + "\n")
```

- [ ] **Step 4: Run the tests to verify they pass**

```bash
python -m pytest scripts/tests/content_scraper/test_orchestrator.py -v
```

Expected: 5 passed (3 from Task 8 + 2 new).

- [ ] **Step 5: Commit**

```bash
git add scripts/content_scraper/orchestrator.py scripts/tests/content_scraper/test_orchestrator.py
git commit -m "feat(content_scraper): per-profile error boundary + JSONL dead letter"
```

---

## Task 10: CLI entry point

**Files:**
- Create: `scripts/scrape_content.py`

- [ ] **Step 1: Write the CLI**

Create `scripts/scrape_content.py`:

```python
"""Manual-trigger CLI for the content scraper.

Resolves a target set of (creator, profile) pairs from one of three
mutually exclusive input modes (--creator-id / --tracking-type / --profile-id),
then dispatches the orchestrator.

Spec: docs/superpowers/specs/2026-04-27-content-scraper-v1-design.md §4
"""
from __future__ import annotations
import argparse
import asyncio
import logging
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from dotenv import load_dotenv
from apify_client import ApifyClient

# Make scripts/ importable
sys.path.insert(0, str(Path(__file__).resolve().parent))

from common import get_supabase  # type: ignore
from content_scraper.fetchers.instagram import InstagramContentFetcher
from content_scraper.fetchers.tiktok import TikTokContentFetcher
from content_scraper.orchestrator import ScrapeOrchestrator, ProfileScope


DEAD_LETTER_PATH = str(Path(__file__).parent / "content_scraper_dead_letter.jsonl")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Manual-trigger content scraper (IG + TT)")
    parser.add_argument("--workspace-id", required=True)
    sel = parser.add_mutually_exclusive_group(required=True)
    sel.add_argument("--creator-id", action="append", default=[])
    sel.add_argument("--tracking-type")
    sel.add_argument("--profile-id", action="append", default=[])
    parser.add_argument("--limit-days", type=int, default=30)
    parser.add_argument("--platform", choices=["ig", "tt", "both"], default="both")
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def _resolve_scopes(sb, args: argparse.Namespace) -> list[ProfileScope]:
    """Resolve the (creator_id, profile_id, handle, platform) tuples to scrape."""
    workspace_id = args.workspace_id

    # Determine creator_id list
    if args.profile_id:
        # Direct-profile escape hatch — bypass creator resolution
        rows = (
            sb.table("profiles")
            .select("id,handle,platform,creator_id,is_active,workspace_id")
            .in_("id", args.profile_id)
            .eq("workspace_id", workspace_id)
            .eq("is_active", True)
            .execute()
        ).data or []
    else:
        if args.creator_id:
            creator_ids = args.creator_id
        else:
            cr = (
                sb.table("creators")
                .select("id")
                .eq("workspace_id", workspace_id)
                .eq("tracking_type", args.tracking_type)
                .execute()
            ).data or []
            creator_ids = [c["id"] for c in cr]
            if not creator_ids:
                print(f"[warn] no creators found with tracking_type={args.tracking_type!r}",
                      file=sys.stderr)
                return []

        rows = (
            sb.table("profiles")
            .select("id,handle,platform,creator_id,is_active,workspace_id")
            .in_("creator_id", creator_ids)
            .eq("workspace_id", workspace_id)
            .eq("is_active", True)
            .in_("platform", ["instagram", "tiktok"])
            .execute()
        ).data or []

    # Apply --platform filter
    plat_filter = {"ig": {"instagram"}, "tt": {"tiktok"}, "both": {"instagram", "tiktok"}}[args.platform]
    scopes = []
    for r in rows:
        if r["platform"] not in plat_filter:
            continue
        scopes.append(ProfileScope(
            profile_id=r["id"],
            handle=r["handle"],
            platform=r["platform"],
            creator_id=r["creator_id"],
        ))
    return scopes


async def _run(args: argparse.Namespace) -> int:
    load_dotenv(Path(__file__).parent / ".env")
    apify_token = os.environ.get("APIFY_TOKEN")
    if not apify_token:
        print("[err] APIFY_TOKEN missing in scripts/.env", file=sys.stderr)
        return 2

    sb = get_supabase()
    scopes = _resolve_scopes(sb, args)
    if not scopes:
        print("[info] no profiles in scope; exiting")
        return 0

    print(f"[info] resolved {len(scopes)} profile(s) across {len({s.creator_id for s in scopes})} creator(s)")
    for s in scopes:
        print(f"  - {s.platform:9s} @{s.handle}  profile_id={s.profile_id}  creator_id={s.creator_id}")

    if args.dry_run:
        print("[info] --dry-run: exiting before Apify call")
        return 0

    apify = ApifyClient(apify_token)
    orch = ScrapeOrchestrator(
        supabase=sb,
        ig_fetcher=InstagramContentFetcher(apify_client=apify),
        tt_fetcher=TikTokContentFetcher(apify_client=apify),
        dead_letter_path=DEAD_LETTER_PATH,
    )
    since = datetime.now(timezone.utc) - timedelta(days=args.limit_days)
    summary = await orch.run(scopes, since=since)

    print(f"[done] profiles_scraped={summary.profiles_scraped} "
          f"profiles_skipped={summary.profiles_skipped} "
          f"posts_upserted={summary.posts_upserted} "
          f"outliers_flagged={summary.outliers_flagged} "
          f"failures={summary.failures}")
    return 0 if summary.failures == 0 else 1


def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    args = _parse_args()
    return asyncio.run(_run(args))


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 2: Smoke-test --help and --dry-run argparse**

```bash
python scripts/scrape_content.py --help
```

Expected: usage message shows `--creator-id` / `--tracking-type` / `--profile-id` are mutually exclusive, `--workspace-id` required.

```bash
python scripts/scrape_content.py --workspace-id 00000000-0000-0000-0000-000000000000 --tracking-type managed --dry-run
```

Expected: connects to Supabase, prints "no creators found with tracking_type='managed'" or a list of resolved scopes, then exits before any Apify call.

- [ ] **Step 3: Commit**

```bash
git add scripts/scrape_content.py
git commit -m "feat(content_scraper): CLI entry point — creator/tracking/profile selection + dry-run"
```

---

## Task 11: Live integration smoke

**Files:**
- (no code; verification only)

- [ ] **Step 1: Run --dry-run against managed creators in Simon's workspace**

Get the workspace ID:

```bash
# Use the Supabase MCP to query workspaces:
# mcp__claude_ai_Supabase__execute_sql with: SELECT id, name FROM workspaces;
```

Then:

```bash
python scripts/scrape_content.py \
  --workspace-id <WS_ID> \
  --tracking-type managed \
  --dry-run
```

Expected: prints resolved scopes, exits 0 without calling Apify.

- [ ] **Step 2: Run a real scrape against ONE creator (smallest blast radius)**

Pick one creator (e.g. Esmae or Kira) and run:

```bash
python scripts/scrape_content.py \
  --workspace-id <WS_ID> \
  --creator-id <CREATOR_ID>
```

Expected: ~30-90s wall clock, summary line at the end. Check Apify console for actor cost.

- [ ] **Step 3: Verify scraped_content rows landed**

Use `mcp__claude_ai_Supabase__execute_sql`:

```sql
SELECT
  p.handle, p.platform,
  COUNT(*) AS post_count,
  COUNT(*) FILTER (WHERE sc.is_outlier) AS outlier_count,
  COUNT(*) FILTER (WHERE array_length(sc.hashtags, 1) > 0) AS posts_with_hashtags,
  COUNT(*) FILTER (WHERE sc.platform_metrics->'audio'->>'signature' IS NOT NULL) AS posts_with_audio_sig,
  MIN(sc.posted_at) AS oldest_post,
  MAX(sc.posted_at) AS newest_post
FROM scraped_content sc
JOIN profiles p ON p.id = sc.profile_id
WHERE p.creator_id = '<CREATOR_ID>'
GROUP BY p.handle, p.platform;
```

Expected: rows for IG and TT (if creator has both); reasonable post counts; oldest_post within last 30 days; non-zero hashtag and audio_signature counts.

- [ ] **Step 4: Verify content_metrics_snapshots rows landed**

```sql
SELECT
  COUNT(*) AS snapshot_count,
  MIN(snapshot_date) AS first_snapshot,
  MAX(snapshot_date) AS last_snapshot
FROM content_metrics_snapshots cms
JOIN scraped_content sc ON sc.id = cms.content_id
JOIN profiles p ON p.id = sc.profile_id
WHERE p.creator_id = '<CREATOR_ID>';
```

Expected: snapshot_count equals the post_count from Step 3 (one snapshot per content per day).

- [ ] **Step 5: Verify profile_metrics_snapshots row landed**

```sql
SELECT profile_id, snapshot_date, follower_count, median_views, outlier_count
FROM profile_metrics_snapshots pms
JOIN profiles p ON p.id = pms.profile_id
WHERE p.creator_id = '<CREATOR_ID>'
  AND pms.snapshot_date = CURRENT_DATE;
```

Expected: one row per scraped profile, with sensible values (median_views > 0 if any posts had views).

- [ ] **Step 6: Re-run the same scrape (idempotency check)**

```bash
python scripts/scrape_content.py --workspace-id <WS_ID> --creator-id <CREATOR_ID>
```

Then re-run the Step 3 query. Expected: post_count is the same (no duplicates from the unique constraint on `(platform, platform_post_id)`).

- [ ] **Step 7: Run dead-letter check**

```bash
test -f scripts/content_scraper_dead_letter.jsonl && cat scripts/content_scraper_dead_letter.jsonl || echo "no dead-letter file (good)"
```

Expected: either the file doesn't exist, or it's empty / contains entries you can explain (e.g., a private profile you knew would fail).

---

## Task 12: Cleanup — delete legacy `apify_scraper.py`

**Files:**
- Delete: `scripts/apify_scraper.py`

- [ ] **Step 1: Verify nothing else imports it**

```bash
grep -rn "from apify_scraper\|import apify_scraper" "/Users/simon/OS/Living VAULT/Content OS/The Hub" \
  --include="*.py" \
  --exclude-dir=__pycache__ \
  --exclude-dir=node_modules \
  --exclude-dir=.git
```

Expected: no matches (or only matches inside `apify_scraper.py` itself).

- [ ] **Step 2: Delete the file**

```bash
git rm scripts/apify_scraper.py
```

- [ ] **Step 3: Run the full pytest suite**

```bash
python -m pytest scripts/tests/ -v
```

Expected: all tests pass (~280+ total: 249 prior + ~30 new).

- [ ] **Step 4: Commit**

```bash
git commit -m "chore(content_scraper): delete legacy scripts/apify_scraper.py — superseded by content_scraper package"
```

---

## Task 13: PROJECT_STATE update

**Files:**
- Modify: `PROJECT_STATE.md`

- [ ] **Step 1: Update §4.1 schema for new scraped_content columns**

In `PROJECT_STATE.md`, find the `scraped_content` line in §4.1 (under "Content layer") and update it to include the new columns. Replace:

```
- `scraped_content` — id, profile_id, platform, platform_post_id (unique per platform), post_url, post_type, caption, hook_text, posted_at, view_count, like_count, comment_count, share_count, save_count, engagement_rate (generated), platform_metrics (jsonb), media_urls[], thumbnail_url, is_outlier, outlier_multiplier, raw_apify_payload (jsonb), trend_id (FK→trends nullable), timestamps
```

with:

```
- `scraped_content` — id, profile_id, platform, platform_post_id (unique per platform), post_url, post_type, caption, hook_text, posted_at, view_count, like_count, comment_count, share_count, save_count, engagement_rate (generated), **is_pinned (bool, default false)**, **is_sponsored (bool, default false)**, **video_duration_seconds (numeric nullable)**, **hashtags (text[] default '{}')**, **mentions (text[] default '{}')**, platform_metrics (jsonb — defined-shape per `scripts/content_scraper/normalizer.py::PlatformMetrics`), media_urls[], thumbnail_url, is_outlier, outlier_multiplier, raw_apify_payload (jsonb), trend_id (FK→trends nullable), **quality_flag (`quality_flag` enum, default 'clean', NOT NULL)**, **quality_reason (text nullable)**, timestamps. The 7 new columns added 2026-04-27 (migration `20260427000000_scraped_content_v1_columns`) for content scraper v1 + watchdog anticipation.
```

- [ ] **Step 2: Add quality_flag to §5 enum table**

In §5 ("All Enums"), add a row:

```
| `quality_flag` | clean, suspicious, rejected |
```

- [ ] **Step 3: Add commit_scrape_result to §6 RPC table**

In §6 ("All RPCs"), add a row:

```
| `commit_scrape_result` | (p_profile_id uuid, p_posts jsonb) → jsonb | Transactional content commit (2026-04-27): for each NormalizedPost in p_posts, upserts into `scraped_content` (ON CONFLICT (platform, platform_post_id) DO UPDATE) AND inserts/updates a `content_metrics_snapshots` row for today. Returns `{posts_upserted, snapshots_written}`. Atomic — if any post or snapshot write fails, all rollback. Driven by `scripts/scrape_content.py` (manual trigger v1; cron deferred). |
```

- [ ] **Step 4: Update §14 build order**

Find the line:
```
9. 🔜 **Phase 2 scraping:** IG + TikTok Apify ingestion (scheduled via GitHub Actions every 12h), normalizers, `flag_outliers` live, Outliers page live
```

Replace with:
```
9. 🟡 **Phase 2 scraping (v1 — manual trigger):** ✅ `scripts/scrape_content.py` CLI ships IG + TikTok ingestion (last 30 days per profile) via batched Apify calls, `commit_scrape_result` RPC for transactional `scraped_content` + `content_metrics_snapshots` writes, `flag_outliers` per-profile, `profile_metrics_snapshots` daily row. Spec: `docs/superpowers/specs/2026-04-27-content-scraper-v1-design.md`. Plan: `docs/superpowers/plans/2026-04-27-content-scraper-v1.md`. 🔜 GitHub Actions 12h cron, runtime watchdog stack (§15.2), Outliers page UI deferred.
```

- [ ] **Step 5: Add to §20 Known Limitations**

Append a new row:

```
| **Content scraper dead-letter has no replay tooling** (sync 18, 2026-04-27) | `scripts/content_scraper_dead_letter.jsonl` | Mirror of the same gap on `discovery_dead_letter.jsonl`. Failed per-profile scrapes accumulate as JSONL; no `replay_content_scraper_dead_letter.py` exists yet. | Same shape as the existing `replay_dead_letter.py` for discovery — straightforward when needed. |
```

- [ ] **Step 6: Append to Decisions Log**

Append the following entry to the bottom of `## Decisions Log`:

```
- 2026-04-27 (sync 18): **Content scraper v1 — manual-trigger foundation shipped.** Branch `phase-2-discovery-v2`. New `scripts/content_scraper/` package (orchestrator + per-platform fetchers + closed-shape Pydantic normalizer) + `scripts/scrape_content.py` CLI. Two migrations: `20260427000000_scraped_content_v1_columns` (5 new top-level columns surfaced from Apify payloads — `is_pinned`, `is_sponsored`, `video_duration_seconds`, `hashtags[]`, `mentions[]` — plus `quality_flag` enum + columns anticipating §15.2 watchdog) and `20260427000100_commit_scrape_result` (transactional content + snapshot RPC). Three input modes: `--creator-id` (repeatable), `--tracking-type`, `--profile-id` (escape hatch); `--limit-days 30` default; `--platform ig|tt|both` default both; `--dry-run`. Both Apify calls are batched (one IG actor run + one TT actor run per CLI invocation, regardless of profile count) for cost efficiency. Per-profile commit → `flag_outliers` → `profile_metrics_snapshots` sequence; per-profile dead-letter on failure (`content_scraper_dead_letter.jsonl`). `PlatformMetrics` Pydantic is `extra="forbid"` — closed-shape jsonb with `audio`, `location`, `tagged_accounts`, `product_type`, `effects`, `is_slideshow`, `is_muted`, `video_aspect_ratio`, `video_resolution`, `subtitles` keys. `raw_apify_payload` retained for forensic / future-extraction use. Legacy `scripts/apify_scraper.py` deleted (unintegrated sketch). 30+ new tests. Spec: `docs/superpowers/specs/2026-04-27-content-scraper-v1-design.md`. Plan: `docs/superpowers/plans/2026-04-27-content-scraper-v1.md`. **Mapped but deferred:** GH Actions 12h cron; Apify webhooks (4 events); `lukaskrivka/results-checker` chain; quality-flag validators; LLM-as-judge on suspicious rows; trend/audio extraction (column already exists, fed by `platform_metrics.audio.signature` captured in v1); outliers UI page; tracking-type tagging UI on creator HQ + bulk-upload form.
```

- [ ] **Step 7: Commit**

```bash
git add PROJECT_STATE.md
git commit -m "docs: PROJECT_STATE sync 18 — content scraper v1 manual-trigger"
```

---

## Self-review

After implementing all 13 tasks, verify against the spec:

| Spec section | Implementation task | Status |
|---|---|---|
| §3.1 Selection unit (creator-keyed + escape hatch) | Task 10 (CLI) | covered |
| §3.2 Per-platform batched fetch | Tasks 6 + 7 | covered |
| §3.3 NormalizedPost + PlatformMetrics | Tasks 3, 4, 5 | covered |
| §3.4 commit_scrape_result RPC | Task 2 | covered |
| §3.5 Profile-level snapshot | Task 8 (`_write_profile_snapshot`) | covered |
| §3.6 Schema additions | Tasks 1 + 2 | covered |
| §4 CLI surface | Task 10 | covered |
| §5 Data flow per run | Tasks 8 + 9 (orchestrator) + Task 10 (CLI) | covered |
| §6.1 Transient Apify retry | Tasks 6 + 7 (tenacity wrap) | covered |
| §6.2 Empty dataset handling | Task 8 (skip when no posts) | covered |
| §6.3 Per-row Pydantic failure | Tasks 6 + 7 (try/except per item) | covered |
| §6.4 RPC failure handling | Task 9 | covered |
| §6.5 Dead-letter | Task 9 | covered |
| §7 Concurrency | Task 8 (asyncio.gather between platforms) | covered |
| §8 Testing | Tasks 3-9 (TDD throughout) | covered |
| §9 Anticipated future work | Task 13 (PROJECT_STATE notes) | covered |
| §10 Open follow-ups | Task 13 (PROJECT_STATE §20) | covered |
