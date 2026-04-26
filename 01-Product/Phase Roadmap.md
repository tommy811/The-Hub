# Phase Roadmap

See [[Full Product Vision]] for the complete 9-module scope.

---

## Phase 1 — Foundation & Creators ✅ COMPLETE (feature work)

- ✅ Complete Supabase schema (18 tables, all RLS)
- ✅ Creator layer migration applied to Content OS
- ✅ Creators hub UI (Bulk import, card grid, deep-dive)
- ✅ Discovery pipeline (Python + Gemini, worker, apify_scraper)
- ✅ Cross-platform identity resolution (merge candidates, rapidfuzz)
- ✅ Claude Code wiring to live Supabase + Realtime transitions
- ✅ Phase 1 UX hardening (Re-run Discovery, Add Account dialog, detail page revamp, avatar fallback, Apify field mapping fix)

### Required Agents — Phase 1
- **verify-and-fix** — ✅ Built (`claude/skills/verify-and-fix/SKILL.md`)

> ✅ Phase 1 agent requirement met. Phase 1 is fully closed.

See [[PROJECT_STATE#16. Per-Phase Agent Requirements]] for full agent requirements table.

**verify-and-fix** — Post-change verification loop. Starts dev server, checks TypeScript compile, curls affected pages for 200 response, verifies Supabase query shapes via MCP, smoke-tests server actions. Auto-fixes up to 3 loops, then escalates with full error context. Solves "Claude says it works, doesn't actually work."

---

## Phase 2 — Platform Intelligence 🔄 IN PROGRESS

### Feature Work
- ✅ Wire `/platforms/instagram/accounts` + `/platforms/tiktok/accounts` to live data
- ✅ Discovery pipeline rebuild — `fetch_input_context` replaced with Apify (`apify/instagram-scraper` details mode for IG, `clockworks/tiktok-scraper` for TT); Linktree/Beacons resolver; Gemini prompt grounded in provided context; `edge_type` enum + funnel_edges fix; 45 pytest tests (PR #2 merged to main)
- ✅ Phase 2 schema migration: `trends` + `creator_label_assignments` tables; `trend_type` / `llm_model` / `content_archetype` enums; `creator_niche` on `label_type`; `archetype`+`vibe` moved from `content_analysis` → `creators`; `scraped_content.trend_id` FK. (Migration `20260424170000_phase_2_schema_migration`, PR #3.)
- ✅ **Discovery v2 (SP1)** — two-stage resolver, deterministic URL classifier, rule-cascade identity scorer with CLIP avatar tiebreak, 9 platform fetchers (IG/TT/YT/Patreon/OF/Fanvue/generic + FB/X stubs), `bulk_imports` observable job, cross-workspace dedup on every commit, Manual Add Account triggers resolver expansion with canonical-field protection. 102 pytest tests, live-smoke passed. Migrations `20260425000000_discovery_v2_schema` + `20260425000100_discovery_v2_rpcs` + `20260425000200_fix_commit_discovery_result_no_updated_at`. (PR #4.)
- ✅ **Always-on discovery worker** — `scripts/worker.py` runs as a macOS launchd user agent (`com.thehub.worker`); RunAtLoad + KeepAlive + ThrottleInterval=10s. Managed via `scripts/worker_ctl.sh`. Logs at `~/Library/Logs/the-hub-worker.{log,err.log}`.
- ✅ **Live progress UI for in-flight runs** — `discovery_runs.progress_pct/label` columns (migration `20260425010000`) + `<DiscoveryProgress>` polling client component. 5-stage emit map (Fetching profile → Resolving links → Analyzing → Saving → Done). Drops into CreatorCard processing branch + creator HQ banner.
- ✅ **Discovery surface bugfix sweep** (sync 13) — retry RPC updates `last_discovery_run_id` (migration `20260425020000`); bulk_import RPC missing `::platform` cast (migration `20260425030000`); seed/primary profile URL written on `_commit_v2`; novel-platform stub rows persisted (Wattpad/Substack/aggregators); fetcher retry on transient Apify failures via tenacity. pytest 102 → 107.
- ✅ **Recursive funnel resolver** (sync 14) — bounded follow-until-terminus expansion through `_expand`. Termination is natural; triple-bounded against runaway via `visited_canonical` dedup + `BudgetTracker` cap + `MAX_DEPTH=6`. Confidence drops linearly with depth. Live smoke on Kira: 3 → 8 profiles. pytest 107 → 138.
- ✅ **Universal URL Harvester** (sync 15, 2026-04-26) — `scripts/harvester/` package with single entry `harvest_urls()`. Replaces per-aggregator dispatch. 3-tier cascade: cache (24h TTL via new `url_harvest_cache` table) → Tier 1 (httpx + 4-signal escalation detector) → Tier 2 (`apify/puppeteer-scraper` with `window.open`/`location.href` setter hooks pre-page-script + 7 auto-click interstitial keyword variants). `DestinationClass` extended 4 → 10 values. New audit columns on `profile_destination_links` (`harvest_method`, `raw_text`, `harvested_at`). Creator HQ renders new "All Destinations" section grouped by class. Live smoke captured the Fanplace link previously hidden behind tapforallmylinks.com's 2-step "Sensitive Content / Open link" gate. 192 pytest. tsc 0. ~80¢ total smoke cost.
- ✅ **Profile noise filter retroactive cleanup + UI polish** (sync 16 / T16, 2026-04-26) — soft-deleted 30 stale noise profile rows; resolver `_classify_and_enrich` calls `is_noise_url(canon)` at the gate before noise URLs become rows; `_commit_v2` URL-keyed dedup pass before RPC; PLATFORMS dict gains reddit/threads/bluesky/snapchat; unified `lucide Link` clip icon for all aggregator types; All Destinations panel moved below tabs in collapsed `<details>`; Stats Strip uses `resolvePlatform(platform, url)` for proper labels.
- ✅ **Specific platform identification + AccountRow restructure + banner foundation** (sync 16 / T17, 2026-04-26) — Postgres `platform` enum extended +19 values (`link_me`, `tapforallmylinks`, `allmylinks`, `lnk_bio`, `snipfeed`, `launchyoursocials`, `fanfix`, `cashapp`, `venmo`, `snapchat`, `reddit`, `spotify`, `threads`, `bluesky`, `kofi`, `buymeacoffee`, `substack`, `discord`, `whatsapp`) via migration `20260426040000`. Total enum count ~37. Pydantic `Platform` Literal updated to match. Gazetteer rewritten with 13 specific host→platform rules (6 generic ones removed). PLATFORMS dict gained 13+ new icon entries. AccountRow restructured: Column 1 = `[icon] [Platform Name]`, Column 2 = handle + display_name. Migration `20260426050000_creator_cover_and_banner` added 3 `creators` columns + `<BannerWithFallback>` component. All 5 creators re-discovered cleanly (Esmae, Aria, Kira, Natalie, Valentina; ~$1 Apify spend total). Valentina's link.me + Fanfix + Cash App + Venmo coexist as 4 distinct rows — the unique-key collision bug from earlier syncs is fixed. 227 pytest. tsc 0.
- 🔜 SP1.1 — provision live Apify actors for Facebook + Twitter (fetchers are stubbed with `source_note='stub:not_implemented'`)
- 🔜 Wire `/content` and `/trends` routes
- 🔜 Per-platform scraping: IG + TikTok via Apify (scheduled via GitHub Actions every 12h)
- 🔜 Normalizer modules (`normalize_instagram.py`, `normalize_tiktok.py`)
- 🔜 Outlier detection (flag_outliers RPC — threshold ≥ 3.0×, 15-post floor, 48h age guard)
- 🔜 Platform accounts page — 4-tab layout (Accounts / Outliers / Classification / Analytics)
- 🔜 Daily snapshot cron job (`content_metrics_snapshots`, `profile_metrics_snapshots`)
- 🔜 Trend linking during content analysis — audio signature extraction from `platform_metrics` populates `scraped_content.trend_id`
- 🔜 `quality_flag` + `quality_reason` columns on `scraped_content` (runtime watchdog per §15.2)

### Required Agents — Phase 2
- **schema-drift-watchdog** — Weekly scan: live Supabase schema vs PROJECT_STATE.md §4 vs code queries. Surfaces drift before it breaks production.
- **scrape-verify** — Post-ingestion verification. Apify webhook handler: row counts, field success rates, auth-wall regex, Pydantic validation. Sets `quality_flag`.
- **verify-scrape** (slash command) — On-demand end-to-end check: Apify → Supabase → UI DOM integrity. Run before declaring any scraper work complete.

---

## Phase 3 — Analysis Engines

### Feature Work
- Gemini content scoring batch pipeline (quality_score, category, visual_tags)
- Claude brand analysis per creator (niche_summary, USP, SEO keywords, archetype, vibe)
- Dynamic label taxonomy + Classification UI
- `profile_scores` + rank tier live computation
- `creator_brand_analyses` reports in creator deep-dive

### Required Agents — Phase 3
- **brand-analysis** — Multi-step Claude agent: bio + link-in-bio + top content → niche, USP, brand_keywords, seo_keywords, archetype, vibe. Writes to `creator_brand_analyses` with versioned `version` column.
- **label-deduplication** — Nightly embedding-based semantic merge of near-duplicate `content_labels`. Auto-merge at ≥ 0.98 similarity; escalate 0.92–0.98.
- **merge-candidate-resolver** — Auto-merges `creator_merge_candidates` at confidence ≥ 0.9 nightly. Escalates lower for human review.

---

## Phase 4 — Funnel & Monetization

### Feature Work
- React Flow funnel editor (drag-to-connect `funnel_edges`)
- Monetization intelligence dashboards
- Cross-creator pattern detection
- Revenue Center shell (manual entry — no scraping of private revenue data)
- Telegram + OF intel

### Required Agents — Phase 4
- **funnel-inference** — Scans content captions + link-in-bio destinations for `funnel_edges` the discovery pass missed. Proposes with confidence ≤ 0.7; requires human approval in funnel editor UI.

## Out of Scope

- Client-facing portal login
- Multi-tenant SaaS
- Audio fingerprinting
- Screenshot-based funnel mapping (deferred)
- Private revenue scraping (OF/Fanvue/Amazon)
