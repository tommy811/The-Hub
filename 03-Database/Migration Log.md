# Migration Log

## 2026-04-26 — new_platform_watchdog view with Gemini LLM suggestions (T20)
**File:** `supabase/migrations/20260426080000_watchdog_view_with_llm_suggestions.sql`
**Applied:** ✅ Supabase (Content OS) via MCP
**Branch / PR:** `phase-2-discovery-v2`

### What Changed
`CREATE OR REPLACE VIEW new_platform_watchdog AS ...` — REPLACES the T19 v1 view. Joins to `classifier_llm_guesses` via CTEs (`grouped` + `guess_per_host` via `DISTINCT ON (host)`). Surfaces Gemini's enriched suggestion per host: `suggested_label`, `suggested_slug`, `description`, `icon_category`. View now has 11 columns total.

**Operator workflow:** `SELECT * FROM new_platform_watchdog ORDER BY creator_count DESC LIMIT 50;` returns each novel host once with Gemini's recommendation pre-populated. VA ratifies in one click; the standard 3-step add (gazetteer rule + PLATFORMS dict entry + HOST_PLATFORM_MAP entry) follows.

**Caveat:** original spec used 4 correlated subqueries; Postgres rejected with `42803` (ungrouped column). Refactored to CTE-based LEFT JOIN with identical semantics.

---

## 2026-04-26 — classifier_llm_guesses enriched metadata (T20)
**File:** `supabase/migrations/20260426070000_classifier_llm_guesses_enriched_metadata.sql`
**Applied:** ✅ Supabase (Content OS) via MCP
**Branch / PR:** `phase-2-discovery-v2`

### What Changed
Adds 4 nullable TEXT columns to `classifier_llm_guesses`: `suggested_label`, `suggested_slug`, `description`, `icon_category`. Backs the Gemini-enriched watchdog (T20 / sync 17).

The companion Python change rewrites the LLM prompt to return all 4 enriched fields alongside the existing platform/account_type/confidence; `_classify_via_llm` returns a 5-tuple `(platform, account_type, confidence, model_version, enriched_metadata)`; `_cache_insert` accepts an optional `enriched: dict` parameter and writes the 4 columns. Empty-string responses persist as NULL. Idempotent (`ADD COLUMN IF NOT EXISTS`).

---

## 2026-04-26 — new_platform_watchdog SQL view v1 (T19)
**File:** `supabase/migrations/20260426060000_new_platform_watchdog_view.sql`
**Applied:** ✅ Supabase (Content OS) via MCP
**Branch / PR:** `phase-2-discovery-v2`

### What Changed
`CREATE OR REPLACE VIEW new_platform_watchdog AS ...` — surfaces every `is_active=true` profile row with `platform='other'` grouped by URL host. Joined to creator names + last_seen + sample_url. VA-friendly triage query: `SELECT * FROM new_platform_watchdog ORDER BY creator_count DESC LIMIT 50;`. Each row is a candidate for adding (a) a gazetteer rule, (b) a PLATFORMS dict entry, (c) a HOST_PLATFORM_MAP entry — ~5 minutes per platform.

Superseded the same day by `20260426080000` which adds Gemini-suggestion columns via CTE join. v1 returns the aggregate columns only.

Returns 0 rows currently — gazetteer + T17 backfill comprehensive for the 5-creator dataset.

**Note:** T18 (handle normalization + visit.link.me OF redirector detection) had no schema migration — application code + data UPDATEs only. The 5 duplicate profile rows were soft-deleted via direct UPDATE; 7 active rows were normalized via direct UPDATE; 5 soft-deleted rows were tombstoned with a `__deleted_<uuid>` suffix to free unique-key slots before normalizing surviving rows. One-time migration artifact — application-layer ON CONFLICT updates re-activate the same row going forward.

---

## 2026-04-26 — Creator cover_image_url + banner_url + override_avatar_url
**File:** `supabase/migrations/20260426050000_creator_cover_and_banner.sql`
**Applied:** ✅ Supabase (Content OS) via MCP
**Branch / PR:** `phase-2-discovery-v2`

### What Changed
Adds 3 nullable text columns to `creators` to back the new banner / cover / override-avatar UI surface (T17 in sync 16):

- `cover_image_url TEXT` — scraper-set; null pending Phase 3 scraper work (IG / FB / Twitter / Reddit cover photos).
- `banner_url TEXT` — agency-managed override; operators can set it directly to override whatever the scraper would otherwise pick.
- `override_avatar_url TEXT` — agency-managed headshot. When set, both creator HQ and the grid card prefer it over the scraper-fetched `profiles.avatar_url` (solves the IG-CDN avatar expiry problem for any creator the agency wants pinned to a stable image).

UI: new `<BannerWithFallback>` client component renders on creator HQ below the merge-candidate banner / above the header. Uses `banner_url` if set, else `cover_image_url`, else gradient placeholder. Idempotent (`ADD COLUMN IF NOT EXISTS`). No backfill — all 3 columns default null.

---

## 2026-04-26 — Extend platform enum with 19 specific-aggregator + monetization values
**File:** `supabase/migrations/20260426040000_add_platform_values_specific_aggregators_and_monetization.sql`
**Applied:** ✅ Supabase (Content OS) via MCP
**Branch / PR:** `phase-2-discovery-v2`

### What Changed
Extends the Postgres `platform` enum with 19 new values (T17 in sync 16):

`link_me`, `tapforallmylinks`, `allmylinks`, `lnk_bio`, `snipfeed`, `launchyoursocials`, `fanfix`, `cashapp`, `venmo`, `snapchat`, `reddit`, `spotify`, `threads`, `bluesky`, `kofi`, `buymeacoffee`, `substack`, `discord`, `whatsapp`.

Total enum count post-migration: ~37 values.

**Why this matters:** the previous `custom_domain` / `other` buckets were causing `(creator_id, platform, profile_url)` unique-constraint collisions when distinct destinations resolved to the same generic platform. With distinct enum values, rows coexist cleanly (e.g. Valentina's `link.me`, `cash.app`, `venmo.com`, and `app.fanfix.io` all become separate, non-colliding rows).

**Companion changes (alongside but not part of this SQL migration):**
- Pydantic `Platform = Literal[...]` in `scripts/schemas.py` extended to match (caught in-flight at pre-commit when the first discovery run failed with `pydantic.ValidationError` and fixed before push).
- Gazetteer (`data/monetization_overlay.yaml`) rewritten with 13 new specific host→platform rules; 6 older generic ones removed so new specifics win.
- `src/lib/platforms.ts` PLATFORMS dict gained 13+ entries with Si* icons (react-icons 5.6.0) + lucide fallbacks (Cash App / Venmo / Fanfix).
- 11 existing profile rows backfilled via direct UPDATE from `other` / `custom_domain` to specific platforms (tapforallmylinks=3, link_me=1, fanfix=1, cashapp=1, venmo=1, snapchat=2, reddit=1, spotify=1).

---

## 2026-04-26 — commit_discovery_result v4 (ON CONFLICT updates destination_class)
**File:** `supabase/migrations/20260426030000_commit_discovery_result_v4_update_destination_class.sql`
**Applied:** ✅ Supabase (Content OS) via MCP
**Branch / PR:** `phase-2-discovery-v2`

### What Changed
Body identical to v3 except the `ON CONFLICT (profile_id, canonical_url) DO UPDATE` clause on `profile_destination_links` now also updates `destination_class = EXCLUDED.destination_class`. Pre-fix rows from buggy earlier runs stuck around with stale class values — e.g. `t.me/...` URLs sat at `other` even after the resolver was patched to emit `messaging`. Caught during the 2026-04-26 smoke when re-running discovery didn't refresh cached destination rows.

---

## 2026-04-26 — Extend destination_class CHECK constraint to 10 values
**File:** `supabase/migrations/20260426020000_extend_destination_class_check.sql`
**Applied:** ✅ Supabase (Content OS) via MCP
**Branch / PR:** `phase-2-discovery-v2`

### What Changed
Extends `profile_destination_links.destination_class` CHECK constraint from 4 → 10 values: `monetization | aggregator | social | commerce | messaging | content | affiliate | professional | other | unknown`. Matches the `DestinationClass` Literal in `scripts/harvester/types.py`. Without this, rows tagged `messaging` (Telegram / WhatsApp / Discord) crashed on insert during the 2026-04-26 smoke. TEXT-with-CHECK pattern (not Postgres ENUM) keeps forward-compat additions to a single `DROP CONSTRAINT / ADD CONSTRAINT` swap.

---

## 2026-04-26 — commit_discovery_result v3 (harvester audit fields)
**File:** `supabase/migrations/20260426010000_commit_discovery_result_v3_harvester_audit.sql`
**Applied:** ✅ Supabase (Content OS) via MCP
**Branch / PR:** `phase-2-discovery-v2`

### What Changed
Threads the new audit columns through `commit_discovery_result`. `p_discovered_urls` jsonb gains optional `harvest_method` (`cache|httpx|headless`) and `raw_text` (anchor / button text) per element. RPC reads them and writes to `profile_destination_links` on insert; ON CONFLICT clause uses `COALESCE(EXCLUDED.x, profile_destination_links.x)` so older rows without audit fields don't get nulled out. Body otherwise identical to `20260425000200`.

---

## 2026-04-26 — Universal URL Harvester v1 schema
**File:** `supabase/migrations/20260426000000_url_harvester_v1.sql`
**Applied:** ✅ Supabase (Content OS) via MCP
**Branch / PR:** `phase-2-discovery-v2`

### What Changed
Backs the Universal URL Harvester ship.

**Audit columns on `profile_destination_links`:**
- `harvest_method TEXT` — `cache | httpx | headless`. NULL on rows pre-dating the harvester.
- `raw_text TEXT` — anchor / button text that surfaced the URL during harvest.
- `harvested_at TIMESTAMPTZ DEFAULT NOW()` — when this destination was last (re)harvested.

**New table `url_harvest_cache` (23 → 24 tables):**
- `canonical_url TEXT PRIMARY KEY`
- `harvest_method TEXT NOT NULL CHECK IN ('httpx','headless')`
- `destinations JSONB NOT NULL` — array of `{canonical_url, raw_url, raw_text, destination_class}`
- `harvested_at TIMESTAMPTZ NOT NULL DEFAULT NOW()` + `expires_at TIMESTAMPTZ NOT NULL` (24h TTL set by Python writer)
- Index `idx_url_harvest_cache_expires` on `expires_at` for TTL filtering
- No RLS — workspace-agnostic, service role only (mirrors `classifier_llm_guesses`)

---

## 2026-04-25 — bulk_import_creator missing ::platform cast on discovery_runs INSERT
**File:** `supabase/migrations/20260425030000_bulk_import_platform_cast.sql`
**Applied:** ✅ Supabase (Content OS) via MCP
**Branch / PR:** `phase-2-discovery-v2` → PR #4

### What Changed
Same root cause as `20260425000300` (the retry RPC fix earlier the same day). `bulk_import_creator` declared `p_platform_hint TEXT` and cast it correctly in the `creators` and `profiles` INSERTs, but passed the raw text into the third INSERT into `discovery_runs`. Postgres errored with `22P02 column "input_platform_hint" is of type platform but expression is of type text`. Visible symptom: every Bulk Paste / Single Handle import via the UI failed with this error in the toast. Fix: explicit `::platform` cast at the discovery_runs INSERT site. Behavior identical otherwise.

---

## 2026-04-25 — retry_creator_discovery now updates last_discovery_run_id
**File:** `supabase/migrations/20260425020000_retry_updates_last_run_id.sql`
**Applied:** ✅ Supabase (Content OS) via MCP
**Branch / PR:** `phase-2-discovery-v2` → PR #4

### What Changed
`retry_creator_discovery` created the new run + flipped `creators.onboarding_status='processing'` but never updated `creators.last_discovery_run_id`. The new `<DiscoveryProgress>` UI polls the run pointed to by `last_discovery_run_id`, so after every retry it was polling the *previous* failed run, immediately saw its terminal status, and the new run's spinner stuck at "Queued 0%" forever — worker actually ran the new attempt within seconds, the UI just never observed it. Fix: add `last_discovery_run_id = v_run_id` to the `UPDATE creators` clause. `bulk_import_creator` already wires this correctly (verified via `pg_get_functiondef`).

---

## 2026-04-25 — discovery_runs progress columns
**File:** `supabase/migrations/20260425010000_discovery_runs_progress.sql`
**Applied:** ✅ Supabase (Content OS) via MCP
**Branch / PR:** `phase-2-discovery-v2` → PR #4

### What Changed
Adds two columns to `discovery_runs` so the UI can render a real progress bar while the pipeline is in flight:

- `progress_pct smallint NOT NULL DEFAULT 0` — 0-100, set by the Python pipeline at each stage
- `progress_label text` — short 2-3 word label for the current stage

Pipeline emits 5 stages — `Fetching profile` (10%) → `Resolving links` (35%) → `Analyzing` (70%) → `Saving` (90%) → `Done` (100%). Idempotent (`ADD COLUMN IF NOT EXISTS`). No backfill needed.

UI side: new `<DiscoveryProgress runId={...}>` client component polls `getDiscoveryProgress` server action every 3s while a card is in `processing` state, calls `router.refresh()` when `status` flips. Drops into both the CreatorCard processing branch and the creator HQ "Discovering…" banner.

---

## 2026-04-25 — fix retry_creator_discovery casts input_platform_hint::platform
**File:** `supabase/migrations/20260425000300_fix_retry_creator_discovery_platform_cast.sql`
**Applied:** ✅ Supabase (Content OS) via MCP
**Branch / PR:** `phase-2-discovery-v2` → PR #4

### What Changed
UI Re-run / Retry Discovery buttons hit Postgres `42703 column input_platform_hint is of type platform but expression is of type text`. Local var `v_platform_hint TEXT` inside the RPC body coerced the platform-typed value to text before the INSERT. Added explicit `::platform` cast at the INSERT site. RPC still copies `input_handle` + `input_platform_hint` from the most recent prior run; only the type cast changed. Verified with a synthetic call against Aria Swan — new pending row inserted with correct `input_platform_hint = 'instagram'::platform`.

---

## 2026-04-25 — fix commit_discovery_result drops discovery_runs.updated_at
**File:** `supabase/migrations/20260425000200_fix_commit_discovery_result_no_updated_at.sql`
**Applied:** ✅ Supabase (Content OS) via MCP
**Branch / PR:** `phase-2-discovery-v2` → PR #4

### What Changed
Hotfix caught during v2 live smoke. `discovery_runs` has only `created_at` (no `updated_at`), but `commit_discovery_result` v2 wrote `UPDATE discovery_runs SET updated_at = NOW()` — Postgres `42703 column does not exist`, failing every successful Stage A. Removed the `updated_at` assignment. `completed_at` carries the "finished" signal.

---

## 2026-04-25 — Discovery v2 RPCs
**File:** `supabase/migrations/20260425000100_discovery_v2_rpcs.sql`
**Applied:** ✅ Supabase (Content OS) via MCP
**Branch / PR:** `phase-2-discovery-v2` → PR #4

### What Changed
- `commit_discovery_result` extended: `p_discovered_urls jsonb` + `p_bulk_import_id uuid`. Writes to `profile_destination_links`, bumps `bulk_imports.seeds_committed`. On `source='manual_add'`, only union-merges `known_usernames` — preserves the human-confirmed creator identity.
- `bulk_import_creator` extended: new `p_bulk_import_id`, returns jsonb `{bulk_import_id, creator_id, run_id}`. Old 6-arg overload dropped (TS type generator picks a single definition).
- New: `run_cross_workspace_merge_pass(p_workspace_id, p_bulk_import_id)` — reads `profile_destination_links` inverted index; raises auto-merge candidates for any monetization/aggregator URL shared across >1 creator. Idempotent via the unique pair index.

---

## 2026-04-25 — Discovery v2 schema
**File:** `supabase/migrations/20260425000000_discovery_v2_schema.sql`
**Applied:** ✅ Supabase (Content OS) via MCP
**Branch / PR:** `phase-2-discovery-v2` → PR #4

### What Changed
Additive schema for the v2 pipeline. 3 new tables (`bulk_imports`, `classifier_llm_guesses`, `profile_destination_links`) → 23 total. New columns: `discovery_runs.{bulk_import_id, apify_cost_cents, source}`, `profiles.discovery_reason`. Unique functional index on `creator_merge_candidates(LEAST/GREATEST pair)` for idempotent merge inserts. RLS on the two workspace-scoped new tables via `is_workspace_member`. `classifier_llm_guesses` intentionally workspace-agnostic (URL-keyed cache, service role writes).

---

## 2026-04-24 — fix_funnel_edges_creator_id
**File:** `supabase/migrations/20260424160000_fix_funnel_edges_creator_id.sql`
**Applied:** ✅ Supabase (Content OS) via MCP
**Branch / PR:** `phase-2-discovery-rebuild` → PR #2 merged

### What Changed
Patched `commit_discovery_result` RPC to include `creator_id` in the `funnel_edges` INSERT. The column is NOT NULL, so the RPC crashed the first time Gemini produced real funnel edges during the discovery rebuild smoke test. Fix is a one-line change to the RPC body.

---

## 2026-04-24 — create_edge_type_enum (fix latent RPC crash)
**File:** `supabase/migrations/20260424150000_create_edge_type_enum.sql`
**Applied:** ✅ Supabase (Content OS) via MCP
**Branch / PR:** `phase-2-discovery-rebuild` → PR #2 merged

### What Changed
Creates `edge_type` enum (5 values: link_in_bio, direct_link, cta_mention, qr_code, inferred) and retypes `funnel_edges.edge_type` from `text` to `edge_type`. Fixes audit item §1.1.7 — `commit_discovery_result` cast `(v_edge->>'edge_type')::edge_type` against a nonexistent type, a latent crash since the column was added.

Guarded: migration aborts if `funnel_edges` has any rows. Safe because `funnel_edges` was empty (crash had never been triggered).

---

## 2026-04-24 — Phase 2 schema migration (trends + labels + archetype/vibe move)
**File:** `supabase/migrations/20260424170000_phase_2_schema_migration.sql`
**Applied:** ✅ Supabase (Content OS) via MCP
**Branch / PR:** `phase-2-schema-migration` → PR #3

### What Changed

**New enums:**
- `trend_type` (6 values): audio | dance | lipsync | transition | meme | challenge
- `llm_model` (4 values): gemini_pro | gemini_flash | claude_opus | claude_sonnet — reserved for analysis pipelines
- `content_archetype` (12 Jungian values) — was documented in PROJECT_STATE §5 but missing from DB; audit gap closed

**Enum extensions:**
- `label_type` += `creator_niche`

**New tables (18 → 20):**
- `trends` — id, workspace_id, name, trend_type, audio_signature, audio_artist, audio_title, description, usage_count, is_canonical, peak_detected_at, timestamps. UNIQUE (workspace_id, audio_signature) WHERE NOT NULL. RLS: `is_workspace_member`. `set_updated_at` trigger.
- `creator_label_assignments` — mirrors `content_label_assignments` pattern. Reuses table-agnostic `increment_label_usage` trigger.

**Column changes:**
- `creators` ADD `archetype content_archetype` (nullable; filled by Phase 3 brand analysis)
- `creators` ADD `vibe content_vibe` (nullable; filled by Phase 3 brand analysis)
- `scraped_content` ADD `trend_id uuid` FK→trends (nullable, ON DELETE SET NULL)
- `content_analysis` DROP `archetype`
- `content_analysis` DROP `vibe`

**Safety guard:** migration aborts with a raised exception if `content_analysis` has any rows before the DROP COLUMN (today: 0 rows). No data loss possible.

**Rationale:** archetype and vibe describe a creator's overall brand identity, not individual posts. A single post carrying a "goth" vibe doesn't tell you much; across a creator's full body of work, it defines the brand. Content-level taxonomy stays with `category`, dynamic labels, and `visual_tags`.

Regenerated `src/types/database.types.ts` via `npm run db:types`. `npx tsc --noEmit` → exit 0.

---

## 2026-04-24 — bulk_import_creator RPC
**File:** `supabase/migrations/20260424000001_bulk_import_creator_rpc.sql`
**Applied:** ✅ Supabase (Content OS) via MCP

### What Changed
Adds atomic `bulk_import_creator(p_handle, p_platform_hint, p_tracking_type, p_tags, p_user_id, p_workspace_id) RETURNS uuid`. Inserts creator + primary profile + pending `discovery_runs` row and links `creators.last_discovery_run_id` to the new run — all in one transaction. SECURITY DEFINER. Replaces the per-handle JS-side `Promise.all` inserts in the old `src/app/actions.ts`.

---

## 2026-04-24 — Consolidate last_discovery_run_id on creators
**File:** `supabase/migrations/20260424000000_consolidate_last_discovery_run_id.sql`
**Applied:** ✅ Supabase (Content OS) via MCP

### What Changed
Drift fix. Live `creators` had two columns pointing at the same logical concept (`last_discovery_run_id` no-FK + `last_discovery_run_id_fk` with FK). This migration backfills into the FK column, reports orphan-pointer count via `RAISE NOTICE`, drops the no-FK column, and renames the FK column + constraint to the canonical names (`creators_last_discovery_run_id_fkey`).

---

## 2026-04-23 — Fix retry_creator_discovery + canonical_name guard
**File:** No local SQL file — applied directly via Supabase MCP
**Applied:** ✅ Supabase (Content OS) via MCP

### What Changed
**RPC patch: `retry_creator_discovery`**
- Now copies `input_handle` and `input_platform_hint` from most recent prior `discovery_runs` row into the newly created run
- Previously these were NULL on retry runs, causing the Python worker to fail immediately (no handle = nothing to discover)

**RPC patch: `commit_discovery_result`**
- Added `NULLIF(NULLIF(TRIM(name), ''), 'Unknown')` guard when writing `canonical_name`
- Prevents Gemini returning the literal string "Unknown" from overwriting a valid canonical_name on a retry run

**Data fix:**
- `UPDATE creators SET canonical_name = 'Esmae' WHERE slug LIKE 'esmaecursed%' AND canonical_name = 'Unknown'`

---

## 2026-04-23 — Add is_primary to profiles
**File:** `supabase/migrations/20260423000000_add_is_primary_to_profiles.sql`
**Applied:** ✅ Supabase (Content OS) via MCP

### What Changed
- Added `is_primary BOOLEAN NOT NULL DEFAULT FALSE` to `profiles`
- Required by `commit_discovery_result` RPC which marks one profile per creator as primary for its platform
- Discovered during first live discovery pipeline run (gothgirlnatalie, ariaxswan, esmaecursed)

---

## 2026-04-23 — Outlier Multiplier Column
**File:** `supabase/migrations/20240103000000_outlier_multiplier.sql`
**Applied:** ✅ Supabase (Content OS) via MCP

### What Changed
- Added `outlier_multiplier NUMERIC(5,2)` to `scraped_content`
- Rewrote `flag_outliers(p_profile_id)` to compute and store the ratio, then set `is_outlier = true` when ≥ 3.0
- Window: last 50 posts OR last 90 days (smaller). Floor: 15 posts. Age guard: 48h.

---

## 2026-04-22 — Creator Layer
**File:** `supabase/migrations/20240102000000_creator_layer.sql`
**Applied:** ✅ Supabase (Content OS) via MCP
**Method:** Supabase:apply_migration tool (3 separate calls to handle enum ADD VALUE constraints)

### What Changed
**Enums extended:**
- `platform` +12 values: onlyfans, fanvue, fanplace, amazon_storefront, tiktok_shop, linktree, beacons, custom_domain, telegram_channel, telegram_cupidbot, facebook, other
- `post_type` +3 values: story_highlight, youtube_short, youtube_long, other
- `signal_type` +1 value: new_monetization_detected

**New enums:**
- `account_type`: social, monetization, link_in_bio, messaging, other
- `onboarding_status`: processing, ready, failed, archived
- `monetization_model`: subscription, tips, ppv, affiliate, brand_deals, ecommerce, coaching, saas, mixed, unknown
- `discovery_run_status`: pending, processing, completed, failed
- `merge_candidate_status`: pending, merged, dismissed
- `label_type`: content_format, trend_pattern, hook_style, visual_style, other

**New tables (7):**
- `creators` — root entity, source of truth
- `discovery_runs` — pipeline processing log
- `creator_merge_candidates` — cross-platform identity collision detection
- `funnel_edges` — directed traffic flow between creator accounts
- `content_labels` — dynamic content taxonomy
- `content_label_assignments` — many:many posts to labels
- `creator_brand_analyses` — Phase 3 brand reports

**Columns added to `profiles`:**
- `creator_id` UUID FK creators (nullable)
- `account_type` account_type DEFAULT 'social'
- `url` TEXT
- `discovery_confidence` NUMERIC(3,2)
- `updated_at` TIMESTAMPTZ

**New RPCs:**
- `commit_discovery_result` — transactional discovery commit
- `mark_discovery_failed` — pipeline error handler
- `retry_creator_discovery` — UI retry trigger
- `merge_creators` — identity merge handler

**New triggers:**
- `trg_creators_updated_at`
- `trg_profiles_updated_at`
- `trg_increment_label_usage`

**Realtime enabled on:** creators, discovery_runs, creator_merge_candidates

---

## 2026-04-22 — Initial Schema
**File:** `supabase/migrations/20240101000000_initial_schema.sql`
**Applied:** ✅ Supabase (Content OS) via MCP

### What Changed
Initial platform-first schema:
- Tables: workspaces, workspace_members, profiles, scraped_content, content_metrics_snapshots, profile_metrics_snapshots, content_analysis, profile_scores, trend_signals, alerts_config, alerts_feed
- Functions: calculate_rank, flag_outliers, refresh_profile_score, is_workspace_member
- RLS on all tables
- All indexes
