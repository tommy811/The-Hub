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
- Phase: **1 complete → Phase 2 starting**
- Database: ✅ Supabase (Content OS project)
- Repo: github.com/tommy811/The-Hub
- Last session: [[06-Sessions/2026-04-23]]

## Active Work
- ✅ `/platforms/instagram/accounts` — live Supabase data
- ✅ `/platforms/tiktok/accounts` — live Supabase data (mirrored from Instagram)
- ✅ Re-run Discovery button — wired end-to-end
- ✅ Manual Add Account dialog — functional with 18 platforms
- ✅ Creator detail page — revamped (stats strip, bio, avatar fallback)
- ✅ Apify field mapping fixed — follower counts backfilled
- 🔜 **Build verify-and-fix agent** (Phase 1 retroactive — blocking phase close)
- 🔜 Phase 2 first task: rebuild discover_creator.py on Apify (httpx blocked by Instagram)
- 🔜 Wire `/content` and `/trends` routes
- 🔜 Phase 2 scraping pipeline (IG + TikTok normalizers, flag_outliers live)
