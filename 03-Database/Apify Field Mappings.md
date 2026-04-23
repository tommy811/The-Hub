# Apify Field Mappings

## The Rule
- Every raw Apify field maps to an exact DB column in `scraped_content`
- Fields NOT listed below go into `platform_metrics` JSONB under their original key name
- `raw_apify_payload` ALWAYS stores the complete unmodified response
- Implemented in: `scripts/normalize_instagram.py` and `scripts/normalize_tiktok.py`

---

## Instagram
**Actor:** `apify/instagram-scraper`

| Raw Apify Field | DB Column | Notes |
|---|---|---|
| `shortCode` | `platform_post_id` | Unique post identifier |
| `url` | `post_url` | Full post URL |
| `type` | `post_type` | GraphImage→image, GraphVideo→reel, GraphSidecar→carousel |
| `caption` | `caption` | Full caption text |
| `timestamp` | `posted_at` | ISO 8601 → timestamptz |
| `videoViewCount` | `view_count` | Null for image posts |
| `likesCount` | `like_count` | |
| `commentsCount` | `comment_count` | |
| `videoUrl` | `media_urls[0]` | Original IG video link (not downloadable) |
| `displayUrl` | `thumbnail_url` | Cover image URL |
| `musicInfo` | `platform_metrics.music` | Full object stored |
| `hashtags` | `platform_metrics.hashtags` | Array |
| `mentions` | `platform_metrics.mentions` | Array |
| `isSponsored` | `platform_metrics.is_sponsored` | Boolean |
| `locationName` | `platform_metrics.location` | String |
| `coauthorProducers` | `platform_metrics.coauthors` | Array |
| `ownerUsername` | *(match only)* | Used to confirm against profiles.handle |
| *(full response)* | `raw_apify_payload` | Always store complete object |

**post_type mapping:**
```python
POST_TYPE_MAP = {
    "GraphImage": "image",
    "GraphVideo": "reel",
    "GraphSidecar": "carousel"
}
```

**hook_text extraction:**
```python
hook_text = caption.split(". ")[0] if caption else None
# or split on first newline: caption.split("\n")[0]
```

---

## TikTok
**Actor:** `clockworks/tiktok-scraper`

| Raw Apify Field | DB Column | Notes |
|---|---|---|
| `id` | `platform_post_id` | |
| `webVideoUrl` | `post_url` | |
| `text` | `caption` | |
| `createTime` | `posted_at` | Unix timestamp → `datetime.fromtimestamp(val, tz=UTC).isoformat()` |
| `playCount` | `view_count` | |
| `diggCount` | `like_count` | TikTok term for likes |
| `commentCount` | `comment_count` | |
| `shareCount` | `share_count` | |
| `collectCount` | `save_count` | TikTok "collect" = save |
| `videoMeta.coverUrl` | `thumbnail_url` | |
| `videoMeta.downloadAddr` | `media_urls[0]` | Watermarked video URL |
| `videoMeta.duration` | `platform_metrics.duration_seconds` | Integer seconds |
| `musicMeta` | `platform_metrics.music` | Full object |
| `hashtags` | `platform_metrics.hashtags` | Array of {name, title} |
| `isAd` | `platform_metrics.is_ad` | Boolean |
| `authorMeta.fans` | *(update profile)* | Update profiles.follower_count |
| `authorMeta.name` | *(confirm only)* | Confirm against profiles.handle |
| *(full response)* | `raw_apify_payload` | Always store complete object |

**post_type:** always `tiktok_video`

**createTime conversion:**
```python
from datetime import datetime, timezone
posted_at = datetime.fromtimestamp(raw["createTime"], tz=timezone.utc).isoformat()
```
