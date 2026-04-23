# Phase 1 — Foundation & Creators Prompt

> Reference copy of the prompt used to generate the Creators hub.
> Full prompt is in the downloadable `creators-page-prompt.md` file.

## What It Builds
- src/lib/platforms.ts — platform enum → display metadata mapping
- src/lib/handleParser.ts — URL/handle parser for bulk import
- src/app/(dashboard)/creators/page.tsx — creators grid + bulk import
- src/app/(dashboard)/creators/actions.ts — server actions
- src/app/(dashboard)/creators/[slug]/page.tsx — creator deep-dive
- src/components/creators/CreatorCard.tsx — 3 states (Processing/Ready/Failed)
- src/components/creators/BulkImportDialog.tsx — bulk paste + single handle
- src/components/creators/HandleChipPreview.tsx — live parse preview chips
- src/components/creators/StatusTabBar.tsx — All/Processing/Ready/Failed/Archived
- src/components/creators/MergeAlertBanner.tsx — amber duplicate alert
- src/components/accounts/PlatformIcon.tsx — lucide icon per platform
- src/components/accounts/AccountRow.tsx — network tab account rows
- src/components/dashboard/Sidebar.tsx — MODIFIED with Creators section
- scripts/discover_creator.py — Gemini discovery pipeline
- scripts/worker.py — polling worker
- scripts/common.py — shared utilities
- supabase/functions/trigger-discovery/index.ts — Edge Function

## Key Constraints Given to the AI
- Do NOT regenerate existing files (listed all existing paths)
- Match existing dark aesthetic: bg-[#0A0A0F], bg-[#13131A], border-white/[0.06]
- Use only already-installed shadcn components
- TypeScript strict, zero any without justification
- Every file has top-of-file comment explaining its role
- Realtime subscriptions on: creators, discovery_runs, creator_merge_candidates

## Database Context Provided
Full schema of both original + creator layer tables, all enum values,
all RPC signatures, Realtime config.
