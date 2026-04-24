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
- Phase: **Phase 2 in progress 🔄** (schema landed; pipeline rebuild next)
- Database: ✅ Supabase (Content OS project) — 20 tables live
- Repo: github.com/tommy811/The-Hub
- Open PR: [#3 phase-2-schema-migration](https://github.com/tommy811/The-Hub/pull/3)
- Last session: [[06-Sessions/2026-04-24]]

## Active Work
- ✅ Phase 2 schema migration — `trends` + `creator_label_assignments`, `trend_type` / `llm_model` / `content_archetype` enums, `creators.archetype`+`vibe`, `scraped_content.trend_id`
- 🔜 **Phase 2 first task:** rebuild `scripts/discover_creator.py` on Apify `resultsType: "details"` — `httpx` is blocked by Instagram
- 🔜 Wire `/content` and `/trends` routes
- 🔜 Phase 2 scraping pipeline (IG + TikTok normalizers, `flag_outliers` live, Outliers page)
- 🔜 Trend linking — audio signature extraction populates `scraped_content.trend_id`
