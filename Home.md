# The Hub — Project Home

## Quick Links
- [[PROJECT_STATE|📐 Project State]] — schema, enums, conventions
- [[00-Meta/Stack & Tools|🧰 Stack & Tools]] — every tool, service, MCP, skill, and workflow pattern
- [[01-Product/Phase Roadmap|🗺 Phase Roadmap]] — what's built, what's next
- [[01-Product/Full Product Vision|🔭 Full Product Vision]] — all 9 modules, complete scope
- [[03-Database/Migration Log|🗄 Migration Log]] — database change history
- [[04-Pipeline/Agent Catalog|🤖 Agent Catalog]] — registry of all agents and their triggers
- [[06-Sessions/|📅 Sessions]] — daily work logs

## Current Status
- Phase: **Phase 2 in progress 🔄** — Discovery v2 live + Universal URL Harvester (sync 15) + profile noise cleanup + specific platform identification + AccountRow + banner foundation (sync 16) + handle normalization + regression-test ring + Gemini-enriched watchdog (sync 17); scraping + trends + content/trends routes next
- Database: ✅ Supabase (Content OS project) — 24 tables live; `platform` enum at ~37 values; 4 enriched-metadata columns on `classifier_llm_guesses`; `new_platform_watchdog` view (T19 v1 + T20 v2 with Gemini suggestions) live
- Repo: github.com/tommy811/The-Hub
- Open PR: [#4 phase-2-discovery-v2](https://github.com/tommy811/The-Hub/pull/4) — Discovery v2 + UI polish + recursive funnel + Universal URL Harvester + specific platform identification + banner foundation + duplicate-prevention regression ring + Gemini-enriched watchdog
- Last session: [[06-Sessions/2026-04-26]] (sync 17 appended) — all duplicate-prevention bugs locked with regression tests; Gemini surfaces VA-ratifiable platform suggestions per novel host

## Active Work
- ✅ Discovery pipeline rebuilt — Apify-grounded context, Linktree/Beacons resolver, grounded Gemini prompt, dead-letter retry, 45 pytest tests (PR #2)
- ✅ Phase 2 schema migration — `trends` + `creator_label_assignments`, `trend_type` / `llm_model` / `content_archetype` enums, `creators.archetype`+`vibe`, `scraped_content.trend_id` (PR #3)
- ✅ **Discovery v2 (SP1)** — two-stage resolver, deterministic classifier, rule-cascade identity scorer, 9 platform fetchers (IG/TT/YT/Patreon/OF/Fanvue/generic + FB/X stubs), `bulk_imports` observable job, cross-workspace dedup every commit, Manual Add Account triggers resolver expansion. 102 pytest tests. Live smoke passed. (PR #4)
- ✅ Verification stack — `npm test` covers typecheck, lint, pytest, and Playwright browser smoke tests; Next.js 16 migration synced into docs and routes.
- ✅ **Creator HQ revamp** — bio out of header, tabs horizontal, real brand icons (`react-icons/si`), deterministic platform sort, header Add Account button, AccountRow Remove action (soft-delete via `is_active=false`), Brand Summary placeholder for Phase 3, retry RPC platform-cast fix, 3 Next 16 sync-API regressions caught + fixed inline. (PR #4 polish pass)
- ✅ **`autonomous-fix-list` skill** added — when "full autonomy / use subagents / minimal input" phrase fires, runs the full plan → dispatch → verify → push playbook end-to-end with zero check-ins.
- ✅ **Always-on discovery worker** — `scripts/worker.py` runs as a macOS launchd user agent (`com.thehub.worker`). RunAtLoad + KeepAlive + ThrottleInterval=10s. New `scripts/worker_ctl.sh` for install/restart/log management. Logs at `~/Library/Logs/the-hub-worker.{log,err.log}`.
- ✅ **Live progress bar UI** — `discovery_runs.progress_pct/label` columns + `<DiscoveryProgress>` polling client component. 5 stages: Fetching profile → Resolving links → Analyzing → Saving → Done.
- ✅ **Discovery surface bugfix sweep** — retry RPC updates last_discovery_run_id, bulk_import platform cast, seed URL written on commit, novel-platform persistence (Wattpad/Substack stub rows), fetcher retry on transient Apify failures. pytest 102 → 107.
- ✅ **Recursive funnel resolver** (sync 14) — bounded follow-until-terminus expansion. Live smoke on Kira: 3 → 8 profiles. pytest 138.
- ✅ **Universal URL Harvester** (sync 15) — single entry `harvest_urls()`, 3-tier cascade (cache → httpx Tier 1 → Apify Puppeteer Tier 2 with window.open hooks + auto-click interstitials). New `url_harvest_cache` table (24 tables total). 10-value `DestinationClass`. Creator HQ "All Destinations" section. Live smoke captured Fanplace link behind 2-step Sensitive Content gate. 192 pytest. tsc 0.
- ✅ **Profile noise filter retroactive cleanup + UI polish** (sync 16, T16) — soft-deleted 30 stale noise rows; `is_noise_url(canon)` now drops noise URLs at the resolver gate before they become rows; `_commit_v2` URL-keyed dedup pass before RPC; PLATFORMS dict gains reddit/threads/bluesky/snapchat; unified `lucide Link` clip icon for all aggregators; All Destinations panel moved below tabs in collapsed `<details>`.
- ✅ **Specific platform identification + AccountRow restructure + banner foundation** (sync 16, T17) — Postgres `platform` enum +19 values to ~37 total; Pydantic Literal mirrored; gazetteer rewritten with 13 specific host→platform rules; AccountRow restructured (Column 1 = `[icon] [Platform Name]`, Column 2 = handle + display_name); 3 new `creators` columns (`cover_image_url` / `banner_url` / `override_avatar_url`) + `<BannerWithFallback>` component. All 5 creators re-discovered cleanly. Valentina's link.me + Fanfix + Cash App + Venmo coexist as 4 distinct rows — unique-key collision bug fixed. 227 pytest. tsc 0.
- ✅ **Handle normalization + regression-test ring + Gemini-enriched watchdog** (sync 17, T18 + T19 + T20) — T18 centralized `_normalize_handle(handle, platform)` at the `_commit_v2` chokepoint (35 case-insensitive platforms); `_r` + `lang` tracking-param strips; `_classify_linkme_redirector` runs FIRST in `classify()` so `?sensitiveLinkLabel=OF` URLs classify as `(onlyfans, monetization)` at confidence 1.0 (was `(linktree, link_in_bio)`). T19 added 13-test `test_commit_v2_dedup.py` + 2-test `test_platform_enum_drift.py` + `new_platform_watchdog` SQL view + PROJECT_STATE §21 invariants. T20 added 4 enriched-metadata columns to `classifier_llm_guesses`; LLM prompt rewritten; watchdog view replaced to JOIN those columns so VAs see Gemini's recommendation per host. Data migration: 5 duplicate rows soft-deleted, 7 active rows handle-normalized, Kira's link.me OF redirector reclassified retroactively. **249 pytest + 1 skip. tsc 0.**
- 🔜 SP1.1 — provision FB + X Apify actors (fetchers are stubbed)
- 🔜 Wire `/content` and `/trends` routes to live data
- 🔜 Phase 2 scraping pipeline (IG + TikTok normalizers, `flag_outliers` live, Outliers page)
- 🔜 Trend linking — audio signature extraction populates `scraped_content.trend_id`
- 🔜 `quality_flag` + `quality_reason` columns on `scraped_content` (runtime watchdog)
