# SCHEMA.md — Generated 2026-04-24T00:00:00Z
> Source: live DB (dbkddgwitqwzltuoxmfi). Regenerate via `npm run db:schema`.
>
> Surgically updated 2026-04-24 post-migrations `20260424000000_consolidate_last_discovery_run_id`, `20260424150000_create_edge_type_enum`, `20260424160000_fix_funnel_edges_creator_id`, and `20260424170000_phase_2_schema_migration` without re-running the script — the script needs `SUPABASE_DB_URL` in `scripts/.env`. Full regen pending.

## Tenant-Scoped Tables

Tables with a `workspace_id` column (row-level RLS isolates by workspace):

- `alerts_config`
- `alerts_feed`
- `content_labels`
- `creator_brand_analyses`
- `creator_merge_candidates`
- `creators`
- `discovery_runs`
- `funnel_edges`
- `profiles`
- `trend_signals`
- `trends`
- `workspace_members`

---

## Enums

- `account_type`: social | monetization | link_in_bio | messaging | other
- `content_archetype`: the_jester | the_caregiver | the_lover | the_everyman | the_creator | the_hero | the_sage | the_innocent | the_explorer | the_rebel | the_magician | the_ruler (creators.archetype)
- `content_category`: comedy_entertainment | fashion_style | fitness | lifestyle | beauty | travel | food | music | gaming | education | other
- `content_vibe`: playful | girl_next_door | body_worship | wifey | luxury | edgy | wholesome | mysterious | confident | aspirational (creators.vibe)
- `discovery_run_status`: pending | processing | completed | failed
- `edge_type`: link_in_bio | direct_link | cta_mention | qr_code | inferred (funnel_edges.edge_type)
- `label_type`: content_format | trend_pattern | hook_style | visual_style | creator_niche | other
- `llm_model`: gemini_pro | gemini_flash | claude_opus | claude_sonnet
- `merge_candidate_status`: pending | merged | dismissed
- `monetization_model`: subscription | tips | ppv | affiliate | brand_deals | ecommerce | coaching | saas | mixed | unknown
- `onboarding_status`: processing | ready | failed | archived
- `platform`: instagram | tiktok | youtube | patreon | twitter | linkedin | onlyfans | fanvue | fanplace | amazon_storefront | tiktok_shop | linktree | beacons | custom_domain | telegram_channel | telegram_cupidbot | facebook | other
- `post_type`: reel | tiktok_video | image | carousel | story | story_highlight | youtube_short | youtube_long | other
- `rank_tier`: diamond | platinum | gold | silver | bronze | plastic
- `signal_type`: velocity_spike | outlier_post | emerging_archetype | hook_pattern | cadence_change | new_monetization_detected
- `tracking_type`: managed | inspiration | competitor | candidate | hybrid_ai | coach | unreviewed
- `trend_type`: audio | dance | lipsync | transition | meme | challenge
- `workspace_role`: owner | admin | member

---

## Tables

### alerts_config

- **id**: uuid — PK DEF gen_random_uuid()
- **workspace_id**: uuid — FK→workspaces.id
- **name**: text — NN
- **rule_type**: text — NN
- **threshold_json**: jsonb — DEF '{}'::jsonb
- **target_profile_ids**: ARRAY — DEF '{}'::uuid[]
- **is_enabled**: boolean — DEF true
- **notify_emails**: ARRAY — DEF '{}'::text[]
- **created_by**: uuid

_RLS: Users view alerts config(SELECT)_

---

### alerts_feed

- **id**: uuid — PK DEF gen_random_uuid()
- **workspace_id**: uuid — FK→workspaces.id
- **config_id**: uuid — FK→alerts_config.id
- **content_id**: uuid — FK→scraped_content.id
- **profile_id**: uuid — FK→profiles.id
- **triggered_at**: timestamp with time zone — DEF now()
- **is_read**: boolean — DEF false
- **payload**: jsonb — DEF '{}'::jsonb

_RLS: Users view alerts feed(SELECT)_

---

### content_analysis

- **id**: uuid — PK DEF gen_random_uuid()
- **content_id**: uuid — FK→scraped_content.id
- **quality_score**: numeric
- **category**: content_category
- **visual_tags**: ARRAY — DEF '{}'::text[]
- **transcription**: text
- **hook_analysis**: text
- **is_clean**: boolean — DEF true
- **analysis_version**: text
- **gemini_raw_response**: jsonb — DEF '{}'::jsonb
- **model_version**: text
- **analyzed_at**: timestamp with time zone — DEF now()

_RLS: Users view content analysis(SELECT)_

---

### content_label_assignments

- **content_id**: uuid — PK FK→scraped_content.id
- **label_id**: uuid — PK FK→content_labels.id
- **assigned_by_ai**: boolean — DEF true
- **confidence**: numeric

_RLS: members insert label_assignments(INSERT), members select label_assignments(SELECT)_

---

### content_labels

- **id**: uuid — PK DEF gen_random_uuid()
- **workspace_id**: uuid — NN FK→workspaces.id
- **label_type**: label_type — NN
- **name**: text — NN
- **slug**: text — NN
- **description**: text
- **usage_count**: integer — DEF 0
- **is_canonical**: boolean — DEF false
- **merged_into_id**: uuid — FK→content_labels.id
- **created_by**: uuid
- **created_at**: timestamp with time zone — DEF now()

_RLS: members insert content_labels(INSERT), members select content_labels(SELECT), members update content_labels(UPDATE)_

---

### content_metrics_snapshots

PK: `(content_id, snapshot_date)`

- **content_id**: uuid — PK FK→scraped_content.id
- **snapshot_date**: date — PK DEF CURRENT_DATE
- **view_count**: bigint — DEF 0
- **like_count**: bigint — DEF 0
- **comment_count**: bigint — DEF 0
- **share_count**: bigint — DEF 0
- **save_count**: bigint — DEF 0
- **velocity**: numeric — DEF 0

_RLS: Users view content metrics(SELECT)_

---

### creator_brand_analyses

- **id**: uuid — PK DEF gen_random_uuid()
- **creator_id**: uuid — NN FK→creators.id
- **workspace_id**: uuid — NN FK→workspaces.id
- **version**: integer — NN DEF 1
- **niche_summary**: text
- **usp**: text
- **brand_keywords**: ARRAY — DEF '{}'::text[]
- **seo_keywords**: ARRAY — DEF '{}'::text[]
- **funnel_map**: jsonb — DEF '{}'::jsonb
- **monetization_summary**: text
- **platforms_included**: ARRAY — DEF '{}'::text[]
- **gemini_raw_response**: jsonb — DEF '{}'::jsonb
- **analyzed_at**: timestamp with time zone — DEF now()

_RLS: members insert brand_analyses(INSERT), members select brand_analyses(SELECT)_

---

### creator_merge_candidates

- **id**: uuid — PK DEF gen_random_uuid()
- **workspace_id**: uuid — NN FK→workspaces.id
- **creator_a_id**: uuid — NN FK→creators.id
- **creator_b_id**: uuid — NN FK→creators.id
- **confidence**: numeric — NN
- **evidence**: jsonb — NN DEF '[]'::jsonb
- **triggered_by_run_id**: uuid — FK→discovery_runs.id
- **status**: merge_candidate_status — DEF 'pending'::merge_candidate_status
- **resolved_by**: uuid
- **resolved_at**: timestamp with time zone
- **created_at**: timestamp with time zone — DEF now()

_RLS: members insert merge_candidates(INSERT), members select merge_candidates(SELECT), members update merge_candidates(UPDATE)_

---

### creators

- **id**: uuid — PK DEF gen_random_uuid()
- **workspace_id**: uuid — NN FK→workspaces.id
- **canonical_name**: text — NN
- **slug**: text — NN
- **known_usernames**: ARRAY — DEF '{}'::text[]
- **display_name_variants**: ARRAY — DEF '{}'::text[]
- **primary_niche**: text
- **primary_platform**: platform
- **monetization_model**: monetization_model — DEF 'unknown'::monetization_model
- **tracking_type**: tracking_type — DEF 'unreviewed'::tracking_type
- **tags**: ARRAY — DEF '{}'::text[]
- **notes**: text
- **onboarding_status**: onboarding_status — DEF 'processing'::onboarding_status
- **import_source**: text — DEF 'bulk'::text
- **last_discovery_run_id**: uuid — FK→discovery_runs.id
- **last_discovery_error**: text
- **archetype**: content_archetype _(filled by Phase 3 brand analysis)_
- **vibe**: content_vibe _(filled by Phase 3 brand analysis)_
- **added_by**: uuid
- **created_at**: timestamp with time zone — DEF now()
- **updated_at**: timestamp with time zone — DEF now()

_RLS: members insert creators(INSERT), members select creators(SELECT), members update creators(UPDATE)_

---

### creator_label_assignments

- **creator_id**: uuid — PK FK→creators.id (CASCADE)
- **label_id**: uuid — PK FK→content_labels.id (CASCADE)
- **assigned_by_ai**: boolean — DEF false
- **confidence**: numeric(3,2)
- **created_at**: timestamp with time zone — DEF now()

_RLS: workspace access inherited from creators via join_
_Trigger: increment_label_usage (bumps content_labels.usage_count on INSERT)_

---

### discovery_runs

- **id**: uuid — PK DEF gen_random_uuid()
- **workspace_id**: uuid — NN FK→workspaces.id
- **creator_id**: uuid — NN FK→creators.id
- **input_handle**: text
- **input_url**: text
- **input_platform_hint**: platform
- **input_screenshot_path**: text
- **status**: discovery_run_status — DEF 'pending'::discovery_run_status
- **raw_gemini_response**: jsonb
- **assets_discovered_count**: integer — DEF 0
- **funnel_edges_discovered_count**: integer — DEF 0
- **merge_candidates_raised**: integer — DEF 0
- **initiated_by**: uuid
- **started_at**: timestamp with time zone
- **completed_at**: timestamp with time zone
- **error_message**: text
- **attempt_number**: integer — DEF 1
- **created_at**: timestamp with time zone — DEF now()

_RLS: members insert discovery_runs(INSERT), members select discovery_runs(SELECT), members update discovery_runs(UPDATE)_

---

### funnel_edges

- **id**: uuid — PK DEF gen_random_uuid()
- **creator_id**: uuid — NN FK→creators.id
- **workspace_id**: uuid — NN FK→workspaces.id
- **from_profile_id**: uuid — NN FK→profiles.id
- **to_profile_id**: uuid — NN FK→profiles.id
- **edge_type**: edge_type — DEF 'inferred'::edge_type
- **confidence**: numeric — DEF 1.0
- **detected_at**: timestamp with time zone — DEF now()

_RLS: members insert funnel_edges(INSERT), members select funnel_edges(SELECT)_

---

### profile_metrics_snapshots

PK: `(profile_id, snapshot_date)`

- **profile_id**: uuid — PK FK→profiles.id
- **snapshot_date**: date — PK DEF CURRENT_DATE
- **follower_count**: bigint — DEF 0
- **median_views**: numeric — DEF 0
- **avg_engagement_rate**: numeric — DEF 0
- **outlier_count**: integer — DEF 0
- **quality_score**: numeric — DEF 0

_RLS: Users view profile metrics(SELECT)_

---

### profile_scores

- **profile_id**: uuid — PK FK→profiles.id
- **current_score**: numeric — DEF 0
- **current_rank**: rank_tier _(generated by calculate_rank(current_score))_
- **scored_content_count**: integer — DEF 0
- **last_computed_at**: timestamp with time zone — DEF now()

_RLS: Users view profile scores(SELECT)_

---

### profiles

- **id**: uuid — PK DEF gen_random_uuid()
- **workspace_id**: uuid — FK→workspaces.id
- **platform**: platform — NN
- **handle**: text — NN
- **display_name**: text
- **profile_url**: text
- **avatar_url**: text
- **bio**: text
- **follower_count**: bigint — DEF 0
- **following_count**: bigint — DEF 0
- **post_count**: bigint — DEF 0
- **tracking_type**: tracking_type — DEF 'unreviewed'::tracking_type
- **tags**: ARRAY — DEF '{}'::text[]
- **is_clean**: boolean — DEF true
- **analysis_version**: text — DEF 'v1'::text
- **last_scraped_at**: timestamp with time zone
- **added_by**: uuid
- **is_active**: boolean — DEF true
- **created_at**: timestamp with time zone — DEF now()
- **creator_id**: uuid — FK→creators.id
- **account_type**: account_type — DEF 'social'::account_type
- **url**: text
- **discovery_confidence**: numeric
- **updated_at**: timestamp with time zone — DEF now()
- **is_primary**: boolean — NN DEF false

_RLS: Users insert profiles to their workspace(INSERT), Users update profiles in their workspace(UPDATE), Users view profiles in their workspace(SELECT)_

---

### scraped_content

- **id**: uuid — PK DEF gen_random_uuid()
- **profile_id**: uuid — FK→profiles.id
- **platform**: platform — NN
- **platform_post_id**: text — NN
- **post_url**: text
- **post_type**: post_type — NN
- **caption**: text
- **hook_text**: text
- **posted_at**: timestamp with time zone
- **view_count**: bigint — DEF 0
- **like_count**: bigint — DEF 0
- **comment_count**: bigint — DEF 0
- **share_count**: bigint — DEF 0
- **save_count**: bigint — DEF 0
- **engagement_rate**: numeric _(generated column)_
- **platform_metrics**: jsonb — DEF '{}'::jsonb
- **media_urls**: ARRAY — DEF '{}'::text[]
- **thumbnail_url**: text
- **is_outlier**: boolean — DEF false
- **raw_apify_payload**: jsonb — DEF '{}'::jsonb
- **created_at**: timestamp with time zone — DEF now()
- **updated_at**: timestamp with time zone — DEF now()
- **outlier_multiplier**: numeric
- **trend_id**: uuid — FK→trends.id (SET NULL on delete)

_RLS: Users view content from profiles in their workspace(SELECT)_

---

### trends

- **id**: uuid — PK DEF gen_random_uuid()
- **workspace_id**: uuid — NN FK→workspaces.id (CASCADE)
- **name**: text — NN
- **trend_type**: trend_type — NN
- **audio_signature**: text
- **audio_artist**: text
- **audio_title**: text
- **description**: text
- **usage_count**: integer — NN DEF 0
- **is_canonical**: boolean — NN DEF true
- **peak_detected_at**: timestamp with time zone
- **created_at**: timestamp with time zone — NN DEF now()
- **updated_at**: timestamp with time zone — NN DEF now()

_UNIQUE (workspace_id, audio_signature) WHERE audio_signature IS NOT NULL_
_RLS: workspace member SELECT + ALL policies_
_Trigger: set_updated_at BEFORE UPDATE_

---

### trend_signals

- **id**: uuid — PK DEF gen_random_uuid()
- **workspace_id**: uuid — FK→workspaces.id
- **signal_type**: signal_type — NN
- **profile_id**: uuid — FK→profiles.id
- **content_id**: uuid — FK→scraped_content.id
- **score**: numeric
- **detected_at**: timestamp with time zone — DEF now()
- **metadata**: jsonb — DEF '{}'::jsonb
- **is_dismissed**: boolean — DEF false

_RLS: Users view trend signals(SELECT)_

---

### workspace_members

PK: `(workspace_id, user_id)`

- **workspace_id**: uuid — PK FK→workspaces.id
- **user_id**: uuid — PK
- **role**: workspace_role — NN DEF 'member'::workspace_role
- **joined_at**: timestamp with time zone — DEF now()

_RLS: Users view workspace members(SELECT)_

---

### workspaces

- **id**: uuid — PK DEF gen_random_uuid()
- **name**: text — NN
- **slug**: text — NN
- **created_at**: timestamp with time zone — DEF now()
- **owner_id**: uuid — NN

_RLS: Users view workspaces they belong to(SELECT)_

---

## Column Disambiguation

_Column names appearing in 2 or more tables:_

- **added_by** — `creators`, `profiles`
- **analysis_version** — `content_analysis`, `profiles`
- **confidence** — `content_label_assignments`, `creator_merge_candidates`, `funnel_edges`
- **content_id** — `alerts_feed`, `content_analysis`, `content_label_assignments`, `content_metrics_snapshots`, `trend_signals`
- **created_at** — `content_labels`, `creator_merge_candidates`, `creators`, `discovery_runs`, `profiles`, `scraped_content`, `workspaces`
- **creator_id** — `creator_brand_analyses`, `creator_merge_candidates`, `discovery_runs`, `funnel_edges`, `profiles`, `trend_signals`
- **detected_at** — `funnel_edges`, `trend_signals`
- **id** — `alerts_config`, `alerts_feed`, `content_analysis`, `content_labels`, `creator_brand_analyses`, `creator_merge_candidates`, `creators`, `discovery_runs`, `funnel_edges`, `profiles`, `scraped_content`, `trend_signals`, `workspaces`
- **is_clean** — `content_analysis`, `profiles`
- **name** — `alerts_config`, `content_labels`, `workspaces`
- **platform** — `profiles`, `scraped_content`
- **profile_id** — `alerts_feed`, `profile_metrics_snapshots`, `profile_scores`, `scraped_content`, `trend_signals`
- **slug** — `content_labels`, `creators`, `workspaces`
- **snapshot_date** — `content_metrics_snapshots`, `profile_metrics_snapshots`
- **status** — `creator_merge_candidates`, `discovery_runs`
- **tags** — `creators`, `profiles`
- **tracking_type** — `creators`, `profiles`
- **updated_at** — `creators`, `profiles`, `scraped_content`
- **workspace_id** — `alerts_config`, `alerts_feed`, `content_labels`, `creator_brand_analyses`, `creator_merge_candidates`, `creators`, `discovery_runs`, `funnel_edges`, `profiles`, `trend_signals`, `workspace_members`

---

## Live vs PROJECT_STATE Drift Notes

All drift resolved as of 2026-04-24.

- `creators.last_discovery_run_id` consolidated via migration `20260424000000_consolidate_last_discovery_run_id`.
- `trend_signals.profile_id`, `alerts_feed.profile_id+content_id`, and `discovery_runs` extra cols (`input_screenshot_path`, `funnel_edges_discovered_count`, `merge_candidates_raised`, `started_at`, `completed_at`) all reflected in PROJECT_STATE.md §4.
- `content_analysis.archetype` is intentionally still `text` — Phase 2 migration drops the column entirely (moves to `creators` table). No schema change needed here.
