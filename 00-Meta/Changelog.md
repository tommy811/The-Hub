# Changelog

## 2026-04-23 (sync 6 — agent architecture integration)
- Added: Agent architecture §15–§19 to PROJECT_STATE.md (replacing §15 Agent Roadmap stub)
- Added: 04-Pipeline/Agent Catalog.md with operational entries for all planned agents
- Installed: superpowers, chrome-devtools-mcp, playwright-mcp, apify-mcp, supabase-mcp (read-only), anthropics/skills
- Created: .claude/agents/verifier.md subagent (read-only tools, structured pass/fail output)
- Created: .claude/hooks/verify-before-stop.sh Stop hook
- Updated: .claude/settings.json with Stop hook registration
- Created: CLAUDE.md with verification protocol
- Updated: scripts/.env.example with Sentry, Slack, and Apify webhook vars
- Updated: Stack & Tools.md — superpowers and webapp-testing added to skills table
- Updated: PROJECT_STATE.md §13 — agent dir path updated to .claude/agents/, reference updated to §15–§19

## 2026-04-23 (agent roadmap)
- Added: §15 Agent Roadmap in PROJECT_STATE.md — formal table of 8 agents across Phases 1–4 + ongoing
- Added: Required Agents column in Full Product Vision module map — every module now lists its agents
- Added: Per-phase Required Agents subsections in Phase Roadmap — each phase has explicit agent completion criteria
- Added: Agent Backlog section at top of Feature Backlog — 8 agents listed, verify-and-fix marked as Phase 1 blocking
- Added: Workflow patterns #7, #8, #9 in Stack & Tools (schema-first/agent-last, agents as deliverables, verify before done)
- Added: Planned agents note in Stack & Tools Claude Code Skills section
- Added: Principle #10 in Stack & Tools project principles (agents are phase deliverables)
- Added: 04-Pipeline/Agent Catalog.md — new file with full spec for all 8 planned agents including workflows, triggers, escalation rules, design principles
- Added: Cross-Module Decision #9 in Full Product Vision (every phase ships with its agents)
- Added: Agent development cadence line in PROJECT_STATE.md §13 Development Workflow
- Changed: Phase 1 status in Phase Roadmap — marked "feature work complete" with ⚠️ note that verify-and-fix is still blocking full phase close
- Decision: Phases close only when required agents are built + validated. verify-and-fix is next build.

## 2026-04-23 (sync 5)
- Added: `AvatarWithFallback.tsx` — client component with `onError` → gradient monogram fallback. Fixes silent blank when Instagram CDN URLs expire. Used on creator cards + detail page.
- Added: `AddAccountDialog.tsx` — manual add account dialog. 18 platforms grouped (Social / Monetization / Link-in-Bio / Messaging / Other). Auto-sets account_type from platform selection. Wired to `addProfileToCreator` server action.
- Added: `RerunDiscoveryButton.tsx` — wired Re-run Discovery button. Calls `rerunCreatorDiscovery` server action → `retry_creator_discovery` RPC.
- Changed: Creator detail page (`/creators/[slug]`) — full revamp. Stats strip (Total Reach, Social count, Monetization count, Link-in-Bio count), bio from primary profile, network sections with icons, avatar fallback, fetches `bio`/`following_count`/`post_count` from profiles.
- Changed: `creators/page.tsx` — real follower count aggregation, account type breakdown per creator card, `totalFollowers` computed from social profiles.
- Fixed: Apify field names in `apify_scraper.py` — `followersCount` (not `ownerFollowers`), `profilePicUrl` (not `ownerProfilePicUrl`), `biography`, `followsCount`, `postsCount`, `ownerFullName`, `metaData` fallback. Follower counts now populate correctly.
- Fixed: `retry_creator_discovery` RPC — now copies `input_handle` + `input_platform_hint` so retry runs have context to work with.
- Fixed: `commit_discovery_result` RPC — `NULLIF` guard prevents "Unknown" from overwriting valid canonical_name.
- Fixed: `AccountRow.tsx` — hydration error from `toLocaleDateString()` → deterministic `toISOString().slice(0, 10)`.
- Known: Instagram CDN avatar URLs expire. `onError` degrades gracefully to gradient monogram. Full fix requires re-scraping or proxying to Supabase Storage.
- Known: Discovery pipeline `httpx.get()` is blocked by Instagram. Gemini fishnet does not work until discover_creator.py is rebuilt on Apify `resultsType: "details"`. Documented in §15 Known Limitations.

## 2026-04-23 (sync 4)
- Added: `/platforms/tiktok/accounts` wired to live Supabase — Server Component + `TikTokAccountsClient.tsx`, mirrors Instagram pattern exactly (platform=tiktok, account_type=social)
- Added: `supabase/migrations/20260423000000_add_is_primary_to_profiles.sql` — `is_primary BOOLEAN DEFAULT FALSE` on profiles (required by `commit_discovery_result` RPC)
- Fixed: Discovery pipeline end-to-end — Gemini 2.5 Flash schema compatibility (strip minimum/maximum/anyOf), monetization_model normalization, dependency conflict resolved
- Fixed: All 3 initial creators (Natalie Vox, Aria Swan, Esmae) discovered and in `ready` state; 10 posts scraped via Apify
- Changed: Gemini model in use updated from `gemini-1.5-pro` → `gemini-2.5-flash` (1.5-pro deprecated)
- Changed: `creators/page.tsx` and `page.tsx` (dashboard) marked `force-dynamic` to prevent stale server cache

## 2026-04-23 (sync 3)
- Added: `/platforms/instagram/accounts` wired to live Supabase — Server Component fetches `profiles` (platform=instagram, account_type=social), joins `profile_scores`, `profile_metrics_snapshots`, `scraped_content`; client component handles tracking tab (URL), rank chips, search, sort, stat cards
- Added: `InstagramAccountsClient.tsx` — new client component for IG accounts filtering/sorting
- Changed: `AccountCard` — removed `fanArchetype`, `archetype`, `vibe`, `category` props; added `isUnlinked` badge; nullable `rank`/`score`/`avatarUrl`
- Changed: `StatCardRow` — now accepts live props (total, withContent, avgFollowers, llmScored) instead of hardcoded mock values
- Changed: `TikTok accounts page` — updated to new component signatures (still placeholder mock data)

## 2026-04-23 (additional)
- Added: Stack & Tools.md (00-Meta/) — complete tool/service/skill/MCP/workflow reference
- Added: sync-project-state skill (.claude/skills/sync-project-state/SKILL.md)
- Added: Stack & Tools quick link to Home.md
- Fixed: table count (20 → 18) in PROJECT_STATE.md, mirror, and Phase Roadmap

## 2026-04-23
- Full repo + vault audit completed
- Applied all audit fixes: RPC param prefix bug, invalid `scored` enum value, outlier threshold copy (2x→3×), orphan script deleted
- Added `outlier_multiplier` column migration + rewrote `flag_outliers` RPC
- Added patreon to platforms.ts
- Rewrote README.md from AI Studio boilerplate to real project README
- Added §15 Known Limitations to PROJECT_STATE.md
- All reference docs updated: Enum Reference, RPC Reference, Migration Log, Entity Relationships
- Full Product Vision.md added (all 9 modules)
- Phase 1 marked complete across all docs

## 2026-04-22
- Vault created
- Initial schema applied to Supabase (Content OS)
- Creator layer migration applied
- Phase 1 AI Studio prompt generated
