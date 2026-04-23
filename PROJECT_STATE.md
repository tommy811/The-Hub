# PROJECT_STATE.md

**The Hub — Creator Intelligence Platform**
Last synced: 2026-04-23 (sync 6)

> This file is the master technical reference. Every AI Studio session starts by pasting this. Claude Code reads this first on every session. Repo and Obsidian vault share one folder — this file is directly visible in both.

---

## 1. What The Hub Is

Internal tool for a 2–5 person creator management agency. **Not a SaaS.** The Creator is the source-of-truth entity; every other entity (accounts, content, analyses, funnel edges, trends) links back to a creator.

Daily job: discover creators → scrape their content across platforms → AI-score and label → surface outliers and winning patterns → feed insights into agency workflows.

---

## 2. Tech Stack

- **Frontend:** Next.js 14 (App Router, Server Components where possible), TypeScript strict, Tailwind, shadcn/ui, Recharts, lucide-react, framer-motion, @xyflow/react
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

### 4.1 Currently live in Supabase (18 tables)

**Tenancy**
- `workspaces` — id, name, slug, owner_id, created_at
- `workspace_members` — workspace_id, user_id, role (`workspace_role`), joined_at

**Creator layer (root)**
- `creators` — id, workspace_id, canonical_name, slug, known_usernames[], display_name_variants[], primary_niche, primary_platform, monetization_model, tracking_type, tags[], notes, onboarding_status, import_source, last_discovery_run_id, last_discovery_error, added_by, timestamps
- `creator_accounts` alias = `profiles` (same table)
- `profiles` — id, workspace_id, creator_id (FK nullable for legacy), platform, handle, display_name, profile_url, url, avatar_url, bio, follower_count, following_count, post_count, tracking_type, tags[], is_clean, analysis_version, last_scraped_at, added_by, is_active, account_type, discovery_confidence, is_primary (bool, default false), timestamps
- `discovery_runs` — id, workspace_id, creator_id, input_handle, input_url, input_platform_hint, status, raw_gemini_response, assets_discovered_count, attempt_number, error_message, initiated_by, timestamps
- `creator_merge_candidates` — id, workspace_id, creator_a_id, creator_b_id (a<b enforced), confidence, evidence (jsonb), triggered_by_run_id, status, resolved_by, timestamps
- `funnel_edges` — id, creator_id, workspace_id, from_profile_id, to_profile_id, edge_type, confidence, detected_at
- `creator_brand_analyses` — id, creator_id, workspace_id, version, niche_summary, usp, brand_keywords[], seo_keywords[], funnel_map (jsonb), monetization_summary, platforms_included[], gemini_raw_response, analyzed_at

**Content layer**
- `scraped_content` — id, profile_id, platform, platform_post_id (unique per platform), post_url, post_type, caption, hook_text, posted_at, view_count, like_count, comment_count, share_count, save_count, engagement_rate (generated), platform_metrics (jsonb), media_urls[], thumbnail_url, is_outlier, outlier_multiplier, raw_apify_payload (jsonb), timestamps
- `content_analysis` — id, content_id (unique), quality_score, archetype TEXT, vibe content_vibe, category, visual_tags[], transcription, hook_analysis, is_clean, analysis_version, gemini_raw_response, model_version, analyzed_at *(archetype + vibe drop in Phase 2 migration — see §4.2)*
- `content_metrics_snapshots` — content_id, snapshot_date, view_count, like_count, comment_count, share_count, save_count, velocity, PK (content_id, snapshot_date)
- `profile_metrics_snapshots` — profile_id, snapshot_date, follower_count, median_views, avg_engagement_rate, outlier_count, quality_score, PK (profile_id, snapshot_date)
- `profile_scores` — profile_id (unique), current_score, current_rank (generated from `calculate_rank`), scored_content_count, last_computed_at

**Labels & taxonomy**
- `content_labels` — id, workspace_id, label_type (`content_format|trend_pattern|hook_style|visual_style|other`), name, slug, description, usage_count, is_canonical, merged_into_id (self FK), created_by, created_at
- `content_label_assignments` — content_id, label_id, assigned_by_ai, confidence, PK (content_id, label_id)

**Signals & alerts**
- `trend_signals` — id, workspace_id, signal_type, creator_id, account_id, content_id, score, detected_at, metadata (jsonb), is_dismissed
- `alerts_config` — id, workspace_id, name, rule_type, threshold_json, target_profile_ids[], is_enabled, notify_emails[], created_by
- `alerts_feed` — id, workspace_id, config_id, content_id, profile_id, creator_id, triggered_at, is_read, payload (jsonb)

### 4.2 Pending migration (Phase 2 entry point)

Two new tables + enum extension + column adds. This migration runs when Phase 2 ingestion starts.

**New table: `trends`**
```
id uuid PK
workspace_id uuid FK workspaces
name text             — e.g. "Espresso – Sabrina Carpenter"
trend_type enum (new): audio | dance | lipsync | transition | meme | challenge
audio_signature text  — normalized: "espresso-sabrina-carpenter"
audio_artist text (nullable)
audio_title text (nullable)
description text
usage_count int
is_canonical boolean
peak_detected_at timestamptz
created_at timestamptz
UNIQUE (workspace_id, audio_signature) WHERE audio_signature IS NOT NULL
```

**New table: `creator_label_assignments`** (mirrors `content_label_assignments`)
```
creator_id uuid FK creators
label_id uuid FK content_labels
assigned_by_ai boolean
confidence numeric(3,2)
PK (creator_id, label_id)
```

**Enum additions:**
- `label_type` += `creator_niche`
- New enum `trend_type`: `audio | dance | lipsync | transition | meme | challenge`
- New enum `llm_model`: `gemini_pro | gemini_flash | claude_opus | claude_sonnet`

**Column additions on `creators`:**
- `archetype content_archetype` (nullable, filled by Phase 3 brand analysis)
- `vibe content_vibe` (nullable, filled by Phase 3 brand analysis)

**Column additions on `scraped_content`:**
- `trend_id uuid REFERENCES trends(id)` (nullable)

**Column removals from `content_analysis`:**
- DROP COLUMN `archetype` (moved to creators — archetype is a creator-level property)
- DROP COLUMN `vibe` (moved to creators — vibe is a creator-level property)

**Rationale:** archetype and vibe describe the creator's overall brand identity, not individual posts. A single post carrying the "goth" vibe doesn't tell you much; across a creator's full body of work, it defines the brand. Content-level stays with `category`, dynamic labels, and visual tags.

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
| `label_type` | content_format, trend_pattern, hook_style, visual_style, creator_niche (pending), other |
| `trend_type` (pending) | audio, dance, lipsync, transition, meme, challenge |
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
| `commit_discovery_result` | (p_run_id, p_creator_data jsonb, p_accounts jsonb, p_funnel_edges jsonb) → jsonb | Transactional: enriches creator, upserts profiles (with collision → merge_candidates), inserts funnel edges, marks run completed. Returns `{creator_id, accounts_upserted, merge_candidates_raised}` |
| `mark_discovery_failed` | (p_run_id, p_error text) → void | Sets run.status=failed, creator.onboarding_status=failed |
| `retry_creator_discovery` | (p_creator_id, p_user_id) → uuid | Creates new `discovery_runs` (attempt_number+1), copies `input_handle` + `input_platform_hint` from most recent prior run, returns new run_id |
| `merge_creators` | (p_keep_id, p_merge_id, p_resolver_id, p_candidate_id) → void | Migrates profiles/edges/analyses merge→keep, merges known_usernames[], archives merged creator |

---

## 7. Routes — Wiring Status

| Route | File | Status |
|---|---|---|
| `/` | `(dashboard)/page.tsx` | ✅ Live — Command Center with live stats from Supabase |
| `/creators` | `(dashboard)/creators/page.tsx` | ✅ Live — real queries, bulk import works |
| `/creators/[slug]` | `(dashboard)/creators/[slug]/page.tsx` | 🟡 Partial — Full revamp: stats strip (Total Reach, account type counts), bio, AvatarWithFallback, network sections with icons. Content/Branding/Funnel tabs are coming-soon stubs. |
| `/content` | `(dashboard)/content/page.tsx` | ⬜ Placeholder |
| `/trends` | `(dashboard)/trends/page.tsx` | ⬜ Mock — UI built, no live data |
| `/admin` | `(dashboard)/admin/page.tsx` | ⬜ Placeholder |
| `/platforms/instagram/accounts` | `platforms/instagram/accounts/page.tsx` + `InstagramAccountsClient.tsx` | ✅ Live — real `profiles` query, stat cards, tracking tab URL filter, rank chip client filter, empty state, Unlinked badge |
| `/platforms/instagram/outliers` | — | ⬜ Placeholder |
| `/platforms/instagram/classification` | — | ⬜ Placeholder |
| `/platforms/instagram/analytics` | — | ⬜ Placeholder |
| `/platforms/tiktok/accounts` | `platforms/tiktok/accounts/page.tsx` + `TikTokAccountsClient.tsx` | ✅ Live — real `profiles` query, stat cards, tracking tab URL filter, rank chip client filter, empty state, Unlinked badge |

**Known cleanup:** Sidebar has duplicate `/content` route ("Content Hub" in DAILY + "Content" in ANALYZE) → delete duplicate. TikTok Intel section is header-only → add child routes matching Instagram. `/admin` needs scope definition.

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
3. 🔄 **Wire existing stub routes** to live Supabase data: ✅ `/platforms/instagram/accounts`, ✅ `/platforms/tiktok/accounts` — 🔜 `/content`, `/trends` remaining
3. 🔜 **Phase 2 scraping:** IG + TikTok Apify ingestion, normalizers, `flag_outliers` live, Outliers page live
4. 🔜 **Phase 2 trends:** `trends` table migration, audio signature extraction from `platform_metrics`, trend linking during content analysis
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
| `verify-and-fix` | Dev-time | 🔜 Next build (blocks Phase 1 close) |
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
| Discovery pipeline broken (httpx) | `scripts/discover_creator.py` — `fetch_input_context()` | `httpx.get("https://www.instagram.com/{handle}/")` returns login redirect or bot block. Gemini receives garbage. Discovery "succeeds" but finds no real data. | Rebuild: replace httpx with Apify `resultsType: "details"` to get real bio + externalUrls. Phase 2 first task. |
