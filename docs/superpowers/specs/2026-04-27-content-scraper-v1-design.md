# Content Scraper v1 — Manual-Trigger Foundation

**Status:** Design
**Date:** 2026-04-27
**Scope:** Phase 2 build-order item 9 (PROJECT_STATE §14), foundation pass — manual trigger only, no cron, no watchdog stack
**Depends on:** Live schema (§4 — `scraped_content`, `content_metrics_snapshots`, `profile_metrics_snapshots`, `flag_outliers` RPC, `trends`); Discovery v2 fetcher patterns under `scripts/fetchers/`
**Successor scope (deferred, mapped):** GitHub Actions 12h cron; runtime watchdog stack (§15.2); trend/audio extraction; outliers UI; tracking-type tagging UI on creator page

---

## 1. Goal

Given a creator (or a set of creators selected by tracking_type), pull the last 30 days of content from each of that creator's Instagram and TikTok profiles, normalize the rows into `scraped_content`, snapshot daily-grain metrics into `content_metrics_snapshots` and `profile_metrics_snapshots`, and run `flag_outliers` per-profile so the data is ready for the future Outliers page.

The trigger surface is a CLI script invoked by Claude during dev — no cron, no UI button, no webhooks. The schema, however, must anticipate the deferred work (cron, watchdog quality flags, trends, audio signature extraction) so we don't owe a migration the day cron lands.

## 2. Non-goals

v1 does **not** cover:

- GitHub Actions / launchd / cron scheduling. Manual CLI trigger only.
- Apify webhook intake (`SUCCEEDED`, `FAILED`, `TIMED_OUT`, `SUCCEEDED_WITH_EMPTY_DATASET`).
- `lukaskrivka/results-checker` post-actor validation chain.
- Quality-flag validators / LLM-as-judge on suspicious rows. The column is added but every row writes `'clean'`.
- Trend / audio signature extraction. `scraped_content.trend_id` stays NULL; `trends` table is unwritten.
- Hook-text deep extraction. v1 uses `caption[:50]` as a placeholder; real hook analysis is Phase 3.
- Outliers UI wiring (`/platforms/instagram/outliers`, `/platforms/tiktok/outliers`).
- Tracking-type tagging UI on the creator page or bulk-upload form. The data already lives on `creators.tracking_type` + `profiles.tracking_type` via the existing bulk-paste flow; v1 just reads it.
- Platforms beyond IG and TikTok. FB / X / YT come post-v1 once the per-platform fetcher contract is proven.
- Server actions / API routes that trigger scrapes from the Next.js UI. The CLI is the only entry point.

## 3. Architecture

```
scripts/
  scrape_content.py                    # CLI entry point
  content_scraper/
    __init__.py
    orchestrator.py                    # creator → profile fanout, commit, outlier flag, snapshot
    normalizer.py                      # NormalizedPost Pydantic + per-platform extractors
    fetchers/
      __init__.py
      base.py                          # BaseContentFetcher contract; reuses is_transient_apify_error
      instagram.py                     # apify/instagram-scraper, batched directUrls
      tiktok.py                        # clockworks/tiktok-scraper, batched profiles[]
    tests/
      __init__.py
      test_normalizer.py
      test_fetcher_instagram.py
      test_fetcher_tiktok.py
      test_orchestrator.py
      test_commit_scrape_result.py
      fixtures/
        instagram_post.json            # representative IG post payload
        tiktok_post.json               # representative TT post payload
```

The package mirrors discovery v2's structure (`scripts/pipeline/` + `scripts/fetchers/` + `scripts/harvester/`) so the codebase stays internally consistent.

`scripts/apify_scraper.py` is **deleted** as part of v1 — it's an unintegrated sketch and the new code supersedes it.

### 3.1 Selection unit (creator-keyed)

The orchestrator's primary input is a list of creator IDs. From each creator, it enumerates `profiles WHERE creator_id = ? AND is_active = true AND platform IN ('instagram', 'tiktok')`. A `--profile-id` escape hatch is provided for fast single-account testing during build, but the canonical mental model is "scrape this creator (across all their IG + TT profiles)."

Selection comes from one of three input modes (mutually exclusive):

1. `--creator-id <uuid>` (repeatable) — explicit creator IDs
2. `--tracking-type <type>` — resolves to all creators with `creators.tracking_type = ?` in the workspace
3. `--profile-id <uuid>` (repeatable) — escape hatch for individual profile testing

### 3.2 Per-platform batched fetch

Both Apify actors accept a list of targets per run (`directUrls` for IG, `profiles` for TT). The orchestrator groups all selected profiles by platform and issues **one Apify call per platform per CLI invocation**, regardless of how many creators are in scope. This keeps cost-per-run sub-linear in profile count and makes the dead-letter granularity per-profile (after the platform-level fetch) rather than per-creator.

### 3.3 Normalized post contract

```python
class NormalizedPost(BaseModel):
    profile_id: UUID
    platform: Literal["instagram", "tiktok"]
    platform_post_id: str
    post_url: str
    post_type: Literal["reel", "tiktok_video", "image", "carousel", "story", "story_highlight", "youtube_short", "youtube_long", "other"]
    caption: str | None
    hook_text: str | None         # v1: caption[:50]; Phase 3 replaces with real extraction
    posted_at: datetime
    view_count: int
    like_count: int
    comment_count: int
    share_count: int | None
    save_count: int | None
    media_urls: list[str]
    thumbnail_url: str | None
    platform_metrics: dict        # platform-specific extras (audio sig, video duration, etc.)
    raw_apify_payload: dict
```

`engagement_rate` is generated server-side; not in the model.
`is_outlier` and `outlier_multiplier` are written by `flag_outliers`, not the normalizer.
`trend_id` stays NULL until trends/audio extraction ships.

### 3.4 RPC: `commit_scrape_result`

```sql
CREATE OR REPLACE FUNCTION commit_scrape_result(
  p_profile_id uuid,
  p_posts jsonb              -- array of NormalizedPost-shaped objects
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
  -- workspace check
  SELECT workspace_id INTO v_workspace_id
  FROM profiles WHERE id = p_profile_id;
  IF v_workspace_id IS NULL THEN
    RAISE EXCEPTION 'profile not found: %', p_profile_id;
  END IF;

  -- upsert each post
  FOR v_post IN SELECT * FROM jsonb_array_elements(p_posts) LOOP
    INSERT INTO scraped_content (
      profile_id, platform, platform_post_id, post_url, post_type,
      caption, hook_text, posted_at,
      view_count, like_count, comment_count, share_count, save_count,
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
      caption = EXCLUDED.caption,
      raw_apify_payload = EXCLUDED.raw_apify_payload,
      updated_at = NOW()
    RETURNING id INTO v_content_id;

    v_posts_upserted := v_posts_upserted + 1;

    -- daily metrics snapshot — same-day re-runs overwrite the day's row
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

The RPC is the **only** way to write to `scraped_content` from the scraper path. Direct `.upsert()` calls from Python are forbidden — the transactional commit (post + snapshot together) is the consistency guarantee.

### 3.5 Profile-level snapshot

After `commit_scrape_result` and `flag_outliers` succeed for a profile, the orchestrator writes one `profile_metrics_snapshots` row for `(profile_id, CURRENT_DATE)` upsert:

- `follower_count` — read from `profiles.follower_count` (set by Discovery, not by content scrape)
- `median_views` — `MEDIAN(view_count)` over the just-scraped posts
- `outlier_count` — `COUNT(*) WHERE is_outlier = true` over the just-scraped posts (post-`flag_outliers`)
- `avg_engagement_rate` — `AVG(engagement_rate)` over the just-scraped posts
- `quality_score` — left NULL in v1 (depends on `content_analysis`, which is Phase 3)

### 3.6 Schema additions

**Migration 1** — `20260427000000_quality_flag_enum.sql`:

```sql
CREATE TYPE quality_flag AS ENUM ('clean', 'suspicious', 'rejected');

ALTER TABLE scraped_content
  ADD COLUMN quality_flag quality_flag NOT NULL DEFAULT 'clean',
  ADD COLUMN quality_reason text;

CREATE INDEX scraped_content_quality_flag_idx
  ON scraped_content (profile_id, quality_flag)
  WHERE quality_flag <> 'clean';
```

The partial index makes "show me suspicious / rejected rows for this workspace" cheap once the watchdog populates them (query joins `scraped_content → profiles` to filter by `workspace_id`, since `scraped_content` itself has no `workspace_id` column — tenant scope is via `profile_id`). Cost on the `clean` write path is zero.

**Migration 2** — `20260427000100_commit_scrape_result.sql`: the RPC body above.

No `scraped_content` columns are added beyond `quality_flag` + `quality_reason`. Trends/audio columns already exist (`trend_id` FK, `platform_metrics` jsonb is sufficient for audio signature payloads later).

## 4. CLI surface

```bash
# Scrape all managed creators in a workspace (dry-run first)
python scripts/scrape_content.py \
  --workspace-id <uuid> \
  --tracking-type managed \
  --dry-run

# Real run, all managed creators, both platforms, last 30 days (defaults)
python scripts/scrape_content.py \
  --workspace-id <uuid> \
  --tracking-type managed

# Single creator across both platforms
python scripts/scrape_content.py \
  --workspace-id <uuid> \
  --creator-id <uuid>

# Single profile escape hatch (fast iteration)
python scripts/scrape_content.py \
  --workspace-id <uuid> \
  --profile-id <uuid> \
  --limit-days 7

# Platform-restricted run
python scripts/scrape_content.py \
  --workspace-id <uuid> \
  --tracking-type managed \
  --platform tt
```

Required: `--workspace-id` and exactly one of `--creator-id` (repeatable) | `--tracking-type` | `--profile-id` (repeatable).
Optional: `--limit-days` (default 30), `--platform ig|tt|both` (default both), `--dry-run`.

`--dry-run` resolves the target set, prints `(creator, profile, platform)` tuples and an estimated Apify cost, and exits without calling Apify.

## 5. Data flow per run

```
CLI parse args
  → resolve workspace + selection mode → list of creator_ids
  → enumerate active IG + TT profiles for those creators
  → group profile_ids by platform
  → IG fetcher: 1 Apify call covering all IG profile URLs in scope, since=NOW-30d
       → returns Dict[profile_id, List[NormalizedPost]]
  → TT fetcher: 1 Apify call covering all TT profile handles in scope, since=NOW-30d
       → returns Dict[profile_id, List[NormalizedPost]]
  → for each profile_id with posts:
       commit_scrape_result(profile_id, posts)        [transactional]
       flag_outliers(profile_id)
       upsert profile_metrics_snapshots row for today
       on any error: dead-letter, continue
  → summary log: profiles processed, posts upserted, outliers flagged, Apify cost cents, dead-letter count
```

## 6. Error handling

### 6.1 Transient Apify errors

The fetchers reuse `is_transient_apify_error()` from `scripts/fetchers/base.py` (already in the codebase from Discovery v2 sync 13 — matches "user was not found" / "authentication token" / "rate limit" / "challenge" / "session expired" / "captcha" / "too many requests" / "429"). Tenacity wraps the Apify `_call_actor` with 3× exponential backoff (3-15s). `EmptyDatasetError` is non-retryable by design — same pattern as Discovery.

### 6.2 Empty dataset (login wall, captcha, private account)

The fetcher returns `{}` for that profile_id (no entry in the result dict). The orchestrator skips the profile with a warning, writes no `scraped_content` rows, does not call `flag_outliers`, does not write a `profile_metrics_snapshots` row. The dead-letter line records `{profile_id, platform, reason: "empty_dataset"}`.

### 6.3 Per-row Pydantic validation failure

Inside the per-platform extractor, each Apify item is wrapped in a `try/except ValidationError`. On failure, log the offending raw payload + the validation error and skip that one post. The rest of the profile's posts proceed.

### 6.4 RPC failure

Caught at the orchestrator level. Dead-letter line records `{creator_id, profile_id, platform, error: "rpc:<msg>"}`. The orchestrator continues to the next profile. Failed profiles do not get `flag_outliers` or `profile_metrics_snapshots` writes — they're already inconsistent.

### 6.5 Dead-letter

Path: `scripts/content_scraper_dead_letter.jsonl`. Append-only JSONL. Same pattern as `scripts/discovery_dead_letter.jsonl`. A `scripts/replay_content_scraper_dead_letter.py` replay script is **out of scope for v1** — listed as a known limitation if dead-letter accumulation becomes a problem.

## 7. Concurrency

The orchestrator uses `asyncio.gather` across **profiles within a platform's results**, with a small concurrency limit (`asyncio.Semaphore(4)` — same value Discovery's worker uses). The two Apify calls (IG batch + TT batch) are also `asyncio.gather`-ed. Total wall-clock for a 5-creator scrape with both platforms ≈ time-of-slowest-Apify-actor (typically 30-90s for the IG actor at 30-day depth) plus ~2-5s of DB roundtrips.

## 8. Testing

| Test file | Coverage |
|---|---|
| `test_normalizer.py` | IG fixture → NormalizedPost; TT fixture → NormalizedPost; missing optional fields default correctly; invalid `post_type` raises ValidationError; `caption=None` produces `hook_text=""` |
| `test_fetcher_instagram.py` | Mock Apify; assert directUrls batching; assert `onlyPostsNewerThan` since-filter passed; assert dispatch returns `Dict[profile_id, List[NormalizedPost]]`; transient-error retry fires; EmptyDatasetError surfaces |
| `test_fetcher_tiktok.py` | Same shape for `clockworks/tiktok-scraper` with `profiles[]` input |
| `test_orchestrator.py` | Mock fetchers + RPC + flag_outliers; assert per-profile commit → outlier → snapshot order; assert dead-letter on RPC failure; assert continue-on-error; assert empty-dataset profiles get no commit + no flag_outliers |
| `test_commit_scrape_result.py` | RPC integration (real Supabase test workspace): idempotent on `(platform, platform_post_id)` re-run; same-day re-run overwrites `content_metrics_snapshots` row not duplicate; quality_flag defaults to 'clean'; transactional rollback when one post in the batch has bad enum |

Test infrastructure reuses the discovery v2 patterns under `scripts/tests/`. New fixture files go under `scripts/content_scraper/tests/fixtures/`.

Target: 30+ new tests. Total pytest count goes from 249 → ~280.

## 9. Anticipated future work (mapped, not built)

The schema and code are designed so the deferred items below land as additive changes:

| Future work | Hook in v1 |
|---|---|
| GH Actions 12h cron | CLI script can be invoked unchanged from a workflow file. No code change needed. |
| Apify webhooks (4 events) | Webhook handler is a separate Next.js API route. Will inspect `dataset_id`, fetch into `scraped_content` via `commit_scrape_result`. The RPC contract doesn't change. |
| `lukaskrivka/results-checker` chain | Runs after the Apify scrape actor; emits its own webhook. Reads/writes `quality_flag` (already in schema). |
| Quality flag validators | `quality_flag` column exists; validators just flip rows from `'clean'` to `'suspicious'` / `'rejected'`. No new column, no migration. |
| LLM-as-judge | Reads `WHERE quality_flag = 'suspicious'`; writes `quality_reason` (already in schema). |
| Trend / audio extraction | `scraped_content.trend_id` already exists (FK to `trends`). The extractor reads `platform_metrics->>'audio_signature'` (TT actor already returns this; IG carries it as `musicInfo` in the payload). Populates `trends` + sets `trend_id`. |
| Outliers UI page | Reads `WHERE is_outlier = true` from `scraped_content` joined to `profiles` and `creators`. Uses the existing tracking_type filter pattern from `/platforms/instagram/accounts`. |
| Tracking-type tagging UI | Field already on `creators` + `profiles` from bulk paste. UI gets an inline editor + a column on the bulk-upload form. The scraper's tracking_type filter doesn't change. |

## 10. Open follow-ups (out of v1, recorded for traceability)

- Replay tooling for `content_scraper_dead_letter.jsonl` (mirror of the same gap on `discovery_dead_letter.jsonl` — known limitation per PROJECT_STATE §20).
- Apify cost estimation in `--dry-run`. v1 prints `(N profiles × ~$X per profile)` rough estimate; precise per-actor cost calibration is post-v1.
- Per-creator scrape-status surface in the UI. v1 only has CLI logs; eventual surface is a "Last scraped" timestamp on the creator card + a per-profile state on the AccountRow.
- Backfill path for creators with a `last_scraped_at` older than 30 days. v1 always pulls "last 30 days from now"; deeper backfills are a separate one-shot script.

---

## Appendix A — Why creator-keyed selection over profile-keyed

A creator may legitimately own multiple IG accounts (main + spicy + business) or have IG + TT + future-FB. The agency mental model is "scrape Esmae" — the creator entity, not "scrape the IG account named esmae123 and the TT account named esmae and the FB page named EsmaeOfficial separately." The orchestrator collapses one creator's profiles into one logical scrape unit even though Apify still issues one platform call per platform.

Profile-keyed selection (`--profile-id`) is preserved for the testing-during-build case ("just rescrape Kira's TT real quick"), explicitly framed as an escape hatch.

## Appendix B — Why a new RPC, not direct upserts

`scraped_content` upsert + `content_metrics_snapshots` write are two operations. Without a transaction, a partial failure mid-loop yields `scraped_content` rows without their daily snapshot — silently inconsistent state that future trend math reads as "no metrics that day." Discovery v2 made the same call (`commit_discovery_result`) for the same reason. Diverging here breaks the codebase's consistency story for net-zero benefit.

## Appendix C — Why one Apify call per platform per run, not one per profile

Both Apify actors accept arrays of targets. Cost is ~linear in dataset size, but per-run *overhead* (actor startup, container provisioning, finalization webhook) is fixed-per-run. Batching all IG profiles into one IG actor run trades a tiny bit of error-isolation granularity (we already get per-profile granularity in the response shape) for a meaningful reduction in Apify cost and wall-clock for multi-creator runs. The dead-letter is per-profile post-fetch, so error handling doesn't degrade.
