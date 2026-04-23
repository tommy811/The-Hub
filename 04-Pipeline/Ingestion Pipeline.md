# Ingestion Pipeline (Phase 2)

> 🟡 Partial. `scripts/apify_scraper.py` exists as of 2026-04-23. Full orchestration planned for Phase 2.

## Overview
After the creator network is discovered (Phase 1), this pipeline scrapes
actual content from Instagram and TikTok for each creator's social accounts.

## Trigger
Manual: "Scrape" button on platform accounts page
Scheduled: cron every 12–24h via `scripts/worker.py`

## Flow
1. Query active `profiles` where `account_type = 'social'` and `platform IN ('instagram','tiktok')`
2. For each: call correct Apify actor
3. Normalize raw response using `normalize_instagram.py` or `normalize_tiktok.py`
4. Upsert into `scraped_content` using `ON CONFLICT (platform, platform_post_id) DO UPDATE`
5. Insert daily row into `content_metrics_snapshots`
6. Call `flag_outliers(profile_id)` to mark top performers
7. Update `profile_metrics_snapshots` with new median_views, avg_engagement_rate

## Scraping Parameters
- **How much content:** Last 90 days OR last 50 posts (whichever is less)
- **Story highlights:** Include if available
- **Re-scraping:** Updates metrics on existing posts (upsert pattern)

## Files
- `scripts/worker.py` — orchestrator (also handles discovery)
- `scripts/normalize_instagram.py` — field mapping
- `scripts/normalize_tiktok.py` — field mapping
- `scripts/common.py` — shared Apify client
