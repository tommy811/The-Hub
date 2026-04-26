# PROJECT_STATE.md

**The Hub — Creator Intelligence Platform**
Last synced: 2026-04-26 (sync 15 — universal URL harvester ships, sensitive-content gates resolved)

> This file is the master technical reference. Every AI Studio session starts by pasting this. Claude Code reads this first on every session. Repo and Obsidian vault share one folder — this file is directly visible in both.

---

## 1. What The Hub Is

Internal tool for a 2–5 person creator management agency. **Not a SaaS.** The Creator is the source-of-truth entity; every other entity (accounts, content, analyses, funnel edges, trends) links back to a creator.

Daily job: discover creators → scrape their content across platforms → AI-score and label → surface outliers and winning patterns → feed insights into agency workflows.

---

## 2. Tech Stack

- **Frontend:** Next.js 16.2.4 (App Router, Server Components where possible), TypeScript strict, Tailwind, shadcn/ui, Playwright browser smoke tests, Recharts, lucide-react, framer-motion, @xyflow/react
- **Backend:** Supabase (Postgres 17, Auth, RLS, Realtime, Storage, Edge Functions)
- **Pipeline:** Python 3.11+, `supabase-py`, `apify-client`, `google-generativeai`, `anthropic`, `pydantic v2`, `tenacity`, `rapidfuzz`, `httpx`, `beautifulsoup4`
- **Supabase project:** Content OS (`dbkddgwitqwzltuoxmfi`, us-east-1)
- **Aesthetic:** Dark mode default. Background `#0A0A0F`, card surface `#13131A`, border `white/[0.06]`, indigo/violet accent

---

## 3. Architectural Principles

1. **Creator-centric relational model.** `creators` is the root. No platform-first tables.
2. **One unified `profiles` table** for all asset types (social / monetization / link_in_bio / messaging), distinguished by `account_type` enum.
3. **Workspace isolation via RLS.** Every row has `workspace_id`. `is_workspace_member()` policy on every table.
4. **Upsert, never duplicate.** Natural unique keys on external-facing rows. `ON CONFLICT ... DO UPDATE` on all writes.
5. **Insert-first, enrich-later.** Bulk import inserts placeholders immediately (`onboarding_status='processing'`) so the UI shows cards at once. Pipeline enriches async.
6. **Time-series snapshots.** `content_metrics_snapshots` and `profile_metrics_snapshots` preserve daily history for trend detection.
7. **Dual taxonomy.** Fixed enums for fast-filterable dimensions (rank, vibe at creator level, category); dynamic `content_labels` for long-tail vocabulary (formats, trends, hook styles, visual styles, creator niches).
8. **Identity resolution at the DB layer.** Handle collisions surfaced via `creator_merge_candidates` inside `commit_discovery_result` RPC. Humans review in UI.
9. **Typed end-to-end.** Pydantic v2 on Python, `supabase gen types typescript` on Next.js.
10. **Rank is computed, never stored.** `calculate_rank(score)` function is the sole source.

---

## 4. Complete Schema (Live + Pending)

### 4.1 Currently live in Supabase (24 tables)

**Tenancy**
- `workspaces` — id, name, slug, owner_id, created_at
- `workspace_members` — workspace_id, user_id, role (`workspace_role`), joined_at

**Creator layer (root)**
- `creators` — id, workspace_id, canonical_name, slug, known_usernames[], display_name_variants[], primary_niche, primary_platform, monetization_model, tracking_type, tags[], notes, onboarding_status, import_source, last_discovery_run_id (FK→discovery_runs), last_discovery_error, archetype (content_archetype nullable), vibe (content_vibe nullable), added_by, timestamps
- `creator_accounts` alias = `profiles` (same table)
- `profiles` — id, workspace_id, creator_id (FK nullable for legacy), platform, handle, display_name, profile_url, url, avatar_url, bio, follower_count, following_count, post_count, tracking_type, tags[], is_clean, analysis_version, last_scraped_at, added_by, is_active, account_type, discovery_confidence, is_primary (bool, default false), timestamps
- `discovery_runs` — id, workspace_id, creator_id, input_handle, input_url, input_platform_hint, input_screenshot_path, status, raw_gemini_response, assets_discovered_count, funnel_edges_discovered_count, merge_candidates_raised, attempt_number, error_message, initiated_by, started_at, completed_at, **progress_pct (smallint NOT NULL DEFAULT 0)**, **progress_label (text)**, timestamps
- `creator_merge_candidates` — id, workspace_id, creator_a_id, creator_b_id (a<b enforced), confidence, evidence (jsonb), triggered_by_run_id, status, resolved_by, timestamps
- `funnel_edges` — id, creator_id, workspace_id, from_profile_id, to_profile_id, edge_type, confidence, detected_at
- `creator_brand_analyses` — id, creator_id, workspace_id, version, niche_summary, usp, brand_keywords[], seo_keywords[], funnel_map (jsonb), monetization_summary, platforms_included[], gemini_raw_response, analyzed_at

**Content layer**
- `scraped_content` — id, profile_id, platform, platform_post_id (unique per platform), post_url, post_type, caption, hook_text, posted_at, view_count, like_count, comment_count, share_count, save_count, engagement_rate (generated), platform_metrics (jsonb), media_urls[], thumbnail_url, is_outlier, outlier_multiplier, raw_apify_payload (jsonb), trend_id (FK→trends nullable), timestamps
- `content_analysis` — id, content_id (unique), quality_score, category, visual_tags[], transcription, hook_analysis, is_clean, analysis_version, gemini_raw_response, model_version, analyzed_at
- `content_metrics_snapshots` — content_id, snapshot_date, view_count, like_count, comment_count, share_count, save_count, velocity, PK (content_id, snapshot_date)
- `profile_metrics_snapshots` — profile_id, snapshot_date, follower_count, median_views, avg_engagement_rate, outlier_count, quality_score, PK (profile_id, snapshot_date)
- `profile_scores` — profile_id (unique), current_score, current_rank (generated from `calculate_rank`), scored_content_count, last_computed_at

**Labels & taxonomy**
- `content_labels` — id, workspace_id, label_type (`content_format|trend_pattern|hook_style|visual_style|creator_niche|other`), name, slug, description, usage_count, is_canonical, merged_into_id (self FK), created_by, created_at
- `content_label_assignments` — content_id, label_id, assigned_by_ai, confidence, PK (content_id, label_id)
- `creator_label_assignments` — creator_id, label_id, assigned_by_ai, confidence, created_at, PK (creator_id, label_id). Trigger: `increment_label_usage`.

**Trends**
- `trends` — id, workspace_id, name, trend_type (`audio|dance|lipsync|transition|meme|challenge`), audio_signature, audio_artist, audio_title, description, usage_count, is_canonical, peak_detected_at, timestamps. UNIQUE (workspace_id, audio_signature) WHERE audio_signature IS NOT NULL. Referenced by `scraped_content.trend_id`.

**Signals & alerts**
- `trend_signals` — id, workspace_id, signal_type, profile_id (FK→profiles), content_id (FK→scraped_content), score, detected_at, metadata (jsonb), is_dismissed
- `alerts_config` — id, workspace_id, name, rule_type, threshold_json, target_profile_ids[], is_enabled, notify_emails[], created_by
- `alerts_feed` — id, workspace_id, config_id, content_id (FK→scraped_content), profile_id (FK→profiles), triggered_at, is_read, payload (jsonb)

**Discovery v2 (applied 2026-04-25)**
- `bulk_imports` — id, workspace_id, initiated_by, seeds_total, seeds_committed, seeds_failed, seeds_blocked_by_budget, merge_pass_completed_at, cost_apify_cents, status (`running|completed|completed_with_failures|partial_budget_exceeded|cancelled`), timestamps. First-class observable bulk-import job. RLS: `is_workspace_member`. `set_updated_at` trigger.
- `classifier_llm_guesses` — canonical_url (PK), platform_guess, account_type_guess, confidence (0-1), model_version, classified_at. Workspace-agnostic cache of LLM-classified URLs. No RLS — service role writes, reads are keyed on URL only.
- `profile_destination_links` — profile_id (FK→profiles), canonical_url, destination_class (TEXT with CHECK constraint, 10 allowed values: `monetization|aggregator|social|commerce|messaging|content|affiliate|professional|other|unknown`), workspace_id, created_at, **harvest_method (text — `cache|httpx|headless`)**, **raw_text (text — anchor text captured at harvest time)**, **harvested_at (timestamptz default NOW())**. PK (profile_id, canonical_url). Persistent reverse index driving cross-workspace identity dedup. RLS: `is_workspace_member`. The 3 audit columns + extended CHECK constraint were added 2026-04-26 by the Universal URL Harvester migrations.

**New columns (Discovery v2):**
- `discovery_runs.bulk_import_id` (FK→bulk_imports, nullable, ON DELETE SET NULL), `discovery_runs.apify_cost_cents` (int default 0), `discovery_runs.source` (text, `seed|manual_add|retry|auto_expand`, default 'seed')
- `discovery_runs.progress_pct` (smallint NOT NULL DEFAULT 0) + `discovery_runs.progress_label` (text) — added 2026-04-25 (migration `20260425010000`); written by the Python pipeline at each stage so the UI's `<DiscoveryProgress>` component can render a live progress bar.
- `profiles.discovery_reason` (text, audit trail for `rule:{name}` / `llm:{kind}` / `manual_add` / `discovered_only_no_fetcher:{reason}`)

**New constraint:** unique index `creator_merge_candidates_pair_uniq` on `(LEAST(a,b), GREATEST(a,b))` for idempotent merge-candidate inserts.

**Universal URL Harvester (applied 2026-04-26)**
- `url_harvest_cache` — canonical_url (PK), harvest_method (`httpx|headless`), destinations (jsonb — `[{canonical_url, raw_url, raw_text, destination_class}, ...]`), harvested_at, expires_at, created_at. Workspace-agnostic cache (mirrors `classifier_llm_guesses` pattern). 24h TTL by default. Service role only — no RLS. Indexed on `expires_at` for TTL-aware lookups.
- The CHECK constraint on `profile_destination_links.destination_class` was extended from 4 → 10 values (migration `20260426020000`) so rows tagged `messaging` (Telegram / WhatsApp / Discord), `commerce` (Shopify / Etsy / Depop), `content` (Substack / Spotify / Apple Podcasts), `affiliate` (amzn.to / geni.us / shareasale), `professional` (LinkedIn / Calendly), and `unknown` no longer crash on insert. Note: this is a TEXT-with-CHECK pattern, not a Postgres ENUM — easier to extend forward-compat without `ALTER TYPE` ceremony.

### 4.2 Phase 2 migration — applied (migration `20260424170000_phase_2_schema_migration`)

All items previously listed as "pending" are now live and reflected in §4.1:

- ✅ `trends` table + `trend_type` enum (6 values)
- ✅ `creator_label_assignments` table (mirrors `content_label_assignments`, reuses `increment_label_usage` trigger)
- ✅ `label_type` enum extended with `creator_niche`
- ✅ `llm_model` enum (4 values: gemini_pro, gemini_flash, claude_opus, claude_sonnet) — reserved for analysis pipelines
- ✅ `content_archetype` enum (12 Jungian values, was documented but missing from DB — audit gap closed)
- ✅ `creators.archetype` (nullable `content_archetype`) and `creators.vibe` (nullable `content_vibe`) added; filled by Phase 3 brand analysis
- ✅ `scraped_content.trend_id` (nullable FK→trends, ON DELETE SET NULL)
- ✅ `content_analysis.archetype` and `content_analysis.vibe` dropped (table was empty, no data loss)

**Rationale (preserved for future reference):** archetype and vibe describe the creator's overall brand identity, not individual posts. A single post carrying the "goth" vibe doesn't tell you much; across a creator's full body of work, it defines the brand. Content-level taxonomy stays with `category`, dynamic labels, and visual tags.

---

## 5. All Enums

| Enum | Values |
|---|---|
| `platform` | instagram, tiktok, youtube, patreon, twitter, linkedin, facebook, onlyfans, fanvue, fanplace, amazon_storefront, tiktok_shop, linktree, beacons, custom_domain, telegram_channel, telegram_cupidbot, other |
| `account_type` | social, monetization, link_in_bio, messaging, other |
| `tracking_type` | managed, inspiration, competitor, candidate, hybrid_ai, coach, unreviewed |
| `rank_tier` | diamond, platinum, gold, silver, bronze, plastic |
| `onboarding_status` | processing, ready, failed, archived |
| `monetization_model` | subscription, tips, ppv, affiliate, brand_deals, ecommerce, coaching, saas, mixed, unknown |
| `discovery_run_status` | pending, processing, completed, failed |
| `merge_candidate_status` | pending, merged, dismissed |
| `post_type` | reel, tiktok_video, image, carousel, story, story_highlight, youtube_short, youtube_long, other |
| `content_archetype` (Jungian 12) | the_jester, the_caregiver, the_lover, the_everyman, the_creator, the_hero, the_sage, the_innocent, the_explorer, the_rebel, the_magician, the_ruler |
| `content_vibe` | playful, girl_next_door, body_worship, wifey, luxury, edgy, wholesome, mysterious, confident, aspirational |
| `content_category` | comedy_entertainment, fashion_style, fitness, lifestyle, beauty, travel, food, music, gaming, education, other |
| `signal_type` | velocity_spike, outlier_post, emerging_archetype, hook_pattern, cadence_change, new_monetization_detected |
| `label_type` | content_format, trend_pattern, hook_style, visual_style, creator_niche, other |
| `trend_type` | audio, dance, lipsync, transition, meme, challenge |
| `llm_model` | gemini_pro, gemini_flash, claude_opus, claude_sonnet |
| `edge_type` | link_in_bio, direct_link, cta_mention, qr_code, inferred |
| `workspace_role` | owner, admin, member |

---

## 6. All RPCs

| Function | Signature | Purpose |
|---|---|---|
| `calculate_rank` | (score numeric) → rank_tier | Pure function: ≥85 diamond, ≥70 platinum, ≥55 gold, ≥40 silver, ≥25 bronze, else plastic |
| `flag_outliers` | (p_profile_id uuid) → void | Sets `is_outlier=true` on posts where view_count > 3× median of last 50 posts (or last 90 days, whichever smaller). Minimum 15 posts required. |
| `refresh_profile_score` | (p_profile_id uuid) → void | Recomputes avg `quality_score` from `content_analysis`, upserts `profile_scores` |
| `is_workspace_member` | (ws_id uuid) → boolean | RLS helper — used on every policy. SECURITY DEFINER. |
| `normalize_handle` | (h text) → text | Strips `@`, `.`, `-`, `_`, whitespace → lowercase. Used for fuzzy matching. |
| `set_updated_at` | () → trigger | Trigger body: sets `updated_at = NOW()` |
| `increment_label_usage` | () → trigger | Trigger: `content_labels.usage_count++` on assignment insert |
| `commit_discovery_result` | (p_run_id, p_creator_data jsonb, p_accounts jsonb, p_funnel_edges jsonb, p_discovered_urls jsonb DEFAULT '[]', p_bulk_import_id uuid DEFAULT NULL) → jsonb | Transactional v4 (2026-04-26): enriches creator (source-aware — `manual_add` only union-merges known_usernames), upserts profiles, inserts funnel edges, writes `profile_destination_links` **including the harvest_method + raw_text audit fields (v3)**, **and ON CONFLICT updates destination_class so post-fix re-runs refresh stale rows (v4)**, bumps `bulk_imports.seeds_committed`, marks run completed. Returns `{creator_id, accounts_upserted, merge_candidates_raised, urls_recorded}` |
| `bulk_import_creator` | (p_handle, p_platform_hint, p_tracking_type, p_tags, p_user_id, p_workspace_id, p_bulk_import_id uuid DEFAULT NULL) → jsonb | Creates creator + primary profile + pending discovery_run; when p_bulk_import_id is NULL, creates a new `bulk_imports` row. Returns `{bulk_import_id, creator_id, run_id}`. **Patched 2026-04-25 (migration `20260425030000`)** — added `::platform` cast to `p_platform_hint` in the `discovery_runs` INSERT (the `creators` and `profiles` INSERTs already cast). Without the cast every Bulk Paste / Single Handle import errored with Postgres `22P02`. |
| `run_cross_workspace_merge_pass` | (p_workspace_id uuid, p_bulk_import_id uuid DEFAULT NULL) → jsonb | Reads `profile_destination_links` inverted index; raises auto-merge candidates for any URL with destination_class in (monetization, aggregator) shared across >1 creator. Sets `bulk_imports.merge_pass_completed_at` + final status when p_bulk_import_id provided. Idempotent via unique pair index |
| `mark_discovery_failed` | (p_run_id, p_error text) → void | Sets run.status=failed, creator.onboarding_status=failed |
| `retry_creator_discovery` | (p_creator_id, p_user_id) → uuid | Creates new `discovery_runs` (attempt_number+1), copies `input_handle` + `input_platform_hint` from most recent prior run, **updates `creators.last_discovery_run_id`** to the new run id (migration `20260425020000`), returns new run_id. Without that update, the UI's DiscoveryProgress polled the previous failed run forever and the new run's spinner stuck at "Queued 0%". |
| `merge_creators` | (p_keep_id, p_merge_id, p_resolver_id, p_candidate_id) → void | Migrates profiles/edges/analyses merge→keep, merges known_usernames[], archives merged creator |

---

## 7. Routes — Wiring Status

| Route | File | Status |
|---|---|---|
| `/` | `(dashboard)/page.tsx` | ✅ Live — Command Center with live stats from Supabase |
| `/creators` | `(dashboard)/creators/page.tsx` | ✅ Live — real queries, bulk import works |
| `/creators/[slug]` | `(dashboard)/creators/[slug]/page.tsx` | 🟡 Partial — Brand HQ surface: stats strip, AvatarWithFallback, network sections with brand icons, Add Account + Re-run Discovery in header, **DiscoveryProgress live bar** during in-flight runs, **All Destinations section grouped by destination_class (2026-04-26) — renders every `profile_destination_links` row with a `gated` chip on headless-harvested rows**. Bio + platform identity stripped from header (account-level data lives only in the network rows). Content/Branding/Funnel tabs are coming-soon stubs. |
| `/content` | `(dashboard)/content/page.tsx` | ⬜ Placeholder |
| `/trends` | `(dashboard)/trends/page.tsx` | ⬜ Mock — UI built, no live data |
| `/admin` | `(dashboard)/admin/page.tsx` | ⬜ Placeholder |
| `/platforms/instagram/accounts` | `platforms/instagram/accounts/page.tsx` + `InstagramAccountsClient.tsx` | ✅ Live — real `profiles` query, stat cards, tracking tab URL filter, rank chip client filter, empty state, Unlinked badge |
| `/platforms/instagram/outliers` | — | ⬜ Placeholder |
| `/platforms/instagram/classification` | — | ⬜ Placeholder |
| `/platforms/instagram/analytics` | — | ⬜ Placeholder |
| `/platforms/tiktok/accounts` | `platforms/tiktok/accounts/page.tsx` + `TikTokAccountsClient.tsx` | ✅ Live — real `profiles` query, stat cards, tracking tab URL filter, rank chip client filter, empty state, Unlinked badge |

**Known cleanup:** Sidebar previously had duplicate tracking-type entries (Managed/Candidates/Competitors/Inspiration) that duplicated the in-page chip filter row — removed 2026-04-25 (commit `c75903d`); the in-page chip row is now the single source of filter truth. TikTok Intel section is header-only → add child routes matching Instagram. `/admin` needs scope definition.

---

## 8. LLM Routing

| Function | Model | Rationale |
|---|---|---|
| Creator discovery (fishnet + funnel) | Gemini 2.5 Flash | Long context, cheap, structured JSON from messy web data |
| Content visual analysis (video/image) | Gemini 2.5 Flash | Native multimodal — analyzes frames directly |
| Brand analysis / SEO report | Claude Sonnet | Better at nuanced synthesis and report writing |
| Quick classification (fixed enum output) | Gemini Flash | Cheap, fast, sufficient for constrained outputs |
| Hook / narrative pattern analysis | Claude Sonnet | Stronger narrative reasoning |
| Multi-step agent workflows (Phase 3+) | Claude Opus or Sonnet | Best tool use + reasoning chains |

**Principle:** Gemini for vision and multimodal. Claude for writing and reasoning. All model selection is stored per-analysis-row (`model_version` column) so we can A/B test later.

---

## 9. Outlier Detection Logic

**Formula:** `outlier_multiplier = current_views / median(last_N_posts_views)`

**Parameters:**
- N = last **50 posts** OR last **90 days**, whichever is smaller
- Minimum floor: **15 posts** scraped before flagging activates
- Post must be ≥ **48 hours old** (view stabilization)
- Flag `is_outlier = true` when multiplier ≥ **3.0**

**Scoring:**
- < 1.0 — underperformer
- 1.0–2.0 — healthy baseline
- 3.0+ — clear outlier (flagged)
- 10.0+ — viral breakout

**Why median over mean:** previous viral hits don't poison the baseline for new detection.
**Why not view-to-follower ratio:** creators with low follower counts (200) can still have millions of views (boosted/trending content) — ratio breaks down for new or recently-discovered creators.

---

## 10. Identity Resolution

Detection happens inside `commit_discovery_result` RPC before any upsert.

| Confidence | Action |
|---|---|
| 1.0 | Auto-merge (direct link chain proves identity) |
| 0.7–0.99 | Raise `creator_merge_candidates` row, surface in UI |
| < 0.7 | Log and discard |

**Evidence signals** (stored in `creator_merge_candidates.evidence` jsonb):
- `handle_collision` — exact handle exists under different creator
- `handle_similarity` — rapidfuzz ratio > 0.85 on normalized handles
- `shared_linktree` — same destination URL found on both
- `display_name_match` — normalized display names match

`known_usernames[]` accumulates all aliases permanently, even post-merge.

---

## 11. Environment Variables

**Next.js (`.env.local`):**
```
NEXT_PUBLIC_SUPABASE_URL=
NEXT_PUBLIC_SUPABASE_ANON_KEY=
```

**Python (`scripts/.env`):**
```
SUPABASE_URL=
SUPABASE_SERVICE_ROLE_KEY=
GEMINI_API_KEY=
ANTHROPIC_API_KEY=
APIFY_TOKEN=
POLL_INTERVAL_SECONDS=30
MAX_CONCURRENT_RUNS=5
```

---

## 12. Naming Conventions

- Tables: `snake_case_plural`
- Columns: `snake_case`
- Enum values: `snake_case`
- Next.js components: `PascalCase.tsx`
- Utility files: `camelCase.ts`
- Routes: `kebab-case`
- Python modules: `snake_case.py`
- Migrations: `YYYYMMDDHHMMSS_description.sql`

---

## 13. Development Workflow

**Who updates `PROJECT_STATE.md`:**
- Claude Code automatically updates this file on any architectural change (new table, new RPC, new route, new enum, removed column).
- When the user says "update project state," Claude Code does a full sync: updates `PROJECT_STATE.md` (repo root = Obsidian vault, same file), updates any affected reference doc (`Enum Reference.md`, `RPC Reference.md`, `Migration Log.md`), commits with message `docs: sync project state`, pushes.

**Session notes:** one file per calendar day in Obsidian `06-Sessions/YYYY-MM-DD.md`. Multiple working sessions in the same day append to that day's file.

**Agent development cadence:** Each phase's required agents are built alongside feature work, not deferred. A phase closes only when its agents are live and validated. Agent specs live in `.claude/agents/[agent-name].md`. See §15–§19 Agent Architecture.

**Every new AI Studio session:** paste this file at the top of the prompt.

**Every new Claude Code session:** "Read PROJECT_STATE.md first."

---

## 14. Build Order (Current)

1. ✅ **Phase 1 complete:** Schema, Creators hub, discovery pipeline, bulk import, merge candidates, live card grid with Realtime
2. ✅ **Phase 1 UX hardening:** Re-run Discovery wired end-to-end, Manual Add Account dialog functional, Creator detail page revamped (stats strip, bio, avatar fallback, network sections), Apify field mapping fixed (follower counts backfilled)
3. ✅ **Phase 1 agents:** `verify-and-fix` skill built — Phase 1 fully closed
4. ✅ **Vault merged into repo:** single folder, single source of truth, all docs committed to git
5. 🔄 **Wire existing stub routes** to live Supabase data: ✅ `/platforms/instagram/accounts`, ✅ `/platforms/tiktok/accounts` — 🔜 `/content`, `/trends` remaining
6. ✅ **Phase 2 discovery rebuild:** `fetch_input_context` rewritten on top of Apify (`apify/instagram-scraper` details mode for IG, `clockworks/tiktok-scraper` for TT), Linktree/Beacons resolver live, Gemini prompt grounded in provided context, `edge_type` enum + `commit_discovery_result` funnel_edges fix live, 45 pytest tests covering the pipeline. Smoke-tested end-to-end with 3 live creators.
7. ✅ **Phase 2 schema migration:** `trends` + `creator_label_assignments` tables; `trend_type` + `llm_model` + `content_archetype` enums; `creator_niche` added to `label_type`; `archetype`+`vibe` moved from `content_analysis` → `creators`; `scraped_content.trend_id` FK. Migration `20260424170000_phase_2_schema_migration`.
8. ✅ **Discovery v2 (SP1):** two-stage resolver (fetch seed → classify+enrich destinations); deterministic URL classifier with LLM fallback cache; rule-cascade identity scorer with CLIP avatar tiebreak; multi-platform fetcher layer (IG/TT via Apify, YT via yt-dlp, OF via curl_cffi, Patreon/Fanvue/generic via httpx, FB+X stubbed for SP1.1); `bulk_imports` as first-class observable job; cross-workspace identity dedup on every commit via persistent `profile_destination_links` index; Manual Add Account triggers full resolver expansion with canonical-field protection. 102 pytest tests. Spec: `docs/superpowers/specs/2026-04-24-discovery-v2-design.md`. Plan: `docs/superpowers/plans/2026-04-24-discovery-v2-plan.md`. ✅ **Recursive funnel resolver** (sync 14): bounded follow-until-terminus expansion through `_expand`. ✅ **Universal URL Harvester** (sync 15, 2026-04-26): replaces per-aggregator `linktree.py` / `beacons.py` / `custom_domain.py` extractors with a single `scripts/harvester/` package — Tier 1 httpx static fetch + 4-signal escalation detector → Tier 2 Apify Puppeteer Scraper headless render with `window.open` / `location.href` setter hooks installed pre-page-script + auto-click 7 interstitial keyword variants. 24h `url_harvest_cache` table fronts the cascade. `DestinationClass` extended 4 → 10 values. Live smoke captured the Fanplace link previously hidden behind tapforallmylinks.com's 2-step "Sensitive Content / Open link" gate. 192 pytest. tsc 0.
9. 🔜 **Phase 2 scraping:** IG + TikTok Apify ingestion (scheduled via GitHub Actions every 12h), normalizers, `flag_outliers` live, Outliers page live
10. 🔜 **Phase 2 trends:** audio signature extraction from `platform_metrics`, trend linking during content analysis (populates `scraped_content.trend_id` + `trends`)
5. 🔜 **Phase 3 content analysis:** Gemini content scoring pipeline, `profile_scores` + rank tier live on UI
6. 🔜 **Phase 3 brand analysis:** Claude-driven brand report per creator, `creator_brand_analyses` populated, creator-level archetype/vibe filled
7. 🔜 **Phase 3 classification UI:** Content Classification + Creator Classification tabs for taxonomy curation
8. 🔜 **Phase 4 funnel editor:** React Flow drag-to-connect for `funnel_edges`
9. 🔜 **Phase 4 monetization intel:** Dashboards aggregating monetization_model across creators

**See [[Full Product Vision]] for the complete feature scope including agency ops modules.**

---

## 15. Agent Architecture

The Hub uses a **two-layer agent architecture**:

- **Layer 1 — Dev-time verification** (inside Claude Code sessions)
  Agents enforce "work actually works" before Claude declares done. Prevents the "claims done, reality empty" failure pattern.

- **Layer 2 — Runtime watchdogs** (deterministic, not LLM-based at row level)
  Webhooks and schema validators catch silent failures (login walls, empty datasets, parse errors) after ingestion.

**No in-app agentic self-healing.** At 2–5 users it adds more operational surface than it removes. Evidence: Anthropic's own "Building Effective Agents" guidance; community consensus across Pixelmojo, Blake Crosley, and the DEV.to "20 agents locally, one in prod" post.

---

## 15.1 Dev-Time Verifier Stack

### Core verification skills/plugins

| Component | Role | Install |
|---|---|---|
| `obra/superpowers` | The gate. Enforces verification-before-completion. Bundles TDD, systematic debugging, verifier subagent patterns. | `/plugin install superpowers@claude-plugins-official` |
| `kepano/obsidian-skills` | Obsidian Flavored Markdown for the vault (already installed). | existing |
| `anthropics/skills` (webapp-testing) | Canonical Python+Playwright pattern with multi-server lifecycle. Matches Next.js + Python stack. | `/plugin install example-skills@anthropic-agent-skills` |
| `nizos/tdd-guard` | Hook-based hard block: no code without a failing test first. Optional but recommended for Phase 3+. | see github |

### Core MCP servers for verifier access

| MCP | Purpose | Connection |
|---|---|---|
| `chrome-devtools-mcp` (Google) | Real Chrome navigation — detects auth walls, captchas, redirects, console errors. **This is what catches the Gemini-scraper-blocked-at-login case.** | `/plugin install chrome-devtools-mcp` |
| `playwright-mcp` (Microsoft) | Structured accessibility snapshots. Cross-browser. Storage-state for authenticated flows. | `claude mcp add playwright npx @playwright/mcp@latest` |
| `supabase-mcp` (official) | Schema/query/logs. **Always `read_only=true&project_ref=<DEV>`** — never connect to production with write access. | `claude mcp add --transport http supabase "https://mcp.supabase.com/mcp?project_ref=<DEV_REF>&read_only=true"` |
| `apify-mcp` | Actor runs, dataset inspection, logs for scraper debugging. | `claude mcp add apify npx @apify/actors-mcp-server` |
| `sentry-mcp` | Production error stack traces surfaced in dev sessions. | `claude mcp add --transport http sentry https://mcp.sentry.dev/mcp` |

### Verifier subagent pattern

`.claude/agents/verifier.md` — a dedicated subagent with **read-only tools only**:

Allowed: `Read`, `Grep`, `Glob`, `Bash`, `mcp__chrome-devtools__*`, `mcp__playwright__*`, `mcp__supabase__*`, `mcp__apify__*`.

**Forbidden: `Edit`, `Write`, any mutation tool.**

Rationale: a verifier that can fix code self-justifies rubber-stamping. Enforcing tool separation prevents the self-evaluation bias Anthropic documents. The verifier reports pass/fail with evidence; the implementer fixes.

### Stop hook as the hard gate

`.claude/settings.json` Stop hook invokes the verifier subagent before allowing task completion. The `stop_hook_active` flag prevents infinite loops. Non-zero exit blocks the turn from ending.

**Known issue:** Stop hooks are unreliable in the VSCode Claude Code extension (GitHub issues #17805, #29767, #40029). Use CLI mode for reliable enforcement; the extension works but cannot be trusted as a hard gate.

---

## 15.2 Runtime Watchdog Stack

### Apify webhooks (4 events, not 1)

Configure on every actor run:
- `ACTOR.RUN.SUCCEEDED` — normal success path
- `ACTOR.RUN.FAILED` — crashed
- `ACTOR.RUN.TIMED_OUT` — exceeded time limit
- **`ACTOR.RUN.SUCCEEDED_WITH_EMPTY_DATASET`** — the one most teams miss. Fires when the actor "succeeded" but wrote zero rows. Catches login walls, captcha deflection, site structure changes.

Webhook targets a Next.js API route or Supabase Edge Function. Returns 200 < 30s. Queues heavy work.

### Deterministic result validators (no LLM at row level)

Chain Apify's `lukaskrivka/results-checker` actor after every scrape:

```yaml
minItems: 50                                    # p5 of historical baseline
jsonSchema: schemas/social_post.schema.json
fieldRules:
  author: 0.95       # 95% of rows must have author
  content: 0.90
  url: 1.0           # 100% must have URL
compareWithPreviousExecution: true              # catches silent degradation
```

### Inside each actor run

- Store raw HTML sample: `{run_id}_raw.html` to Apify key-value store
- Validator regex: `sign in|captcha|cf-chl|access denied|log in` — fail run if found
- Pydantic validation on every row; retry via `tenacity` on `finish_reason in {"SAFETY", "RECITATION", "MAX_TOKENS"}`

### Supabase schema additions (Phase 2)

Add to `scraped_content`:
- `quality_flag` enum (`clean` | `suspicious` | `rejected`)
- `quality_reason` text

Populate before any row is exposed in UI. Surface flags in admin views. Never show `rejected` rows.

### Cron check (deterministic, no LLM)

Supabase scheduled function runs hourly:
```sql
-- Alert if any tracked creator has no successful scrape in 48h
SELECT creator_id, MAX(scraped_at) as last_scrape
FROM scraped_content
WHERE workspace_id = <ws>
GROUP BY creator_id
HAVING MAX(scraped_at) < NOW() - INTERVAL '48 hours';
```

Results post to a Slack webhook. No agent involvement.

### LLM-as-judge (only on flagged rows)

Gemini Flash reviews ~5% of scraped rows flagged as `suspicious` by deterministic validators. Decides: promote to `clean` or demote to `rejected`. Keeps LLM cost under $10/month at The Hub's scale.

---

## 16. Per-Phase Agent Requirements

**A phase is not complete until its required agents exist, are validated, and are documented in the Agent Catalog.**

### Phase 1 — Foundation & Creators

Required agents (retroactive adds):

| Agent | Layer | Status |
|---|---|---|
| `verify-and-fix` | Dev-time | ✅ Built — `.claude/skills/verify-and-fix/SKILL.md` |
| `verify-scrape` (slash command, not agent) | Dev-time | 🔜 Deferred until Phase 2 has real scrapes |
| `schema-drift-watchdog` | Ongoing | 🔜 Builds with Phase 2 |

### Phase 2 — Platform Intelligence + Scraping

Required agents:

| Agent | Layer | Purpose |
|---|---|---|
| `schema-drift-watchdog` | Dev-time | Weekly comparison: live Supabase vs PROJECT_STATE vs code queries |
| `scrape-verify` | Runtime | Post-ingestion check: row counts, field success rates, auth-wall detection |
| `verify-scrape` slash command | Dev-time | On-demand end-to-end check: Apify → Supabase → UI DOM integrity |

### Phase 3 — Analysis Engines

Required agents:

| Agent | Layer | Purpose |
|---|---|---|
| `brand-analysis` | Dev+Runtime | Multi-step Claude agent: bio + link-in-bio + top content → brand report. Writes to `creator_brand_analyses`. |
| `label-deduplication` | Runtime (nightly) | Embedding-based semantic merge of near-duplicate `content_labels`. Auto-merge at high confidence; escalate ambiguous. |
| `merge-candidate-resolver` | Runtime (nightly) | Auto-merges `creator_merge_candidates` at confidence ≥ 0.9. Escalates lower. |

### Phase 4 — Funnel & Monetization

Required agents:

| Agent | Layer | Purpose |
|---|---|---|
| `funnel-inference` | Runtime (weekly) | Scans content captions + link-in-bio destinations for `funnel_edges` the discovery pass missed. Proposes with confidence. |

### Ongoing (all phases)

| Agent | Layer | Purpose |
|---|---|---|
| `documentation-drift` | Dev-time (weekly) | Companion to `sync-project-state`. Scans for deprecated pattern references, broken wiki-links, unlinked files, stale session notes. |

---

## 17. Agent Design Principles

1. **Separation of tools.** Verifier agents never hold write access to the thing they verify. Self-evaluation bias is real; Anthropic has documented it.
2. **Deterministic before LLM.** Row-count checks, schema validation, regex — use these first. Only escalate flagged rows to LLM judgment.
3. **Explicit checklists beat vague criteria.** Verifier prompts must enumerate what to check. "Verify this works" produces rubber stamps.
4. **Escalate, don't guess.** On ambiguous cases, agents write to `06-Sessions/YYYY-MM-DD.md` under "Agent Escalations" and stop.
5. **One runtime per agent, or none.** Every agent running in production is a system to maintain. Weigh against scale. The Hub's scale mostly justifies dev-time agents + deterministic runtime watchdogs, not autonomous runtime agents.
6. **Read-only in production by default.** Only the `sync-project-state` skill and the brand-analysis agent write to Supabase. Verifiers never.
7. **Audit trail.** Every agent logs its actions to the day's session note. No silent modifications.
8. **Cost ceiling per agent.** Each agent has a documented monthly LLM cost estimate. If it exceeds ceiling, it's refactored or removed.

---

## 18. Agent-Stack-Specific Environment Variables

Add to `scripts/.env`:

```
# Webhook targets for Apify watchdog
APIFY_WEBHOOK_URL_SUCCEEDED=
APIFY_WEBHOOK_URL_FAILED=
APIFY_WEBHOOK_URL_EMPTY_DATASET=

# Sentry MCP (optional, for prod error surfacing in dev)
SENTRY_AUTH_TOKEN=
SENTRY_ORG_SLUG=

# Slack webhook for runtime alerts
SLACK_WEBHOOK_URL_ALERTS=
```

Add to `.claude/settings.json`:

```json
{
  "mcpServers": {
    "supabase": { "transport": "http", "url": "https://mcp.supabase.com/mcp?project_ref=<DEV_REF>&read_only=true" },
    "chrome-devtools": { "command": "npx", "args": ["chrome-devtools-mcp"] },
    "playwright": { "command": "npx", "args": ["@playwright/mcp@latest"] },
    "apify": { "command": "npx", "args": ["@apify/actors-mcp-server"] },
    "sentry": { "transport": "http", "url": "https://mcp.sentry.dev/mcp" }
  },
  "hooks": {
    "Stop": [
      { "command": "bash .claude/hooks/verify-before-stop.sh" }
    ]
  }
}
```

---

## 19. Integration with Existing Workflow

- **`sync-project-state` skill** — extend to read Apify latest-run metadata and Supabase `quality_flag` distribution. Writes a nightly `project-health.md` note in Obsidian.
- **`PROJECT_STATE.md` §7 Routes table** — add a "Verifier" column indicating which agent/slash-command validates each route.
- **`06-Sessions/YYYY-MM-DD.md`** — new section template: "Agent Escalations." Agents write here when they escalate.
- **`00-Meta/Stack & Tools.md`** — agent stack is referenced here, canonically defined in PROJECT_STATE.md §15–§18.
- **`04-Pipeline/Agent Catalog.md`** — operational details of each agent live here (triggers, workflow, escalation paths).

---

## 20. Known Limitations

| Issue | Location | Impact | Fix |
|---|---|---|---|
| `auth.uid()` returns null | `src/app/(dashboard)/creators/actions.ts` — `mergeCandidateCreators`, `retry_creator_discovery` | `resolver_id` / `p_user_id` passed to RPCs is null; merge/retry still works but loses audit trail | Wire Supabase Auth session when Auth is implemented |
| Anon key used in server actions | Same file — `getSupabase()` uses `NEXT_PUBLIC_SUPABASE_ANON_KEY` | RLS policies with `auth.uid()` checks may block writes | Switch to service role key (with `cookies()` auth) or implement Auth |
| Command Center outlier feed | `src/app/(dashboard)/page.tsx` | Outlier cards are hardcoded mock data — no live `scraped_content` query yet | Wire in Phase 2 when `flag_outliers` runs on real posts |
| Trend Signals feed | Same file | TrendItem cards are hardcoded mock data | Wire via `trend_signals` table in Phase 2–3 |
| Instagram CDN avatar expiry | `src/components/creators/AvatarWithFallback.tsx` | Avatar URLs scraped by Apify expire after ~hours. `onError` falls back to gradient monogram — so the UI degrades gracefully but the stored URL is stale | Re-scrape profile to refresh `avatar_url`. Long-term: proxy or store to Supabase Storage |
| Private / restricted Apify fetches mark creator `failed` | `scripts/discover_creator.py` — `fetch_input_context()` | `fetch_input_context` now raises `EmptyDatasetError` when Apify returns a shape-valid but all-null item (private / restricted / resolve-failed). The creator ends up `onboarding_status='failed'` with `empty_context: ...` in `last_discovery_error` (observed: ariaxswan 2026-04-24). Fail-fast is correct, but the UX is still "manual investigation required" — no automatic alternative path (e.g. TikTok fallback, screenshot-based discovery). | Long-term: if IG details fail, optionally fall back to TikTok details when a TT handle was supplied, or surface an "account may be private" hint in the UI. Short-term: operator manually confirms account status and either unarchives or re-queues with a corrected handle. |
| Apify details not written to profile | `scripts/discover_creator.py` — `commit()` + `run()` | `fetch_input_context` fetches bio / followers / avatar via Apify details, but only passes Gemini output to `commit_discovery_result`. The actual profile fields (bio, follower_count, avatar_url) are populated by a SECOND Apify call via `scrape_instagram_profile` — wasteful + relies on post metaData. | Pass `ctx` (or extracted profile fields) into `commit()` and write them directly to `profiles` before the posts scrape. |
| Dead-letter file has no replay tooling | `scripts/discover_creator.py` — `DEAD_LETTER_PATH` | Write-only JSONL. If `mark_discovery_failed` RPC exhausts retries, entries accumulate but there's no script to re-queue them. | Add `scripts/replay_dead_letter.py` that reads the file, re-queues each entry as a new `discovery_runs` row, truncates on success. |
| **Highlights v1 — shelved 2026-04-25** (Simon's call: discovery is "good enough" functionally after recursive funnel ship) | `scripts/fetchers/instagram_highlights.py` + `scripts/pipeline/resolver.py` (HIGHLIGHTS_ENABLED) | Code lives in the repo but `DISCOVERY_HIGHLIGHTS_ENABLED` defaults to `0` because `apify/instagram-scraper resultsType=stories` returns `no_items` without IG `sessionCookies` (verified by diagnostic 2026-04-25 on @kirapregiato + @esmaecursed). Recursive funnel + aggregator scraping is currently catching the majority case (Kira live-smoke: 3→8 profiles incl. link.me aggregator + 4-deep chain). Shelved gap = the slice of OF-adjacent creators who park CTAs only in highlights ("OF" / "LINKS" / "VIP" highlight reels) to dodge IG's bio-link crackdowns. | **Thaw conditions:** (a) discovery turns out to be missing CTAs we materially care about for managed creators or candidates (signal: a creator we're tracking has visible "OF link in highlights ↑" but no OF in our DB); OR (b) the v2 content-library use case (browsable highlight assets in the Creator HQ "Highlights" tab) becomes priority. **Resume work:** flip `DISCOVERY_HIGHLIGHTS_ENABLED=1`, wire IG `sessionCookies` from Simon's burner into the actor input (env var or Supabase Vault), document refresh runbook, re-smoke on Kira + Esmae. Spec/plan already written at `docs/superpowers/specs/2026-04-25-highlights-v1-design.md` + `docs/superpowers/plans/2026-04-25-highlights-v1.md`. |
| **SCHEMA.md regen blocked on missing `SUPABASE_DB_URL`** | `scripts/.env` (pre-existing tooling gap) | Live DB now has 24 tables; `docs/SCHEMA.md` still shows 23 because `npm run db:schema` requires `SUPABASE_DB_URL` to introspect Postgres directly and the env var is unset. PROJECT_STATE.md §4.1 has been hand-updated to reflect the 24-table reality. Discrepancy is cosmetic until SCHEMA.md can be regenerated. | Simon fills `SUPABASE_DB_URL` in `scripts/.env` (host visible in Supabase project settings; password is the DB password, not the service role key), then runs `npm run db:schema && npm run db:types`. Documented in user memory `project_schema_tooling.md`. |

---

## Decisions Log

- 2026-04-23: Installed agent architecture (UI skills + SCHEMA.md + Stop hook).
  Scope: 90-min minimal version, not the full 30-hr research plan.
  Rationale: 25-file codebase, 2-5 users, internal tool — full harness was over-engineered.
  See docs/AGENT_USAGE.md for day-to-day usage.
- 2026-04-24: Phase 1 schema drift resolved (migration 20260424000000). PROJECT_STATE §4 now matches live DB exactly. Phase 2 schema migration deferred to Phase 2 entry per docs/superpowers/specs/2026-04-23-phase-1-overhaul-design.md.
- 2026-04-24: Phase 1 overhaul complete on branch `phase-1-overhaul`. All 6 layers verified by both code-side checks (`npx tsc --noEmit` returns 0) and live-browser checks via chrome-devtools-mcp. 37 tasks delivered across ~30 commits. Highlights: typed Database generic on all Supabase clients, no more anon-key fallback, every page reads via `src/lib/db/queries.ts` helpers (zero raw `.from()` in pages), all server actions return `Result<T>`, `bulk_import_creator` RPC for atomic creator+profile+run insert, sonner toasts, EmptyState/ErrorState/ComingSoon shared components, sidebar standardized on `?tracking=`, dead UI controls (search/sort/Single Handle import/merge/retry/CreatorCard retry) all wired. Plan: docs/superpowers/plans/2026-04-23-phase-1-overhaul-plan.md. Spec: docs/superpowers/specs/2026-04-23-phase-1-overhaul-design.md. Discovery pipeline rebuild + Phase 2 migration remain on the Phase 2 roadmap as documented in §14.
- 2026-04-24: Discovery pipeline rebuilt on branch `phase-2-discovery-rebuild` (PR #2 merged to main). `fetch_input_context()` now dispatches to Apify (`apify/instagram-scraper` details mode for IG, `clockworks/tiktok-scraper` for TT) instead of httpx-against-login-walls. Link-in-bio resolver (`scripts/link_in_bio.py`) follows Linktree/Beacons pages. Gemini prompt explicitly grounds in provided context rather than prior knowledge (`build_prompt` includes literal "Ground every field in the provided context. Do not rely on prior knowledge."). `edge_type` enum created (migration 20260424150000) — fixes audit §1.1.7 latent crash. `commit_discovery_result` `funnel_edges` INSERT fixed to include `creator_id` (migration 20260424160000) — discovered during smoke test when Gemini produced real funnel edges for the first time. Pydantic `Literal` on `Platform` and `EdgeType` closes audit item 15 validation gap. `patreon` added to platform enum in `schemas.py`. `mark_discovery_failed` gets tenacity retry + dead-letter fallback at `scripts/discovery_dead_letter.jsonl`. Worker (`scripts/worker.py`) surfaces per-task exceptions via new `log_gather_results` instead of swallowing them. Full rewrite covered by 45 pytest tests (schemas / apify_details / link_in_bio / discover_creator / replay_dead_letter / worker). Smoke-tested by re-running discovery for all 3 existing creators — Natalie Vox + Esmae came through clean with real bio/follower/avatar/funnel-edge data; ariaxswan's Apify details fetch returned empty fields (new §20 known limitation). Plan: docs/superpowers/plans/2026-04-24-discovery-pipeline-rebuild.md.
- 2026-04-24: Phase 2 schema migration applied on branch `phase-2-schema-migration` (migration `20260424170000_phase_2_schema_migration`, PR #3 rebased onto main after PR #2). Adds `trends` and `creator_label_assignments` tables (20 tables total); creates `trend_type`, `llm_model`, and `content_archetype` enums; extends `label_type` with `creator_niche`; adds nullable `archetype` + `vibe` columns to `creators` (filled by Phase 3 brand analysis); adds `scraped_content.trend_id` FK; drops now-obsolete `archetype` + `vibe` from `content_analysis` (table was empty — no data loss). `npx tsc --noEmit` returns 0. Unblocks Phase 2 scraping + Phase 3 brand analysis.
- 2026-04-25: Discovery v2 (SP1) shipped on branch `phase-2-discovery-v2`. Two-stage resolver replaces the single-hop pipeline. Deterministic `pipeline/classifier.py` owns `(platform, account_type)` via a rule-first gazetteer (`data/monetization_overlay.yaml`) with cached LLM fallback (`classifier_llm_guesses`). Identity scorer (`pipeline/identity.py`) runs a first-match rule cascade: shared monetization URL → auto-merge; shared aggregator → auto-merge; bio cross-mention → candidate 0.8; cross-platform handle + CLIP ≥ 0.85 → candidate 0.7. `pipeline/resolver.py` orchestrates Stage A (fetch seed) + Stage B (classify + enrich destinations, aggregator children expanded once, no chaining). Budget-aware via `pipeline/budget.py`. 9 platform fetchers live under `fetchers/` (IG + TT via Apify, YT via yt-dlp, OF via curl_cffi with chrome120 JA3 impersonation, Patreon + Fanvue + generic via httpx, FB + X stubbed for SP1.1). Aggregators split into `aggregators/{linktree,beacons,custom_domain}.py`. Schema: 3 new tables (`bulk_imports`, `classifier_llm_guesses`, `profile_destination_links`) — 23 tables total; `discovery_runs.{bulk_import_id, apify_cost_cents, source}` added; `profiles.discovery_reason` added; unique pair index on `creator_merge_candidates`. RPCs: `commit_discovery_result` v2 (accepts `p_discovered_urls` + `p_bulk_import_id`, source-aware canonical-field protection for `manual_add`), `bulk_import_creator` v2 (returns `{bulk_import_id, creator_id, run_id}` jsonb), new `run_cross_workspace_merge_pass`. Worker passes `bulk_import_id` through and auto-fires the merge pass when a bulk terminates. Manual Add Account UI (`AddAccountDialog`) gains a "Run discovery on this account" checkbox (default on). 102 pytest tests. Live smoke (2026-04-25): Natalie Vox and Esmae re-discovered cleanly (4–7 profiles, 5–8 destination links, 3–6 funnel edges each); Aria Swan failed-fast with `empty_context:` (private/restricted IG — expected). Total Apify spend 48¢ across the 3-creator smoke. Caught and patched two in-flight bugs during smoke: classifier `_cache_lookup` didn't handle supabase-py 2.x returning `None` from `.maybe_single().execute()` on cache miss (commit `48849e7`); `commit_discovery_result` attempted to write `discovery_runs.updated_at` which doesn't exist (migration `20260425000200_fix_commit_discovery_result_no_updated_at`, commit `d81e645`). Spec: `docs/superpowers/specs/2026-04-24-discovery-v2-design.md`. Plan: `docs/superpowers/plans/2026-04-24-discovery-v2-plan.md`.
- 2026-04-25: Creator detail page revamped from "Instagram-page-for-the-model" into a proper creator brand HQ. Bio stripped from header (was an account-level value leaking into creator-level identity). Tabs forced horizontal across the top (was rendering side-by-side via missing Radix `orientation="horizontal"`). Single header **Add Account** button replaces 4 redundant per-section "Add manually" inline buttons; opens the existing `AddAccountDialog` with the v2 manual-add discovery flow. New `removeAccountFromCreator` server action wired into the AccountRow dropdown — soft-delete via `is_active=false`; Edit/Mark-Primary/Verify-Connection items hidden until backed by real implementations. `getProfilesForCreator` now filters `is_active=true` so Removed accounts disappear after refresh. Generic lucide icons replaced with real brand glyphs from `react-icons/si` (SiInstagram/SiTiktok/SiYoutube/SiX/SiFacebook/SiPatreon/SiOnlyfans/SiTelegram/SiLinktree); SiLinkedin/SiAmazon fall back to FontAwesome (`FaLinkedin`/`FaAmazon`); Fanvue/Fanplace/Beacons fall back to lucide. New `sortAccounts` util applies canonical platform order (primary → social IG/TT/YT/FB/X/LinkedIn → monetization OF/Patreon/Fanvue/Amazon/TT-shop → aggregators → messaging) at the render layer. Stats Strip "Social" sub-text now de-dupes platform names — Esmae no longer reads "instagram, twitter, instagram". Re-run/Retry Discovery buttons unified into a single component with `variant: 'header' | 'failed-state'`; CreatorCard's failed-state retry pill kept its own visual chrome but inherits the unified label "Re-run Discovery". `AccountRow` polished: `replaceAll('_',' ')` so `link_in_bio` reads as `link in bio`; em-dash for null/0 followers instead of `0 flwrs`; relative date format ("today", "1d ago"). Migration `20260425000300_fix_retry_creator_discovery_platform_cast` — RPC's INSERT into discovery_runs cast `input_platform_hint` to the `platform` enum (was failing UI Re-run with Postgres `42703`). Brand-icon + dedupe + label-fix patterns propagated to `/creators` grid and `/platforms/{instagram,tiktok}/accounts`. Three Next-16 sync-API regressions caught and fixed inline during the consistency pass (`/creators/[slug]`, `/creators`, `/platforms/{instagram,tiktok}/accounts` were treating params/searchParams as sync values; now `await` them). Brand Summary placeholder card added between stats strip and tabs to signal where Phase 3 brand analysis will land. tsc 0, pytest 102/102 green throughout. Commits: `3b08376` (params await) → `6f481ff` (retry RPC cast) → `6ec3048` (brand icons + sort) → `9a3b90b` (page restructure) → `cefa808` (is_active filter) → `03b0c8a` (consistency propagation).
- 2026-04-25: New project skill `autonomous-fix-list` (`.claude/skills/autonomous-fix-list/SKILL.md`) codifies the workflow Simon validated this session: when he hands a fix list with a full-autonomy phrase ("full autonomy", "every permission granted", "don't come back and ask", "use subagents to run everything", "minimal input from my end", "stay within our parameters"), run the full plan → dispatch (parallel where independent, sequenced where dependent) → catch unrelated regressions inline → final verify (tsc + pytest + visual via Chrome DevTools MCP) → push → report playbook end-to-end with zero check-ins. Companion to the existing `autonomous-execution` decision-gating policy. Skill commit: `93960a8`.
- 2026-04-25 (sync 14): **Recursive funnel resolver shipped + Highlights v1 code shipped/runtime gated on IG auth.** Branch `phase-2-discovery-v2`, 28 commits. Pytest 107 → 138.
  **Recursive funnel** (`docs/superpowers/plans/2026-04-25-recursive-funnel-resolution.md`): replaced the seed-only Stage B in `scripts/pipeline/resolver.py` with bounded follow-until-terminus recursion through `_expand(ctx, depth)`. After enriching a profile (depth ≥ 1), the resolver follows its `external_urls`, runs a cheap Gemini Flash bio-mentions extraction (`run_gemini_bio_mentions` in `scripts/discover_creator.py`), and recurses one hop deeper. Termination is natural — a profile is "terminal" iff its enrichment surfaces no new external_urls and no new bio mentions. Triple-bounded against runaway: existing `visited_canonical` cycle dedup (now also pre-seeded with the seed's own canonical URL via new `_build_seed_url` + `_SEED_HOST_FOR_PLATFORM` map for cycle protection) + `BudgetTracker` cap + `MAX_DEPTH=6` defensive cap (env: `DISCOVERY_MAX_DEPTH`). New `RECURSIVE_GEMINI` env flag (default ON) gates the bio-mentions extractor. Discovery confidence drops linearly with depth via `_confidence_at_depth`: depth 0 = 1.0, depth 1 = 0.9, drops 0.05 per hop, floors at 0.5. New `DiscoveredUrl.depth` field; `_commit_v2` builds a `depth_for_canon` lookup and applies the depth-aware confidence to both enriched and unenriched account rows. **Live smoke on Kira (run `8a60ef86`)**: 3 profiles → 8 profiles. Surfaced `link.me/kirapregiato` aggregator (depth 2, 0.85), `twitter/itskirapregiato` (depth 1, 0.80, bio mention), `about.link.me/{terms,privacy}` (depth 3, aggregator children), `tiktok/@Kira` (depth 4, 0.75). 9 destination_links. Apify cost 44¢. All confidence values match the formula exactly.
  **Highlights v1** (`docs/superpowers/specs/2026-04-25-highlights-v1-design.md`, `docs/superpowers/plans/2026-04-25-highlights-v1.md`): per the tier-decision doc (`docs/superpowers/specs/2026-04-25-highlights-tier-decision.md`), funnel-only slice. New `HighlightLink` Pydantic model. New fetcher `scripts/fetchers/instagram_highlights.py` calling `apify/instagram-scraper` with `resultsType="stories"`, `addParentData=True`, parsing `story_link_stickers[].url` and `mentions[].username`. New env constants `HIGHLIGHTS_ENABLED` (default OFF — see auth blocker below) and `HIGHLIGHTS_COST_CENTS=5`. `_expand` gains a third source after external_urls and bio_mentions: for `ctx.platform=="instagram"` at depth ≥ 1 with budget headroom, calls `fetch_highlights`, dispatches link-sticker URLs straight to `_classify_and_enrich(depth+1)`, dispatches caption mentions through `_synthesize_url(TextMention(...))` shim. No new tables, no UI changes — surfaced URLs flow through the existing `discovered_urls → commit_discovery_result → profile_destination_links` plumbing.
  **Highlights v1 BLOCKER (resolved interim, escalated for full fix):** live smoke + isolated diagnostic confirmed `apify/instagram-scraper resultsType="stories"` does NOT return pinned highlights without IG `sessionCookies`. `@kirapregiato` returns `{"error":"no_items"}`; `@esmaecursed` silently falls back to scraping 183 feed posts (no `story_link_stickers` field anywhere). Code is correct (fetcher returns `[]` gracefully); the actor just can't deliver. Interim: `DISCOVERY_HIGHLIGHTS_ENABLED` default flipped to "0" (commit `283ca37`) so prod doesn't burn ~10¢/secondary on guaranteed-empty calls. **Decision pending from Simon next session:** add IG sessionCookies (real fix, ban risk + cookie-rotation overhead) vs. try alternative actor (probably hits same wall) vs. defer indefinitely. Highlights v2 (content storage + UI) blocked on the same external dependency.
  **Pollish items deferred from recursive-funnel smoke:** aggregator footer-link noise filter (link.me's `termsandconditions`/`privacypolicy` surfaced as creator destinations); URL canonicalizer should strip tracking params (`?igsh=...`, `?s=21`); `visited_canonical` should be case-insensitive on path (`@Kira` and `@kira` currently treated as distinct). All non-blocking; queued.
  **Subagent-driven execution stats:** 6 implementer dispatches (Tasks 0-3, 4, 5-9, 10-12, 13-14, then Highlights v1 setup, wiring, safety tests) + 12 reviewer dispatches (spec compliance + code quality per batch) + 1 verifier subagent + 1 design subagent + 1 doc-writer subagent + 1 diagnostic subagent. Verifier returned PASS on all 9 checks. All reviews approved with non-blocking observations.
  Total commits: 28 (recursive funnel: 16 incl. plan rewrite & dead-@retry fix; highlights v1: 8; tier-decision doc + flag flip + sync: 4). Diagnostic output preserved at `/tmp/diag_highlights.out`.
- 2026-04-26 (sync 15): **Universal URL Harvester shipped.** Branch `phase-2-discovery-v2`, 17 commits ahead of origin pre-sync. Replaces the per-aggregator extractor stack (`scripts/aggregators/{linktree,beacons,custom_domain}.py`, deleted) with a single-entry `scripts/harvester/` package. **Architecture:** `harvester.harvest_urls(url, supabase)` runs a 3-tier cascade — (1) `url_harvest_cache` lookup (24h TTL, workspace-agnostic, mirrors `classifier_llm_guesses` pattern); (2) Tier 1 = `tier1_static.fetch_static` httpx+BS4 with a 4-signal escalation detector (SPA marker, near-empty anchor count, sensitive-content gate keywords, JS-only body); (3) Tier 2 = `tier2_headless.fetch_headless` via `apify/puppeteer-scraper` actor running a custom `page_function.js` that hooks `window.open` + `location.href` setters BEFORE page scripts execute and auto-clicks 7 interstitial keyword variants ("open link", "continue", "i am over 18", "i agree", "i confirm", "18+", "enter") via Puppeteer 22+ `page.$$('xpath/...')` selector syntax. Each harvested URL gets canonicalized, classified through `pipeline.classifier`, then mapped through a host-aware `_destination_class_for(account_type, canonical_url)` that promotes Substack/Spotify/Apple Podcasts to `content`, amzn.to/geni.us/shareasale to `affiliate`, Shopify/Etsy/Depop to `commerce`, Telegram/WhatsApp/Discord to `messaging`. **DB:** new table `url_harvest_cache` (24 tables total); 3 audit columns added to `profile_destination_links` (`harvest_method`, `raw_text`, `harvested_at`); `destination_class` CHECK constraint extended from 4 → 10 values (TEXT-with-CHECK, not Postgres ENUM, for forward-compat). `commit_discovery_result` v3 writes the new audit fields; v4 patches the ON CONFLICT clause to update `destination_class` so post-fix re-runs refresh stale rows (caught when t.me URLs from pre-fix runs stuck at `other` instead of `messaging`). **Resolver wiring:** `_classify_and_enrich` now delegates to `harvest_urls()` (one call per page, returns all outbound destinations) instead of dispatching per-aggregator. **UI:** Creator HQ renders new "All Destinations" section grouped by `destination_class` with a `gated` chip on rows where `harvest_method='headless'`. **Gazetteer:** ~30 new rules in `data/monetization_overlay.yaml` covering BuyMeCoffee, Ko-fi, Substack subdomains, Spotify, Telegram, WhatsApp, affiliate redirectors. **Live smoke (2026-04-26):** re-discovered `esmaecursed-1776896975319784`. The previously-invisible **Fanplace link** (hidden behind tapforallmylinks.com's 2-step "Sensitive Content / Open link" gate) was cleanly captured — Tier 1 detected the gate via the sensitive-content signal, Tier 2 hooked the `location.href` setter and harvested all 6 destinations including 2 messaging links. Total Apify spend ~80¢ across 4 smoke runs. **Tests:** 192 pytest passing. tsc 0 errors. **Migrations applied via MCP:** `20260426000000_url_harvester_v1` (cache table + audit cols), `20260426010000_commit_discovery_result_v3_harvester_audit`, `20260426020000_extend_destination_class_check`, `20260426030000_commit_discovery_result_v4_update_destination_class`. **Known limitation surfaced:** SCHEMA.md regen still blocked on missing `SUPABASE_DB_URL` — live DB has 24 tables, `docs/SCHEMA.md` shows 23 (cosmetic; PROJECT_STATE §4.1 hand-updated). Pre-existing tooling gap; Simon's call to fill the env var.
- 2026-04-25 (sync 13): Discovery surface hardened end-to-end across worker, RPCs, fetchers, and UI on branch `phase-2-discovery-v2` (10 commits, head `8bc9ddc`). **Always-on worker:** `scripts/worker.py` is now managed by macOS launchd via `~/Library/LaunchAgents/com.thehub.worker.plist` (RunAtLoad + KeepAlive + ThrottleInterval=10s, logs to `~/Library/Logs/the-hub-worker.{log,err.log}`). New `scripts/worker_ctl.sh` with `install/start/stop/restart/unload/status/log/err/uninstall` subcommands; `restart` triggers SIGTERM and lets KeepAlive respawn the process with fresh code (necessary after pipeline edits). PROJECT_STATE §15 still avoids in-app runtime agents at production scale; for the local single-machine dev box, launchd is the standard macOS pattern. **Live progress UI:** new `discovery_runs.progress_pct (smallint, default 0)` + `progress_label (text)` columns (migration `20260425010000`). Pipeline emits 5 stages — 10% Fetching profile → 35% Resolving links → 70% Analyzing → 90% Saving → 100% Done. New `<DiscoveryProgress>` client component polls `getDiscoveryProgress` server action every 3s while a card is in `processing` state; calls `router.refresh()` when status flips. Drops into the CreatorCard processing branch + creator HQ "Discovering…" banner. Polling chosen over Realtime — no `ALTER PUBLICATION` needed, only fires while in flight, simple. **Pipeline data persistence:** `_commit_v2` now (a) builds a stub `profiles` row for any `DiscoveredUrl` not already enriched (so novel platforms — Wattpad/Substack/etc — land in profiles instead of being stranded in `profile_destination_links` only), and (b) writes a canonical seed/primary URL via new `_seed_profile_url(platform, handle)` helper (without it the seed account had `url=null` and the UI rendered the row as plain text instead of a clickable link). **Fetcher resilience:** new `is_transient_apify_error()` predicate in `fetchers/base.py` matches "user was not found", "authentication token", "rate limit", "challenge", "session expired", "captcha", "too many requests", "429"; tenacity-wrapped `_call_actor` in `instagram.py` and `tiktok.py` retries 3× with 3-15s exponential backoff. EmptyDatasetError stays non-retryable by design. **RPC fixes:** `retry_creator_discovery` now updates `creators.last_discovery_run_id` to the new run (migration `20260425020000`) — without this the DiscoveryProgress component polled the previous failed run forever, so the new run's spinner stuck at "Queued 0%". `bulk_import_creator` got the missing `::platform` cast on its `discovery_runs` INSERT (migration `20260425030000`) — same shape as the retry-RPC cast bug from earlier in the day, missed in that sweep; before the patch every Bulk Paste / Single Handle import errored with Postgres `22P02`. **Creator card cleanup:** stripped platform identity from CreatorCard ready state (no `@handle`, no IG icon under name) and failed state (canonical-name monogram in red box instead of a faded IG icon), matching the HQ-page subtitle cleanup that landed earlier the same day. Sidebar tracking-type shortcuts (Managed/Candidates/Competitors/Inspiration) removed — the in-page chip row is now the single source of filter truth. **Operational note:** during smoke a different bug surfaced — `scripts/.env` held a revoked `APIFY_TOKEN` while Simon's shell had the working one; launchd workers see only their plist's clean env, so they used the bad one and got 401s from Apify ("User was not found or authentication token is not valid"). Tokens were 46-char different values both prefixed `apify_ap`. Resolution: backed up `scripts/.env` → `.env.bak.{ts}`, replaced just the `APIFY_TOKEN=` line via Python rewrite, restarted worker. Aria Swan re-discovery then completed cleanly to 100% with all expected accounts. **Tests:** pytest 102 → 107 (3 new for novel-platform persistence + 2 for seed URL). All 4 creators in DB now have valid primary URLs (Kira backfilled directly via SQL).
