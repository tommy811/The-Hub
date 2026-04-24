# Migration Log

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
