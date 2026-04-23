# RPC Reference

All callable via: `supabase.rpc('function_name', { args })`

---

## commit_discovery_result
**Called by:** Python discovery pipeline on successful Gemini response
**Args:**
- `p_run_id` UUID
- `p_creator_data` JSONB — `{canonical_name, known_usernames[], display_name_variants[], primary_platform, primary_niche, monetization_model}`
- `p_accounts` JSONB — array of `{account_type, platform, handle, url, display_name, bio, follower_count, is_primary, discovery_confidence}`
- `p_funnel_edges` JSONB — array of `{from_handle, from_platform, to_handle, to_platform, edge_type, confidence}`

**Returns:** `{creator_id, accounts_upserted, merge_candidates_raised}`

**Does (transactional):**
1. Enriches creator row with discovered data
2. For each account: checks for handle collision with different creator → raises merge candidate if found, otherwise upserts profile row
3. Inserts funnel edges (resolves handle → profile_id)
4. Marks discovery_run completed
5. Sets creator.onboarding_status = 'ready'

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
**Does:** Creates new discovery_runs row (increments attempt_number), **copies `input_handle` and `input_platform_hint` from most recent prior run** (so the worker knows what handle to discover), resets creator to onboarding_status = processing

> **Fixed 2026-04-23:** Previous version did not copy `input_handle` into the new row. Retry runs had NULL handle and immediately failed at the worker's fetch step.

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
