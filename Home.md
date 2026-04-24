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
- Phase: **Phase 2 in progress 🔄** — Discovery v2 live; verification stack synced; scraping + trends + content/trends routes next
- Database: ✅ Supabase (Content OS project) — 23 tables live
- Repo: github.com/tommy811/The-Hub
- Open PR: [#4 phase-2-discovery-v2](https://github.com/tommy811/The-Hub/pull/4) — Discovery v2
- Last session: [[06-Sessions/2026-04-24]]

## Active Work
- ✅ Discovery pipeline rebuilt — Apify-grounded context, Linktree/Beacons resolver, grounded Gemini prompt, dead-letter retry, 45 pytest tests (PR #2)
- ✅ Phase 2 schema migration — `trends` + `creator_label_assignments`, `trend_type` / `llm_model` / `content_archetype` enums, `creators.archetype`+`vibe`, `scraped_content.trend_id` (PR #3)
- ✅ **Discovery v2 (SP1)** — two-stage resolver, deterministic classifier, rule-cascade identity scorer, 9 platform fetchers (IG/TT/YT/Patreon/OF/Fanvue/generic + FB/X stubs), `bulk_imports` observable job, cross-workspace dedup every commit, Manual Add Account triggers resolver expansion. 102 pytest tests. Live smoke passed. (PR #4)
- ✅ Verification stack — `npm test` covers typecheck, lint, pytest, and Playwright browser smoke tests; Next.js 16 migration synced into docs and routes.
- 🔜 SP1.1 — provision FB + X Apify actors (fetchers are stubbed)
- 🔜 Wire `/content` and `/trends` routes
- 🔜 Phase 2 scraping pipeline (IG + TikTok normalizers, `flag_outliers` live, Outliers page)
- 🔜 Trend linking — audio signature extraction populates `scraped_content.trend_id`
- 🔜 `quality_flag` + `quality_reason` columns on `scraped_content` (runtime watchdog)
