# Prompt Log

## How to Use This Log
After every AI Studio or Claude session that produces code or architecture decisions,
log it here. This prevents losing context between sessions.

---

## 2026-04-22 — Phase 1 Initial Prompt (older version)
**Tool:** Google AI Studio (Gemini)
**Output:** Initial Hub codebase — IG/TikTok accounts pages, rank badges, sidebar, AccountCard, TrackingTabBar, RankFilterChips, ingest.py stub
**Architecture at that point:** Platform-first (profiles table only, no creator entity)
**Gaps identified:** No creator layer, no bulk import, no identity resolution

---

## 2026-04-22 — Creator Layer Prompt
**Tool:** Google AI Studio (Gemini)
**Prompt file:** [[Phase1-Foundation]] (creators-page-prompt.md)
**Status:** 🔄 Running
**Expecting output:**
1. src/lib/platforms.ts
2. src/lib/handleParser.ts
3. src/app/(dashboard)/creators/page.tsx
4. src/app/(dashboard)/creators/actions.ts
5. src/app/(dashboard)/creators/[slug]/page.tsx
6. src/components/creators/CreatorCard.tsx (3 states)
7. src/components/creators/BulkImportDialog.tsx
8. src/components/creators/HandleChipPreview.tsx
9. src/components/creators/StatusTabBar.tsx
10. src/components/creators/MergeAlertBanner.tsx
11. src/components/accounts/PlatformIcon.tsx
12. src/components/accounts/AccountRow.tsx
13. src/components/dashboard/Sidebar.tsx (modified)
14. scripts/discover_creator.py
15. scripts/worker.py
16. scripts/common.py
17. scripts/requirements.txt
18. scripts/.env.example
19. supabase/functions/trigger-discovery/index.ts

---

## Prompt Lessons Learned
- Always paste PROJECT_STATE.md at top of any new AI session
- Specify "do not regenerate existing files" explicitly — list them
- Field mappings must be in the prompt itself — AI won't infer Apify field names
- Schema must come before UI — DB is the contract everything else references
- Split large prompts into phases — AI Studio loses quality after ~5000 tokens of output
- Use `IF NOT EXISTS` everywhere in SQL — makes re-runs safe
- `ALTER TYPE ADD VALUE` cannot run inside a transaction — apply separately
