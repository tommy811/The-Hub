# Apify Actor Registry

## Active (V1 — Phase 2)
| Platform | Actor ID | Notes |
|---|---|---|
| Instagram | `apify/instagram-scraper` | Posts, reels, story highlights |
| TikTok | `clockworks/tiktok-scraper` | Videos, profile metadata |

## Planned (Phase 2+)
| Platform | Actor ID | Status |
|---|---|---|
| YouTube | `streamers/youtube-scraper` | TBD — verify before use |
| Facebook | TBD | Research needed |

## Actor Configuration Notes

### Instagram
- Scrape last 30–90 days of content (configure `resultsLimit` or date range)
- Include story highlights if available
- Store `videoUrl` as audio_url reference (not downloadable — original IG link)
- `ownerUsername` used to match back to profiles.handle

### TikTok
- `createTime` is Unix timestamp — must convert in normalizer
- `diggCount` = likes (TikTok terminology)
- `collectCount` = saves
- `downloadAddr` is watermarked — store as reference only

## Adding a New Actor
1. Test actor in Apify console with a sample account
2. Log full raw response JSON
3. Create `scripts/normalize_[platform].py` mapping raw fields → DB columns
4. Add platform to `APIFY_ACTOR_MAP` in `scripts/common.py`
5. Add field mapping table to `03-Database/Apify Field Mappings.md`
6. Extend `platform` enum in Supabase if not already present
