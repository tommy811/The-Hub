# Scraping Follow-Up Without Cron

**Goal:** Finish the Phase 2 scraping surfaces that are useful without scheduled 12-hour automation: harden the manual scraper, make scrape health observable, expose live content/outliers in the UI, and add deterministic quality/trend tooling that can be run manually or by a later scheduler.

**Out of scope:** GitHub Actions / 12-hour auto scrape. That stays deferred. No autonomous Apify console configuration. No paid live scrape unless explicitly invoked.

## Tasks

1. Harden manual scraper runtime.
   - Fetch all Apify dataset items via pagination/iteration.
   - Isolate IG and TikTok fetch failures so one actor failure does not discard the other platform's data.
   - Write structured dead-letter rows for fetch failures and no-post skips.

2. Add scrape observability.
   - Add a `scrape_runs` migration with one row per profile scrape attempt.
   - Track status, reason, post count, Apify run id/dataset id when available, started/completed timestamps.
   - Update `profiles.last_scraped_at` on successful profile commits.

3. Wire live content and outliers UI.
   - Add query helpers for content rows and platform outliers.
   - Replace `/content` placeholder with a live content table.
   - Replace Instagram/TikTok outlier placeholders with live outlier pages.

4. Add deterministic quality/trend tooling.
   - Add a manual validator that marks suspicious/rejected rows via existing `quality_flag` / `quality_reason`.
   - Add a manual trend/audio extraction script that reads `platform_metrics.audio.signature`, upserts `trends`, and links `scraped_content.trend_id`.

5. Update project documentation and verification.
   - Update `PROJECT_STATE.md` and migration log.
   - Run focused pytest, full Python suite, TypeScript typecheck, and route smoke where relevant.

## Verification

- `cd scripts && python3 -m pytest tests/content_scraper -q`
- `cd scripts && python3 -m pytest tests -q`
- `npm run typecheck`
- Browser/route smoke for `/content`, `/platforms/instagram/outliers`, `/platforms/tiktok/outliers` if UI changes land.
