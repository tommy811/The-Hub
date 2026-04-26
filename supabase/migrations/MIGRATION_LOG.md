# Migration Log

## 20260426080000_watchdog_view_with_llm_suggestions

Applied 2026-04-26 via Supabase MCP `apply_migration`. Branch `phase-2-discovery-v2`. Part of T20 (sync 17).

`CREATE OR REPLACE VIEW new_platform_watchdog` — REPLACES the T19 version (from migration `20260426060000`). Joins to `classifier_llm_guesses` via CTEs (`grouped` for the `platform='other'` rows aggregated by URL host + `guess_per_host` via `DISTINCT ON (host)` for the latest matching guess per host). Surfaces Gemini's enriched suggestion (`suggested_label`, `suggested_slug`, `description`, `icon_category`) per host alongside the active-row aggregate (creator_count, last_seen, sample_url). 11 columns total.

**Operator workflow:** `SELECT * FROM new_platform_watchdog ORDER BY creator_count DESC LIMIT 50;` returns each novel host once with Gemini's recommendation pre-populated. VA ratifies in one click; the standard 3-step add (gazetteer rule + `src/lib/platforms.ts` PLATFORMS dict entry + `HOST_PLATFORM_MAP` entry) takes ~5 minutes per platform. Returns 0 rows currently — gazetteer + T17 backfill comprehensive for the 5-creator dataset.

**Caveat:** the original T20 spec used 4 correlated subqueries to fetch the LLM-guess columns. Postgres rejected that with `42803` (column must appear in the GROUP BY clause or be used in an aggregate function). Refactored to CTE-based LEFT JOIN with the same semantics — `DISTINCT ON (host)` over `classifier_llm_guesses` ordered by `classified_at DESC` to get the latest guess per host, then LEFT JOIN to the grouped active rows.

---

## 20260426070000_classifier_llm_guesses_enriched_metadata

Applied 2026-04-26 via Supabase MCP `apply_migration`. Branch `phase-2-discovery-v2`. Part of T20 (sync 17).

Adds 4 nullable TEXT columns to `classifier_llm_guesses`:

- `suggested_label TEXT` — human-readable platform label (e.g. `"Cash App"`, `"Substack"`).
- `suggested_slug TEXT` — snake_case slug suitable for the `platform` enum if ratified (e.g. `"cashapp"`, `"substack"`).
- `description TEXT` — short Gemini-generated description of what the host is.
- `icon_category TEXT` — Gemini's hint at icon family (e.g. `"monetization"`, `"social"`, `"messaging"`) so the operator can pick the right react-icon Si* / lucide fallback quickly.

All 4 columns nullable; empty-string LLM responses are coerced to NULL by the Python writer (`_cache_insert` in `scripts/pipeline/classifier.py`). The companion code change in `_classify_via_llm` returns a 5-tuple `(platform, account_type, confidence, model_version, enriched_metadata: dict)`; `_cache_insert(supabase, canonical_url, platform, account_type, confidence, model_version, enriched=...)` persists the dict. Idempotent (`ADD COLUMN IF NOT EXISTS`).

---

## 20260426060000_new_platform_watchdog_view

Applied 2026-04-26 via Supabase MCP `apply_migration`. Branch `phase-2-discovery-v2`. Part of T19 (sync 17).

`CREATE OR REPLACE VIEW new_platform_watchdog AS ...` — surfaces every `is_active=true` profile row with `platform='other'` grouped by URL host. Returns: host (extracted via regex), creator_count, profile_count, last_seen, sample_url, sample creator name. VA-friendly query for triaging novel platforms.

This is the v1 watchdog view; superseded the same day by `20260426080000_watchdog_view_with_llm_suggestions` which adds Gemini enrichment per host. v1 returns the aggregate columns only; v2 adds 4 LLM-suggestion columns via CTE join to `classifier_llm_guesses`.

Returns 0 rows currently — gazetteer + T17 backfill comprehensive for the 5-creator dataset.

---

## 20260426050000_creator_cover_and_banner

Applied 2026-04-26 via Supabase MCP `apply_migration`. Branch `phase-2-discovery-v2`. Part of T17 (sync 16).

Adds 3 nullable text columns to `creators` to back the new banner / cover / override-avatar UI surface:

- `cover_image_url TEXT` — scraper-set, null pending Phase 3 scraper work. Intended to hold IG / FB / Twitter / Reddit cover photos when those scrapers are wired.
- `banner_url TEXT` — agency-managed override. Operators can set this directly to override whatever the scraper would otherwise pick.
- `override_avatar_url TEXT` — agency-managed headshot. When set, both creator HQ and the grid card prefer this over the scraper-fetched `profiles.avatar_url`. Solves the IG-CDN avatar URL expiry problem for any creator the agency wants pinned to a stable image.

UI side: new `<BannerWithFallback>` client component renders on creator HQ below the merge-candidate banner / above the header — uses `banner_url` if set, else `cover_image_url`, else degrades to a gradient placeholder. Both columns nullable; UI has a clean fallback for either.

Idempotent (`ADD COLUMN IF NOT EXISTS`). No backfill — all 3 columns default null. The pre-existing `profiles.avatar_url` is still scraper-managed and untouched.

---

## 20260426040000_add_platform_values_specific_aggregators_and_monetization

Applied 2026-04-26 via Supabase MCP `apply_migration`. Branch `phase-2-discovery-v2`. Part of T17 (sync 16).

Extends the Postgres `platform` enum with 19 new values to support specific-aggregator + specific-monetization identification (instead of bucketing everything under `custom_domain` / `other`):

`link_me`, `tapforallmylinks`, `allmylinks`, `lnk_bio`, `snipfeed`, `launchyoursocials`, `fanfix`, `cashapp`, `venmo`, `snapchat`, `reddit`, `spotify`, `threads`, `bluesky`, `kofi`, `buymeacoffee`, `substack`, `discord`, `whatsapp`.

**Total `platform` enum count: ~37 values** (post-migration).

**Why this matters:** the previous `custom_domain` bucket was hiding genuine duplicate-row collisions. e.g. Valentina had `link.me/valentina` AND `cash.app/valentina` both classified as `custom_domain`, both with the same `profile_url` shape — the `(creator_id, platform, profile_url)` unique constraint blocked the second INSERT and the resolver had to soft-fail. With distinct enum values, the rows coexist cleanly. Architectural alternative considered: synthetic-handle uniqueness (`handle = "tapforallmylinks.com_esmaecursed"`) — uglier; changing the unique-constraint shape — riskier; adding enum values — cleanest.

**Companion changes (NOT in this migration but applied alongside):**
- Pydantic `Platform = Literal[...]` in `scripts/schemas.py` extended to match. Caught at pre-commit when the first discovery run after migration failed with `pydantic.ValidationError` — fixed before push. Future enum extensions could silently break discovery without a CI diff test (flagged as future work in PROJECT_STATE §20).
- Gazetteer (`data/monetization_overlay.yaml`) rewritten with 13 new specific host→platform rules; 6 older generic rules removed so new specifics win.
- `src/lib/platforms.ts` PLATFORMS dict gained 13+ new entries with Si* icons (react-icons 5.6.0) + lucide fallbacks for Cash App / Venmo / Fanfix.
- 11 existing profile rows backfilled via direct `UPDATE` from `other` / `custom_domain` to specific platforms (tapforallmylinks=3, link_me=1, fanfix=1, cashapp=1, venmo=1, snapchat=2, reddit=1, spotify=1).

---

## 20260426030000_commit_discovery_result_v4_update_destination_class

Applied 2026-04-26 via Supabase MCP `apply_migration`. Branch `phase-2-discovery-v2`.

Body identical to `20260426010000` (v3) except the `ON CONFLICT (profile_id, canonical_url) DO UPDATE` clause on the `profile_destination_links` INSERT now also updates `destination_class = EXCLUDED.destination_class`. Without it, rows from buggy pre-fix runs stuck around with stale class values (e.g. `t.me/...` at `other` when the resolver was later patched to map `messaging`). Caught during the 2026-04-26 smoke when re-running discovery on a creator with cached destination rows didn't refresh their class. The `harvest_method` and `raw_text` updates already used `COALESCE(EXCLUDED.x, profile_destination_links.x)`; left those untouched.

---

## 20260426020000_extend_destination_class_check

Applied 2026-04-26 via Supabase MCP `apply_migration`. Branch `phase-2-discovery-v2`.

Extends the `profile_destination_links.destination_class` CHECK constraint from 4 values (`monetization|aggregator|social|other`) to 10 (`monetization|aggregator|social|commerce|messaging|content|affiliate|professional|other|unknown`) — matching the `DestinationClass` Literal in `scripts/harvester/types.py`. Without this, the harvester crashed on insert any time a row tagged `messaging` (Telegram / WhatsApp / Discord) hit `commit_discovery_result` — caught by the 2026-04-26 smoke. Note: TEXT-with-CHECK pattern, not a Postgres ENUM. Forward-compat extensions are a single `DROP CONSTRAINT / ADD CONSTRAINT` instead of `ALTER TYPE ... ADD VALUE` ceremony.

---

## 20260426010000_commit_discovery_result_v3_harvester_audit

Applied 2026-04-26 via Supabase MCP `apply_migration`. Branch `phase-2-discovery-v2`.

Extends `commit_discovery_result` to write the 3 new audit columns on `profile_destination_links` (`harvest_method`, `raw_text`, `harvested_at`). The `p_discovered_urls` jsonb shape gains optional fields `harvest_method` and `raw_text` per element; the RPC reads `v_url->>'harvest_method'` and `v_url->>'raw_text'` and threads them through both the INSERT and the ON CONFLICT DO UPDATE (using `COALESCE(EXCLUDED.x, profile_destination_links.x)` so older rows without the audit fields don't get nulled out). Body otherwise identical to `20260425000200`.

---

## 20260426000000_url_harvester_v1

Applied 2026-04-26 via Supabase MCP `apply_migration`. Branch `phase-2-discovery-v2`.

Backs the Universal URL Harvester ship.

**Audit columns on `profile_destination_links`:**
- `harvest_method TEXT` — `cache | httpx | headless`. NULL on rows pre-dating the harvester.
- `raw_text TEXT` — the anchor / button text that surfaced the URL during harvest.
- `harvested_at TIMESTAMPTZ DEFAULT NOW()` — when this destination was last (re)harvested.

**New table `url_harvest_cache` (23 → 24 tables):**
- `canonical_url TEXT PRIMARY KEY`
- `harvest_method TEXT NOT NULL CHECK IN ('httpx','headless')`
- `destinations JSONB NOT NULL` — array of `{canonical_url, raw_url, raw_text, destination_class}`
- `harvested_at TIMESTAMPTZ NOT NULL DEFAULT NOW()`
- `expires_at TIMESTAMPTZ NOT NULL` — 24h TTL by default; set by Python writer
- `created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()`
- Index `idx_url_harvest_cache_expires` on `expires_at` for TTL-aware lookups
- No RLS — workspace-agnostic, service role only (mirrors `classifier_llm_guesses`)

---

## 20260425030000_bulk_import_platform_cast

Applied 2026-04-25 via Supabase MCP `apply_migration`. Branch `phase-2-discovery-v2`, PR #4.

Same root cause as `20260425000300` (which fixed the retry RPC's identical bug). `bulk_import_creator` declared `p_platform_hint TEXT` and cast it correctly in the `creators` and `profiles` INSERTs, but passed the raw text into the `discovery_runs` INSERT — Postgres errored with `22P02 column "input_platform_hint" is of type platform but expression is of type text`. Every Bulk Paste / Single Handle import via the UI failed with this error in the toast. Fix: explicit `::platform` cast at the third INSERT site. Behavior identical otherwise.

---

## 20260425020000_retry_updates_last_run_id

Applied 2026-04-25 via Supabase MCP `apply_migration`. Branch `phase-2-discovery-v2`, PR #4.

`retry_creator_discovery` created the new run + flipped `creators.onboarding_status='processing'` but never updated `creators.last_discovery_run_id`. The new `<DiscoveryProgress>` UI polls the run pointed to by `last_discovery_run_id`, so after every retry it polled the previous failed run, immediately saw its terminal status, and the new run's spinner was stuck at "Queued 0%" forever (worker actually ran the new attempt within seconds; UI never observed it). Fix: add `last_discovery_run_id = v_run_id` to the `UPDATE creators` clause. `bulk_import_creator` already wires this correctly (verified via `pg_get_functiondef`).

---

## 20260425010000_discovery_runs_progress

Applied 2026-04-25 via Supabase MCP `apply_migration`. Branch `phase-2-discovery-v2`, PR #4.

Adds two columns to `discovery_runs` so the UI can render a real progress bar while the pipeline is in flight:

- `progress_pct smallint NOT NULL DEFAULT 0` — 0-100, set by the Python pipeline at each stage
- `progress_label text` — short 2-3 word label for the current stage (`Fetching profile` / `Resolving links` / `Analyzing` / `Saving` / `Done`)

Idempotent (`ADD COLUMN IF NOT EXISTS`). No backfill needed — existing rows keep `progress_pct=0, progress_label=null` until next discovery (terminal rows never re-run).

Pipeline emits at `_emit(10, "Fetching profile")` (start of `resolver.resolve_seed`), `_emit(35, "Resolving links")` (after Stage A succeeds), `_emit(70, "Analyzing")` (just before Gemini call), `_emit(90, "Saving")` and `_emit(100, "Done")` (in `discover_creator.run()` around `_commit_v2`).

UI side: `<DiscoveryProgress runId={...}>` client component polls `getDiscoveryProgress` server action every 3s while a card is in `processing` state, calls `router.refresh()` when `status` flips out of `pending|processing`. Drops into the CreatorCard processing branch + creator HQ "Discovering…" banner.

---

## 20260425000300_fix_retry_creator_discovery_platform_cast

Applied 2026-04-25 via Supabase MCP `apply_migration`. Branch `phase-2-discovery-v2`, PR #4.

UI Re-run / Retry Discovery buttons errored with `column "input_platform_hint" is of type platform but expression is of type text`. The RPC's local var `v_platform_hint TEXT` carried the value through plpgsql's implicit-coerce pipe and arrived at the INSERT as text. Fix: explicit `::platform` cast at the INSERT site. No behavior change beyond the cast — RPC still copies `input_handle` + `input_platform_hint` from the most recent prior run. Verified by re-running `retry_creator_discovery(aria.id, NULL)` — new pending row inserted cleanly with correct types.

---

## 20260425000200_fix_commit_discovery_result_no_updated_at

Applied 2026-04-25 via Supabase MCP `apply_migration`. Branch `phase-2-discovery-v2`, PR #4.

Hotfix caught during the v2 live smoke: `commit_discovery_result` v2 wrote `UPDATE discovery_runs SET updated_at = NOW()`, but `discovery_runs` has only `created_at` (no `updated_at` column). Crashed with Postgres `42703 column does not exist` at the end of every successful Stage A on smoke seeds Esmae and Natalie. Fix: drop the `updated_at` assignment from the discovery_runs UPDATE. `completed_at` already carries the "finished" signal; the unique `updated_at` assignment was a copy-paste from `creators`/`profiles` branches.

---

## 20260425000100_discovery_v2_rpcs

Applied 2026-04-25 via Supabase MCP `apply_migration`. Branch `phase-2-discovery-v2`, PR #4.

Three RPC changes:

- **`commit_discovery_result` v2** — new params `p_discovered_urls jsonb DEFAULT '[]'` and `p_bulk_import_id uuid DEFAULT NULL`. Writes each discovered URL to `profile_destination_links`. Bumps `bulk_imports.seeds_committed` when `p_bulk_import_id` is provided. Source-aware: on `discovery_runs.source = 'manual_add'` only union-merges `known_usernames`, preserving the creator's human-confirmed canonical_name / primary_niche / monetization_model. Returns `{creator_id, accounts_upserted, merge_candidates_raised, urls_recorded}`.
- **`bulk_import_creator` v2** — accepts `p_bulk_import_id uuid DEFAULT NULL`. When NULL, creates a new `bulk_imports` row (single-handle path). Returns `jsonb {bulk_import_id, creator_id, run_id}` instead of raw `uuid`. Old 6-arg overload dropped separately (so the TS type generator picks a single definition).
- **`run_cross_workspace_merge_pass(p_workspace_id, p_bulk_import_id)` (new)** — reads `profile_destination_links` inverted index; for any URL with `destination_class IN ('monetization','aggregator')` shared across >1 creator, inserts a `creator_merge_candidates` row per pair (ordered `LEAST/GREATEST`). Idempotent via the unique pair index. Sets `bulk_imports.merge_pass_completed_at` and final status when `p_bulk_import_id` is provided.

---

## 20260425000000_discovery_v2_schema

Applied 2026-04-25 via Supabase MCP `apply_migration`. Branch `phase-2-discovery-v2`, PR #4.

Additive schema migration backing the v2 pipeline.

**New tables (20 → 23):**
- `bulk_imports` — first-class observable job table with `seeds_total`, `seeds_committed`, `seeds_failed`, `seeds_blocked_by_budget`, `cost_apify_cents`, `merge_pass_completed_at`, `status` (`running|completed|completed_with_failures|partial_budget_exceeded|cancelled`). RLS via `is_workspace_member`. `set_updated_at` trigger.
- `classifier_llm_guesses` — workspace-agnostic cache keyed on `canonical_url`. Columns: `platform_guess`, `account_type_guess`, `confidence` (0-1), `model_version`, `classified_at`. No RLS — service role writes, reads keyed on URL only.
- `profile_destination_links` — persistent reverse index. PK `(profile_id, canonical_url)`. Columns: `destination_class` (`monetization|aggregator|social|other`), `workspace_id`. Indexes on `canonical_url`, partial on `destination_class IN ('monetization','aggregator')`, composite on `(workspace_id, canonical_url)`. RLS via `is_workspace_member`.

**Column additions:**
- `discovery_runs.bulk_import_id` (FK → `bulk_imports`, nullable, ON DELETE SET NULL)
- `discovery_runs.apify_cost_cents` (int NOT NULL DEFAULT 0)
- `discovery_runs.source` (text NOT NULL DEFAULT 'seed', CHECK `source IN ('seed','manual_add','retry','auto_expand')`)
- `profiles.discovery_reason` (text, audit trail for `rule:{name}` / `llm:{kind}` / `manual_add`)

**New constraint:** unique functional index `creator_merge_candidates_pair_uniq` on `(LEAST(creator_a_id, creator_b_id), GREATEST(creator_a_id, creator_b_id))` — idempotent merge-candidate inserts. Enables `ON CONFLICT DO UPDATE evidence` in `run_cross_workspace_merge_pass`.

No existing data touched.

---

## 20260424160000_fix_funnel_edges_creator_id

Applied 2026-04-24 via Supabase MCP `apply_migration`. Branch `phase-2-discovery-rebuild`, PR #2 (merged).

Patched `commit_discovery_result` RPC: the `funnel_edges` INSERT was omitting `creator_id`, which is NOT NULL. The RPC crashed the first time Gemini produced real funnel edges during the discovery rebuild smoke test. One-line fix to the RPC body; no table changes.

---

## 20260424150000_create_edge_type_enum

Applied 2026-04-24 via Supabase MCP `apply_migration`. Branch `phase-2-discovery-rebuild`, PR #2 (merged).

Creates `edge_type` enum (5 values: `link_in_bio`, `direct_link`, `cta_mention`, `qr_code`, `inferred`) and retypes `funnel_edges.edge_type` from `text` to `edge_type`. Fixes audit §1.1.7: `commit_discovery_result` cast `(v_edge->>'edge_type')::edge_type` against a nonexistent type — latent crash on first real funnel edge. Guard aborts migration if `funnel_edges` has any rows (it was empty).

---

## 20260424170000_phase_2_schema_migration

Applied 2026-04-24 via Supabase MCP `apply_migration`. Branch `phase-2-schema-migration`, PR #3.

**New enums:**
- `trend_type` (audio, dance, lipsync, transition, meme, challenge)
- `llm_model` (gemini_pro, gemini_flash, claude_opus, claude_sonnet) — reserved for analysis pipelines
- `content_archetype` (12 Jungian values — was documented in PROJECT_STATE §5 but missing from DB; audit gap closed)

**Enum extension:** `label_type` += `creator_niche`

**New tables (18 → 20):**
- `trends` — id, workspace_id, name, trend_type, audio_signature, audio_artist, audio_title, description, usage_count, is_canonical, peak_detected_at, timestamps. UNIQUE (workspace_id, audio_signature) WHERE audio_signature IS NOT NULL. RLS via `is_workspace_member`. `set_updated_at` trigger.
- `creator_label_assignments` — mirrors `content_label_assignments` pattern. Reuses table-agnostic `increment_label_usage` trigger.

**Column changes:**
- `creators` ADD `archetype content_archetype` (nullable — filled by Phase 3 brand analysis)
- `creators` ADD `vibe content_vibe` (nullable — filled by Phase 3 brand analysis)
- `scraped_content` ADD `trend_id uuid` FK→trends (nullable, ON DELETE SET NULL)
- `content_analysis` DROP `archetype` (moved to creators)
- `content_analysis` DROP `vibe` (moved to creators)

Guard: migration aborts if `content_analysis` has any rows before DROP COLUMN (today: 0 rows). No data loss possible.

Regenerated `src/types/database.types.ts` via `npm run db:types`. `npx tsc --noEmit` → exit 0.

---

## 20260424000001_bulk_import_creator_rpc

Applied 2026-04-24 via Supabase MCP `apply_migration` (registered as `bulk_import_creator_rpc`).

Adds atomic `bulk_import_creator(p_handle, p_platform_hint, p_tracking_type, p_tags, p_user_id, p_workspace_id) RETURNS uuid`. Inserts creator + primary profile + pending discovery_run, then links `creators.last_discovery_run_id` to the new run. SECURITY DEFINER, granted to authenticated/anon/service_role.

Replaces the per-handle JS-side `Promise.all` of inserts in the old `src/app/actions.ts` flow. The new server action `bulkImportCreators` (in `src/app/(dashboard)/creators/actions.ts`, coming in L4.3) will loop over handles and call this RPC once per handle.

Smoke-tested 2026-04-24: synthetic handle inserted via RPC, all three rows present (creator with `last_discovery_run_id` set, primary profile, pending discovery_run), cleanup ran successfully.

---

## 20260424000000_consolidate_last_discovery_run_id

Applied 2026-04-24 via Supabase MCP `apply_migration` (registered as `consolidate_last_discovery_run_id`).

Drift fix. The live `creators` table had two columns pointing at the same logical concept: `last_discovery_run_id` (no FK) and `last_discovery_run_id_fk` (FK→discovery_runs.id). This migration:

1. Backfills any value from `last_discovery_run_id` into `last_discovery_run_id_fk` where the FK column was NULL and the target run exists.
2. Reports orphan-pointer count (rows where the no-FK column pointed at a deleted run) via `RAISE NOTICE` before discarding them on column drop.
3. Drops the no-FK column.
4. Renames `last_discovery_run_id_fk` → `last_discovery_run_id` (column).
5. Renames the FK constraint `creators_last_discovery_run_id_fk_fkey` → `creators_last_discovery_run_id_fkey`.

`commit_discovery_result` RPC body unchanged — already wrote to `last_discovery_run_id`.

Post-state verified: 1 column named `last_discovery_run_id` with FK constraint `creators_last_discovery_run_id_fkey → discovery_runs(id) ON DELETE SET NULL`.

---

## fix_retry_discovery_and_canonical_name_guard (applied via MCP — no local file)

Applied 2026-04-23. Two RPC patches:

**`retry_creator_discovery`** — now copies `input_handle` and `input_platform_hint` from the most recent prior `discovery_runs` row into the new run. Previously these were NULL on retry runs, causing the Python worker to have no context to work with (re-ran but immediately failed because it didn't know the handle).

**`commit_discovery_result`** — added `NULLIF(NULLIF(TRIM(name), ''), 'Unknown')` guard when writing `canonical_name`. Prevents Gemini returning the string "Unknown" from overwriting a previously valid canonical_name on a retry run.

Data fix also applied: `UPDATE creators SET canonical_name = 'Esmae' WHERE slug LIKE 'esmaecursed%' AND canonical_name = 'Unknown'`

---

## 20260423000000_add_is_primary_to_profiles

Adds `is_primary BOOLEAN NOT NULL DEFAULT FALSE` column to `profiles`.

Required by `commit_discovery_result` RPC which marks one profile per creator as the primary account for that platform. Applied via Supabase MCP on 2026-04-23 during discovery pipeline debugging.

---

## 20240103000000_outlier_multiplier

Adds `outlier_multiplier NUMERIC(5,2)` column to `scraped_content` and rewrites `flag_outliers` to store the computed ratio alongside the boolean flag.

Outlier logic: `outlier_multiplier = view_count / median(last_50_posts)`. Window: last 50 posts OR last 90 days (smaller). Floor: 15 posts minimum. Age guard: ≥ 48 hours. Threshold: ≥ 3.0 sets `is_outlier = true`.

---

## 20240102000000_creator_layer

Creator entity + discovery pipeline + identity resolution.

New tables: creators, discovery_runs, creator_merge_candidates, funnel_edges,
content_labels, content_label_assignments, creator_brand_analyses.

New columns on profiles: creator_id, account_type, url, discovery_confidence, updated_at.

New RPCs: commit_discovery_result, mark_discovery_failed, retry_creator_discovery, merge_creators.

New helper RPCs/triggers: normalize_handle, set_updated_at (trigger), increment_label_usage (trigger).

New triggers: trg_creators_updated_at, trg_profiles_updated_at, trg_increment_label_usage.

Realtime enabled: creators, discovery_runs, creator_merge_candidates.

---

## 20240101000000_initial_schema

Base platform schema.

Tables: workspaces, workspace_members, profiles, scraped_content,
content_metrics_snapshots, profile_metrics_snapshots, content_analysis,
profile_scores, trend_signals, alerts_config, alerts_feed.

Functions: calculate_rank, flag_outliers, refresh_profile_score, is_workspace_member.

RLS on all tables. All indexes.

---

## Pending

No pending migrations at this time. Next migration slated is the Phase 2 scraping work (Apify ingestion + `quality_flag`/`quality_reason` on `scraped_content` per PROJECT_STATE §15.2).

> **Tooling note:** `npm run db:schema` is still blocked on missing `SUPABASE_DB_URL` in `scripts/.env`. Live DB has 24 tables; `docs/SCHEMA.md` shows 23. PROJECT_STATE.md §4.1 has been hand-updated. See PROJECT_STATE §20 Known Limitations for the regen runbook.
