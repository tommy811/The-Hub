# RPC Reference

All callable via: `supabase.rpc('function_name', { args })`

---

## commit_discovery_result (v2, 2026-04-25)
**Called by:** Python discovery pipeline (`pipeline/resolver.py` → `discover_creator._commit_v2`) on successful resolver output
**Args:**
- `p_run_id` UUID
- `p_creator_data` JSONB — `{canonical_name, known_usernames[], display_name_variants[], primary_platform, primary_niche, monetization_model}`
- `p_accounts` JSONB — array of `{account_type, platform, handle, url, display_name, bio, follower_count, is_primary, discovery_confidence, reasoning}`
- `p_funnel_edges` JSONB — array of `{from_handle, from_platform, to_handle, to_platform, edge_type, confidence}`
- `p_discovered_urls` JSONB DEFAULT `'[]'` — array of `{canonical_url, platform, account_type, destination_class, reason}` (v2)
- `p_bulk_import_id` UUID DEFAULT NULL (v2)

**Returns:** `{creator_id, accounts_upserted, merge_candidates_raised, urls_recorded}`

**Does (transactional):**
1. Reads `discovery_runs.source` for this run.
2. On `source='manual_add'`: only union-merges `known_usernames` on the existing creator (preserves human-confirmed canonical_name / primary_niche / monetization_model). On any other source: enriches creator with canonical_name / niches / monetization_model and sets `onboarding_status='ready'`.
3. Upserts each proposed account as a `profiles` row (unique on `(workspace_id, platform, handle)`).
4. Inserts funnel edges after resolving from/to handles to profile_ids.
5. Records each discovered URL in `profile_destination_links` against the creator's primary profile.
6. Marks discovery_run completed (`completed_at = NOW()`, `assets_discovered_count`, `funnel_edges_discovered_count`, `bulk_import_id`).
7. If `p_bulk_import_id` is set, increments `bulk_imports.seeds_committed`.

> **Fixed 2026-04-25 (migration `20260425000200`):** v2 initially wrote `UPDATE discovery_runs SET updated_at = NOW()`, but `discovery_runs` has only `created_at` — caused Postgres `42703 column does not exist` on every successful Stage A. `completed_at` carries the "finished" signal; `updated_at` assignment dropped.

---

## bulk_import_creator (v2, 2026-04-25)
**Called by:** Server actions `bulkImportCreators` (one call per handle in the batch) and `importSingleCreator` (single-handle path).
**Args:** `p_handle` TEXT, `p_platform_hint` TEXT, `p_tracking_type` tracking_type, `p_tags` TEXT[], `p_user_id` UUID, `p_workspace_id` UUID, `p_bulk_import_id` UUID DEFAULT NULL
**Returns:** JSONB `{bulk_import_id, creator_id, run_id}`
**Does:** When `p_bulk_import_id` is NULL, creates a new `bulk_imports` row (single-handle path). Inserts creator (placeholder `canonical_name = handle` until discovery fills), primary profile stub, and a pending `discovery_runs` row linked to the bulk. Returns all three ids for the caller to thread.

> **Shape change (v2):** returns JSONB instead of raw UUID. Callers extract `res.data.creator_id` for anything that previously expected a single uuid. Old 6-arg overload was dropped (so the TypeScript type generator sees one signature; `p_bulk_import_id` has a DEFAULT so pre-v2 callers passing 6 args still work).

> **Fixed 2026-04-25 (migration `20260425030000`):** the `discovery_runs` INSERT was passing `p_platform_hint` raw (text) instead of `p_platform_hint::platform`. The `creators` and `profiles` INSERTs already cast — only the third INSERT was missed. Postgres `22P02 column "input_platform_hint" is of type platform but expression is of type text`. Every Bulk Paste / Single Handle import errored in the toast. Same shape as `retry_creator_discovery`'s earlier-day fix — missed in that sweep.

---

## run_cross_workspace_merge_pass (new, 2026-04-25)
**Called by:** Python worker after each batch of runs terminates, for every `bulk_import_id` represented in the batch.
**Args:** `p_workspace_id` UUID, `p_bulk_import_id` UUID DEFAULT NULL
**Returns:** JSONB `{buckets_evaluated, bulk_import_id}`
**Does:** Reads `profile_destination_links` as an inverted index. For every `canonical_url` with `destination_class IN ('monetization','aggregator')` shared across >1 creator in the workspace, inserts a `creator_merge_candidates` row per pair (ordered `LEAST/GREATEST`). Idempotent via the unique functional pair index (`ON CONFLICT DO UPDATE evidence`). When `p_bulk_import_id` is provided, sets `bulk_imports.merge_pass_completed_at` and final status based on the bulk's seed-level counters.

---

## mark_discovery_failed
**Called by:** Python pipeline on any exception
**Args:** `p_run_id` UUID, `p_error` TEXT
**Does:** Sets run status = failed, sets creator onboarding_status = failed, stores error message

---

## retry_creator_discovery
**Called by:** UI Retry button on failed creator card, and Re-run Discovery button on creator detail page
**Args:** `p_creator_id` UUID, `p_user_id` UUID
**Returns:** new `run_id` UUID
**Does:** Creates new discovery_runs row (increments attempt_number), **copies `input_handle` and `input_platform_hint` from most recent prior run** (so the worker knows what handle to discover), resets creator to onboarding_status = processing, and **points `creators.last_discovery_run_id` at the new run**.

> **Fixed 2026-04-23:** Previous version did not copy `input_handle` into the new row. Retry runs had NULL handle and immediately failed at the worker's fetch step.

> **Fixed 2026-04-25 (migration `20260425000300`):** Local var `v_platform_hint TEXT` was carrying the value through plpgsql as text, so the INSERT into `discovery_runs(input_platform_hint)` (column type: `platform` enum) failed with `42703 column ... is of type platform but expression is of type text`. UI Re-run / Retry Discovery buttons errored. Fix: explicit `::platform` cast at the INSERT site.

> **Fixed 2026-04-25 (migration `20260425020000`):** RPC was creating the new run but never updating `creators.last_discovery_run_id`. The `<DiscoveryProgress>` UI polls the run pointed to by `last_discovery_run_id` — so after every retry it polled the *previous* failed run, saw its terminal status, and the new run's spinner stuck at "Queued 0%" forever. Fix: add `last_discovery_run_id = v_run_id` to the `UPDATE creators` clause.

---

## getDiscoveryProgress (server action — not an RPC)
**Called by:** `<DiscoveryProgress>` client component, every 3s while a card is in processing state.
**Args:** `runId` string
**Returns:** `Result<{ status, progressPct, progressLabel }>`
**Does:** Reads the row from `discovery_runs` via service-role client (RLS bypassed; runId is the lookup key). Surfaces three fields the UI needs to render the bar + label and decide whether to fire `router.refresh()`. Lives in `src/app/(dashboard)/creators/actions.ts` next to the other discovery actions; imported via `import { getDiscoveryProgress } from "@/app/(dashboard)/creators/actions"`.

---

## merge_creators
**Called by:** UI merge review panel — "Merge → keep this" button
**Args:** `p_keep_id` UUID, `p_merge_id` UUID, `p_resolver_id` UUID, `p_candidate_id` UUID
**Does:**
1. Migrates all profiles, funnel_edges, brand_analyses from merge_id → keep_id
2. Merges known_usernames[] and display_name_variants[] arrays (deduped)
3. Sets merged creator onboarding_status = 'archived'
4. Sets merge candidate status = 'merged'

---

## calculate_rank (internal)
**Called by:** GENERATED ALWAYS AS on profile_scores.current_rank
**Args:** `score` NUMERIC
**Returns:** rank_tier
**Thresholds:** ≥85=diamond, ≥70=platinum, ≥55=gold, ≥40=silver, ≥25=bronze, else plastic

---

## flag_outliers
**Called by:** Python ingestion pipeline after scraping
**Args:** `p_profile_id` UUID
**Does:**
- Computes `outlier_multiplier = view_count / median(last_50_posts_views)` for all posts in profile
- Window: last **50 posts** OR last **90 days**, whichever smaller
- Floor: minimum **15 posts** required before flagging activates
- Age guard: post must be ≥ **48 hours old** (view stabilization)
- Sets `is_outlier = true` and stores `outlier_multiplier` when multiplier ≥ **3.0**

---

## refresh_profile_score
**Called by:** Python analysis pipeline after content_analysis rows created
**Args:** `p_profile_id` UUID
**Does:** Computes AVG(quality_score) from content_analysis for this profile, upserts into profile_scores

---

## is_workspace_member (internal)
**Called by:** RLS policies on every table
**Args:** `ws_id` UUID
**Returns:** BOOLEAN
**Security:** DEFINER — runs with elevated privileges for RLS check

---

## normalize_handle (internal)
**Called by:** `commit_discovery_result` RPC for fuzzy collision detection
**Args:** `h` TEXT
**Returns:** TEXT
**Does:** Strips `@`, `.`, `-`, `_`, whitespace → lowercase. Used for rapidfuzz similarity scoring.

---

## set_updated_at (trigger function)
**Called by:** `trg_creators_updated_at`, `trg_profiles_updated_at` triggers
**Returns:** TRIGGER
**Does:** Sets `updated_at = NOW()` on any row update

---

## increment_label_usage (trigger function)
**Called by:** `trg_increment_label_usage` trigger on `content_label_assignments`
**Returns:** TRIGGER
**Does:** Increments `content_labels.usage_count` by 1 on every new label assignment insert
