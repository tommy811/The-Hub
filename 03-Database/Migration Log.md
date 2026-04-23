# Migration Log

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

## Pending — Phase 2 Entry

**File to create:** `supabase/migrations/20240201000000_phase2_trends.sql`
**Status:** ⬜ Not yet applied — runs when Phase 2 ingestion starts

**New enum:** `trend_type` (audio, dance, lipsync, transition, meme, challenge)

**Enum addition:** `label_type` += `creator_niche`

**New table: `trends`** — canonical trend registry, audio_signature dedup (UNIQUE per workspace)

**New table: `creator_label_assignments`** — mirrors content_label_assignments for creator-level niche tagging

**Column additions on `creators`:** `archetype content_archetype` (nullable), `vibe content_vibe` (nullable)

**Column addition on `scraped_content`:** `trend_id uuid REFERENCES trends(id)` (nullable)

**Column removals from `content_analysis`:** DROP `archetype`, DROP `vibe` (moved to creator level)

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
