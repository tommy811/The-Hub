# Phase 1 Overhaul — Design

**Date:** 2026-04-23
**Status:** Draft for review
**Owner:** Simon Lim
**Model:** Opus 4.7 for implementation
**Scope:** Audit and harden every layer of Phase 1 — schema, types, data access, server actions, components, pages — before Phase 2 starts.

---

## 1. Context

Phase 1 was largely scaffolded by Gemini and shipped with broken pieces — schema drift between live DB and docs, untyped queries, an anon-key fallback that masks RLS failures, a stub action file, non-functional UI controls (search, sort, single-handle import, merge buttons), sidebar param mismatches, and hardcoded mock data on the Command Center.

We are doing a strict bottom-up overhaul: lock down the data layer first, then build the UI on a proven foundation. No layer moves until the layer below has passed its verification gate.

## 2. Layer Architecture

Six layers, executed in order. Each has an explicit exit gate.

| # | Layer | Exit criteria |
|---|---|---|
| 1 | **Schema** | All 4 documented drift issues resolved. PROJECT_STATE §4 matches live DB exactly. `docs/SCHEMA.md` regenerated with zero drift. |
| 2 | **Generated artifacts** | `database.types.ts` regenerated. `npm run typecheck` passes. |
| 3 | **Data access** | Single canonical `getCurrentWorkspaceId()`. All reads via typed helpers in `src/lib/db/queries.ts`. No raw `.from()` in pages. Service client throws on missing service role key (no anon fallback). |
| 4 | **Server actions** | One actions file per route. Hardcoded `SYSTEM_USER_ID` for audit trail. All actions return `Result<T>`. `bulk_import_creator` RPC handles atomic creator+profile+run insert. |
| 5 | **Components** | All component prop types derived from generated DB types — no `any`. Every data-driven component has loading/empty/error states. |
| 6 | **Pages & routing** | Sidebar links resolve correctly. Search/sort wired to URL state. Mock data removed. Standardized filter param naming (`?tracking=`). |

**Out of scope** (deferred to their respective phases):
- Discovery pipeline rebuild (`httpx` → Apify) — Phase 2
- Apify ingestion / scraper pipeline — Phase 2
- Pending Phase 2 schema migration (trends, creator_label_assignments, archetype/vibe move) — Phase 2 entry
- Real Supabase Auth (login UI, session management) — Phase 4-ish
- Content analysis (Gemini scoring), brand analysis — Phase 3
- Funnel editor — Phase 4

---

## 3. Layer 1 — Schema

### 3.1 Drift fixes (one new migration)

| Drift | Decision |
|---|---|
| `creators.last_discovery_run_id` (no FK) **and** `last_discovery_run_id_fk` (FK) | Drop `last_discovery_run_id`, rename `last_discovery_run_id_fk` → `last_discovery_run_id`. Update RPC `commit_discovery_result` line 397 reference. |
| `trend_signals` live has `profile_id` — docs say `creator_id, account_id` | Live wins. Update docs. Creator derived via `profiles.creator_id`. |
| `alerts_feed` missing `creator_id` per docs | Live wins. Update docs. Creator derived via profile. |
| `discovery_runs` extra cols (`input_screenshot_path`, `funnel_edges_discovered_count`, `merge_candidates_raised`) | Live wins. Add to docs. |
| `content_analysis.archetype` is `text` not enum | Leave. Phase 2 drops the column entirely. |

### 3.2 Phase 2 migration: deferred

The pending Phase 2 migration (new `trends` table, `creator_label_assignments`, enum extensions, archetype/vibe move to creators, `trend_id` on scraped_content) stays pending. Reason: the tables are for features that don't exist yet. Building empty schema now would force assumptions before we know the actual Apify payload shape and audio-signature normalization rules.

### 3.3 Doc alignment + cleanup

- Update `PROJECT_STATE.md §4` to match live DB exactly.
- Remove `PROJECT_STATE.md §20` schema-drift row.
- Regenerate `docs/SCHEMA.md` via `npm run db:schema` — drift footer must be empty.
- Append the new drift-fix migration to `MIGRATION_LOG.md`.

### 3.4 Verification gate

- `npm run db:schema` produces SCHEMA.md with empty Drift section.
- `psql \d creators` shows exactly one `last_discovery_run_id` column with FK to `discovery_runs(id)`.
- Grep `last_discovery_run_id_fk` across `src/`, `scripts/`, `supabase/migrations/` → zero hits.

---

## 4. Layer 2 — Generated Artifacts

### 4.1 Regeneration

After Layer 1 lands:
- Run `npm run db:types` to regenerate `src/types/database.types.ts`.
- Run `npm run db:schema` to regenerate `docs/SCHEMA.md`.

### 4.2 Type re-exports

New file `src/types/db.ts`:
```ts
import type { Database } from './database.types'
export type Tables<T extends keyof Database['public']['Tables']> =
  Database['public']['Tables'][T]['Row']
export type Inserts<T extends keyof Database['public']['Tables']> =
  Database['public']['Tables'][T]['Insert']
export type Updates<T extends keyof Database['public']['Tables']> =
  Database['public']['Tables'][T]['Update']
export type Enums<T extends keyof Database['public']['Enums']> =
  Database['public']['Enums'][T]
```

App code imports from `@/types/db`, never from the generated file directly.

### 4.3 Verification gate

- `npm run typecheck` passes.
- A sample query (`from('creators').select('id, canonical_name')`) returns a fully typed result with autocomplete in IDE.

---

## 5. Layer 3 — Data Access

### 5.1 Five concrete fixes

| # | Problem | Fix |
|---|---|---|
| 1 | `createServiceClient()` falls back to anon key if service role key missing | Throw on missing key. No fallback. |
| 2 | Every page re-implements `getWorkspaceId()` | Single helper `src/lib/workspace.ts → getCurrentWorkspaceId()`, cached per-request via React `cache()`, throws if no workspace exists. |
| 3 | `workspace_id` filter is convention, not enforced | Typed query wrappers in `src/lib/db/queries.ts` — pages never call `.from()` directly. |
| 4 | `scraped_content` has no `workspace_id` column — JOIN required | `getScrapedContentForWorkspace(wsId, filters)` enforces the JOIN through `profiles`. |
| 5 | RPCs called via stringly-typed `supabase.rpc('name', ...)` | Wrapper module `src/lib/db/rpc.ts` with one typed function per RPC. |

### 5.2 File layout

```
src/lib/
  supabase/
    client.ts          # browser, typed
    server.ts          # cookie + service, typed, no fallback
  db/
    queries.ts         # workspace-scoped read helpers (split by domain — creators.ts, profiles.ts, content.ts — if it grows past ~300 lines)
    rpc.ts             # typed RPC wrappers
  workspace.ts         # getCurrentWorkspaceId() — cached
  auth.ts              # getCurrentUserId() — reads SYSTEM_USER_ID
src/types/
  db.ts                # Tables<>, Enums<> re-exports
  database.types.ts    # generated, do not import directly
```

### 5.3 Verification gate

- `npm run typecheck` passes.
- Grep `\.from\(` across `src/app/**` returns zero hits — all reads go through `src/lib/db/queries.ts`.
- Grep `NEXT_PUBLIC_SUPABASE_ANON_KEY` in `src/lib/supabase/server.ts` returns zero hits.
- Verifier subagent runs one read per route and confirms results are non-empty (or empty for the right reason).

---

## 6. Layer 4 — Server Actions + Auth

### 6.1 Auth scaffold (Option B — hardcoded system user)

- New env var `SYSTEM_USER_ID` pointing to a real row in `auth.users`.
- New env var `DEFAULT_WORKSPACE_ID` for `getCurrentWorkspaceId()` to read.
- New helper `src/lib/auth.ts → getCurrentUserId()` returns `SYSTEM_USER_ID`.
- Server actions pass this UUID as `p_user_id` / `p_resolver_id` to RPCs. Audit trail works ("system" appears as the actor).
- Future upgrade to real Supabase Auth touches only `getCurrentUserId()` — wrapper hides the source.

### 6.2 Result type for all actions

```ts
type Result<T> =
  | { ok: true; data: T }
  | { ok: false; error: string; code?: string }
```

UI must handle both branches. No silent failures.

### 6.3 New `actions.ts` structure

Delete `src/app/(dashboard)/creators/actions.ts` (dead code).

Move all actions into one file per logical surface:
- `src/app/(dashboard)/creators/actions.ts` (rebuilt fresh):
  - `bulkImportCreators(handles, trackingType, tags) → Result<{ imported, skipped, errors[] }>`
  - `importSingleCreator(platform, handle, url?) → Result<{ creatorId, slug }>`
  - `retryCreatorDiscovery(creatorId) → Result<{ runId }>`
  - `dismissMergeCandidate(candidateId) → Result<void>`
  - `mergeCandidateCreators(keepId, mergeId, candidateId) → Result<void>`
  - `addAccountToCreator(creatorId, profileData) → Result<{ profileId }>`

Delete `src/app/actions.ts` once all its actions have been moved into route-scoped action files and all imports updated. Verify zero remaining imports of `@/app/actions` before deletion.

Each action:
- Uses `createServiceClient()` (typed, no anon fallback).
- Calls `getCurrentUserId()` and `getCurrentWorkspaceId()`.
- Wraps DB calls in try/catch and returns `Result<T>`.
- camelCase naming throughout.
- Calls `revalidatePath()` after mutations.

### 6.4 New `bulk_import_creator` RPC

Atomic Postgres function — all inserts succeed or roll back. Replaces the JS-side `Promise.all` of inserts.

Signature:
```sql
bulk_import_creator(
  p_handle text,
  p_platform_hint platform,
  p_tracking_type tracking_type,
  p_tags text[],
  p_user_id uuid,
  p_workspace_id uuid
) → uuid  -- returns creator_id
```

Function body (transactional):
1. `SELECT normalize_handle(p_handle)` for slug derivation.
2. `INSERT INTO creators (...) RETURNING id` with `onboarding_status='processing'`, `tracking_type=p_tracking_type`, `tags=p_tags`, `added_by=p_user_id`, `import_source='bulk'`.
3. `INSERT INTO profiles (...)` with `creator_id=new.id`, `platform=p_platform_hint`, `handle=p_handle`, `account_type='social'`, `is_primary=true`, `added_by=p_user_id`.
4. `INSERT INTO discovery_runs (workspace_id=p_workspace_id, creator_id=new_creator.id, ...) RETURNING id` with `status='pending'`, `attempt_number=1`, `input_handle=p_handle`, `input_platform_hint=p_platform_hint`, `initiated_by=p_user_id`. (creator_id is NOT NULL and FKs to the creator inserted in step 2.)
5. `UPDATE creators SET last_discovery_run_id = new_run.id WHERE id = new_creator.id`. (Two-step insert is required because of the circular FK: discovery_runs.creator_id → creators.id, and creators.last_discovery_run_id → discovery_runs.id.)
6. Return `new_creator.id`.

Bulk import action loops over handles and calls this RPC once per handle. Errors are collected per handle, not aborted globally.

### 6.5 Verification gate

- `npm run typecheck` passes.
- Bulk-import 3 test handles → verifier confirms 3 `creators`, 3 `profiles`, 3 `discovery_runs` rows present, all linked correctly (`creators.last_discovery_run_id` set).
- Trigger an action that should fail (dismiss with bad UUID) → UI receives `{ ok: false, error: ... }`, shows error toast.
- Grep `console.error` in `src/app/**/actions.ts` returns zero hits — errors must propagate.

---

## 7. Layer 5 — Components

### 7.1 Broken behavior to fix

| # | Component | Issue | Fix |
|---|---|---|---|
| 1 | `BulkImportDialog` Single Handle tab | "Import Creator" button has no `onClick` | Wire to `importSingleCreator` action |
| 2 | `BulkImportDialog` props | Imports old `ParsedHandle` type from now-deleted file | Re-derive from new actions module |
| 3 | `CreatorsFilters` | Untyped `any` props | Use `Tables<'creators'>['Row']` derived type |
| 4 | `MergeAlertBanner` (in `creators/[slug]`) | "Merge" / "Not the same person" buttons non-functional | Wire to `mergeCandidateCreators` + `dismissMergeCandidate`, surface Result errors as toasts |
| 5 | Failed-state retry button in `creators/[slug]` (separate from `RerunDiscoveryButton`) | The `<Button>Retry</Button>` inside the red failed-state banner has no `onClick` | Wire to `retryCreatorDiscovery` |
| 5b | `RerunDiscoveryButton` | Works, but swallows errors via `console.error` | Update to consume `Result<T>` and surface error toast on `{ ok: false }` |
| 6 | Loading states | Most pages have no `loading.tsx` | Add for `/creators`, `/creators/[slug]`, `/platforms/instagram/accounts`, `/platforms/tiktok/accounts` |
| 7 | Empty states | Some routes blank-render | Standardize on `<EmptyState />` component |
| 8 | Error boundaries | None exist | Add `error.tsx` per dashboard route |
| 9 | `any` in props | Multiple spots | Derive prop types from generated DB types |

### 7.2 New shared components

- `src/components/ui/EmptyState.tsx` — icon, title, description, optional CTA. Used everywhere data may be empty.
- `src/components/ui/ErrorState.tsx` — for `error.tsx` boundaries.
- `src/components/shared/ComingSoon.tsx` — for placeholder sub-routes (Phase 2/3/4 pages). Takes `phase` prop, shows "Coming in Phase X" with consistent visual treatment.

---

## 8. Layer 6 — Pages & Routing

### 8.1 Search and sort wiring (`/creators`)

- Search input: wire to URL state (`?q=`). Server-side filter `canonical_name ILIKE %q%`.
- Sort dropdown: wire to URL state (`?sort=recently_added|name_asc|platform`). Server-side `.order()`.

### 8.2 Sidebar standardization

| Issue | Fix |
|---|---|
| Sidebar uses `?type=managed` but page reads `?tracking=` | Standardize on `?tracking=`. Update sidebar links. |
| Duplicate `/content` route (Daily "Content Hub" + Analyze "Content") | Keep "Content Hub" only. Remove "Content" from Analyze. |
| TikTok Intel header has no children | Add child links matching Instagram structure. Existing real route: `/platforms/tiktok/accounts`. Create three new placeholder page files (`/platforms/tiktok/outliers/page.tsx`, `/classification/page.tsx`, `/analytics/page.tsx`), each rendering `<ComingSoon phase="2" />` (or appropriate phase). Sub-items in sidebar show with "Soon" badge. |
| Instagram sub-nav links to placeholder pages | Keep links visible with "Soon" badge. Each placeholder page renders `<ComingSoon phase="2" />` etc. |

### 8.3 Command Center mock data removal

- Outliers feed: replace hardcoded items with `getRecentOutliersForWorkspace(wsId, limit=5)` against `scraped_content` where `is_outlier=true` ordered by `outlier_multiplier desc`. Empty state: "No outliers yet — Phase 2 will populate this when scraping starts."
- Trend Signals feed: `getActiveTrendSignalsForWorkspace(wsId, limit=5)` from `trend_signals` where `is_dismissed=false`. Same empty state pattern.
- "Avg Quality Score": real `AVG(current_score)` from `profile_scores`. Empty state shows "—" with subtitle "No scores yet."
- "Posts Ingested" count: scope by workspace via the new `getScrapedContentForWorkspace` helper.

### 8.4 Platform pages

Both `/platforms/instagram/accounts` and `/platforms/tiktok/accounts`:
- Replace `?type=` with `?tracking=` in both the page's `searchParams` TypeScript signature AND the client component prop names (`activeType` → `activeTracking`).
- Inline workspace lookup + JOIN replaced by `getProfilesWithStatsForWorkspace(wsId, { platform, accountType: 'social' })`.
- Update `TrackingTabBar` consumers if its prop name `onTabChange` ties to the old param name.

### 8.5 Creator detail page

- Merge banner buttons — wired (per Layer 5).
- Retry button on failed state — wired (per Layer 5).
- Funnel tab: leave as Phase 4 placeholder, but use `<ComingSoon phase="4" />` for consistency.
- Content/Branding tabs: leave as Phase 3 placeholders, use `<ComingSoon phase="3" />`.

### 8.6 Verification gate

- Click every sidebar link, every filter chip, every action button → no broken links, no non-functional buttons.
- Bulk-import 3 test handles → 3 cards appear, profiles attached, all `processing`, `last_discovery_run_id` set.
- Click "Re-run Discovery" → new `discovery_runs` row with `attempt_number=2`.
- Search "test" → URL updates to `?q=test`, results filter.
- Sort by "Name (A-Z)" → URL updates to `?sort=name_asc`, order changes.
- Verifier subagent navigates each route via chrome-devtools-mcp, captures console errors, confirms zero `[Error]` logs.

---

## 9. Verification Strategy

Each layer ends with the verifier subagent (read-only, no edit tools) running its gate's checks. Implementation does not advance to the next layer until verification passes.

The Stop hook (per CLAUDE.md) ensures no task is marked complete without verifier sign-off.

For UI work in Layers 5–6, verification additionally uses `chrome-devtools-mcp` to navigate routes in a real browser and capture console output, network failures, and accessibility regressions.

## 10. Out of Scope (Reaffirmed)

- Discovery pipeline rebuild (Python, `httpx` → Apify)
- Apify scraping ingestion
- Phase 2 schema migration (trends, creator labels, archetype/vibe move)
- Real Supabase Auth (login UI, session management)
- Content/brand analysis pipelines
- Funnel editor

These all remain on the Phase 2/3/4 roadmap as documented in `PROJECT_STATE.md §14`.

## 11. Decisions Log

| Decision | Choice | Reason |
|---|---|---|
| Approach | Bottom-up layer sweep | Schema and query issues cut across every screen — fix at the source. |
| Phase 2 schema | Deferred | No real ingestion shape yet to design against. |
| Drop redundant `last_discovery_run_id` column | Yes | Eliminates ambiguity. Cleaner than maintaining both. |
| Denormalize `creator_id` on `trend_signals` / `alerts_feed` | No | Keep lean. Derive via profile JOIN. |
| Query access pattern | Wrappers in `src/lib/db/queries.ts`, no raw `.from()` in pages | Structural, not lint-rule-bound. |
| Auth | Hardcoded `SYSTEM_USER_ID` env var (Option B) | Unblocks RPCs without heavyweight Auth build. Wrapper hides source for future swap. |
| Atomic bulk import | New `bulk_import_creator` RPC | Atomicity belongs in the DB. |
| Placeholder Instagram sub-routes | Keep visible with "Soon" badge (Option 3) | Honest, signals intent, matches existing pattern. |

---

## 12. Next Step

After user review of this spec, hand off to the `superpowers:writing-plans` skill to break each layer into an executable, testable implementation plan.
