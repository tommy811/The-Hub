# Winning Content Intelligence Follow-Up

**Date:** 2026-04-28
**Status:** Active follow-up to Phase 2 scraping/trends
**Goal:** Make the current content surfaces useful for finding repeatable winning ideas per creator, while clearly marking what needs Phase 3 analysis.

## Now: Stored Metrics We Can Trust

Use these across `/scraped-content`, platform outlier pages, `/trends`, and platform account intel:

- Views, with explicit missing-view coverage for IG static posts where the actor does not expose views.
- Outlier multiplier against profile baseline.
- Engagement rate from the generated DB column.
- Likes, comments, shares, saves where the platform exposes them.
- Repeat-audio usage count and distinct creator count.
- Pinned and sponsored flags.
- Post type, duration, hashtags, mentions, audio metadata, posted date.
- Profile/account reach, median views over non-zero view rows, outlier count.

Current useful sorts:

- Copy priority, recent, views, engagement, outlier lift, trend usage, likes, comments, shares, saves, profile.

Current useful filters:

- Platform, content format, outliers, has audio, repeat audio, no trend, has views, missing views, pinned, sponsored, needs review, minimum outlier lift, free-text search.

## Implemented Immediately

These are Phase 2-safe because they derive from fields already stored in `scraped_content`, `profiles`, and `trends`:

- Distinct creator count for repeat audio.
- Cross-creator audio filtering in `/trends`.
- Known/missing view handling for IG static posts.
- Non-zero median view snapshots for profile account cards.
- Profile/account avatars in creator HQ and platform account cards.
- Read-time profile avatar fallback from recent scraped post payloads.
- Scraper-side profile avatar refresh on successful content scrapes.
- Manual direct profile-avatar refresh via `scripts/refresh_profile_avatars.py` for accounts whose scraped post payloads do not include pfp fields.
- Server-side `/api/avatar` proxy for allowed IG/TT/YT avatar CDN hosts so signed platform images render more reliably in the browser.
- Dedicated IG highlights import via `scripts/scrape_instagram_highlights.py`, storing highlight stories as `scraped_content.post_type='story_highlight'`.
- Format filtering for reels, TikToks, carousels, and images.
- Deterministic copy-priority scoring for content rows.
- Primary navigation trimmed to real working surfaces.

## Copy Priority Rubric

`copyPriorityScore` is a deterministic UI ranking, not a stored model score. It exists to answer "what should we inspect first today?" with current Phase 2 data.

Signals:

- Outlier lift: strongest signal because it normalizes against each creator's own baseline.
- Engagement rate: indicates audience response beyond reach.
- Cross-creator audio: indicates a pattern working for more than one creator.
- Share/save availability: deep engagement where the platform exposes it.
- Known high views: secondary signal, because raw views can be misleading across creator sizes.
- Sponsored penalty: paid posts are less useful as organic inspiration unless manually reviewed.

Do not treat this as Phase 3 content quality. Phase 3 should replace/augment it with analyzed hook, visual, retention, and conversion labels.

## Later: Label-Driven Filters

The schema is ready, but the rows are not populated enough yet for production filtering:

- `content_analysis.category`, `quality_score`, `hook_analysis`, `visual_tags`, `transcription`.
- `content_labels` and `content_label_assignments` for `content_format`, `trend_pattern`, `hook_style`, `visual_style`, `creator_niche`, `other`.
- `creator_label_assignments` for creator-level niches.

Treat these as Phase 3, not a Phase 2 UI task. The right next step is a Gemini/Claude analyzer that writes structured analysis per post, then a taxonomy curation UI that filters by canonical labels.

## Add To Project Pipeline

Phase 3 analyzer:

- Input: `scraped_content` rows with media, caption, metrics, raw payload.
- Output: `content_analysis` plus `content_label_assignments`.
- Labels: hook style, content format, visual style, trend pattern, CTA type, niche, production pattern.
- Scores: hook strength, clarity, replayability, save/share likelihood, creator-fit, brand-fit, conversion-fit.
- Model split: Gemini for frame/video understanding; Claude for hook/narrative synthesis.

Phase 3 taxonomy curation:

- Human review UI for canonical labels.
- Merge near-duplicate labels.
- Filter content library by labels once coverage is high enough.
- Promote proven labels into reusable briefs/templates.

Phase 3/4 metrics enrichment:

- Retention/watch-time source if actor/API makes it available.
- Sends/reach, saves/reach, average watch time, completion rate, replay rate.
- Historical velocity snapshots from repeated scrapes.
- Creator-specific win-rate by format/hook/audio pattern.
- Stable avatar/media caching to Supabase Storage so signed platform CDN URLs do not expire in the UI.
- Optional scheduled profile-avatar refresh for active IG/TikTok accounts, using a small Apify budget and writing through `profiles.avatar_url`.

Do not block current Phase 2 UI on these. They require new analyzer jobs, better source data, and enough row coverage to avoid fake precision.

## Metrics To Add For Emulation Scoring

Research direction: TikTok says recommendations heavily weight user interactions, including likes, shares, comments, watch-full/skip behavior, and time watched. TikTok One defines video completion rate, total play time, average view time, and 2-second views as reporting metrics. Instagram reporting moved toward views as a primary metric, with view rate / first-3-second retention and views-over-time added for Reels; industry coverage of Mosseri's guidance consistently points to watch time, likes per reach, and sends per reach as core reach diagnostics.

Add these when source data or analysis supports them:

- Hook hold: 2s/3s retention, first-frame pattern, first-caption line, visible text hook.
- Watch quality: average watch time, completion rate, replay rate, total watch time.
- Shareability: share rate, sends/reach when available, "send-to-a-friend" content pattern label.
- Save value: save rate, tutorial/reference/list/template label.
- Comment pull: comment rate, question/controversy/prompt pattern.
- Replication fit: same audio used by multiple creators, same hook/format working across creators, creator-specific historical outlier match.
- Production pattern: duration band, edit density, face/headshot presence, subtitle presence, camera style, post type.
- Conversion clues: caption CTA, bio/funnel mention, monetization platform mention, pinned/sponsored status.

## Surface-Specific Product Direction

- Content Library: become the broad triage table for all scraped posts. Best current ranking: outlier lift, views with coverage, engagement, saves/shares, repeat-audio creator count.
- Platform Outliers: become the "what worked above baseline" list. Keep multiplier first; add filters for audio, min lift, known/missing views, pinned/sponsored.
- Audio Trends: rank by posts and distinct creators. Distinct creators matters more than raw posts because it separates one creator repeating a sound from cross-creator adoption.
- Platform Accounts: show profile photos, followers, median non-zero views, outlier count, and content coverage. Later sort by win rate once enough posts are analyzed.
- Creator Profile: show best avatar from any scraped platform account, then use the content tab in Phase 3 for that creator's own winning content patterns.
- Instagram Highlights: store current highlight stories as content assets now; later add a creator-level Highlights tab and CTA extraction/classification.

## Public-Ready UI Rule

Primary navigation should only expose working surfaces. Future routes can stay in the repo, but visible disabled "Soon" items should not be part of the deployable app shell until the feature has a real workflow.
