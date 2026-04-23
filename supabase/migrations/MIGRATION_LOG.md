# Migration Log

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

## Pending — Phase 2 Entry

Runs when Phase 2 ingestion starts. **Do NOT apply yet.**

**File to create:** `20240201000000_phase2_trends.sql`

**New enum:** `trend_type` (audio, dance, lipsync, transition, meme, challenge)

**Enum addition:** `label_type` += `creator_niche`

**New table: `trends`** — canonical trend registry with audio_signature dedup

**New table: `creator_label_assignments`** — mirrors content_label_assignments for creator-level niche tagging

**Column additions on `creators`:** `archetype content_archetype`, `vibe content_vibe`

**Column addition on `scraped_content`:** `trend_id uuid REFERENCES trends(id)`

**Column removals from `content_analysis`:** DROP `archetype`, DROP `vibe` (both move to creator level)
