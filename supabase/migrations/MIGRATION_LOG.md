# Migration Log

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
