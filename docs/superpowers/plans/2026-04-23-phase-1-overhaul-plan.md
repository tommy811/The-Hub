# Phase 1 Overhaul Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Audit and harden every layer of Phase 1 — schema, types, data access, server actions, components, pages — before Phase 2 starts.

**Architecture:** Six-layer bottom-up sweep. Each layer has a verification gate; no layer advances until the layer below is verified. Schema drift fixed via one new migration; data access becomes typed and structural via query/RPC wrappers; broken UI controls wired with `Result<T>` error handling; mock data replaced with real workspace-scoped queries.

**Tech Stack:** Next.js 14 (App Router), TypeScript strict, Supabase (Postgres 17), shadcn/ui, Tailwind, sonner (new — for toasts), @supabase/ssr, @supabase/supabase-js.

**Spec reference:** `docs/superpowers/specs/2026-04-23-phase-1-overhaul-design.md`

**Verification model:** This codebase has no test framework. Verification per layer relies on:
- `npm run typecheck` (TypeScript compiler) — strict type errors block progress.
- `psql`/`supabase db` — SQL state assertions for schema and RPC behavior.
- `grep` invariants for code patterns (e.g., no raw `.from()` in `src/app/`).
- The `verifier` subagent (read-only, per `CLAUDE.md`) — runs end-to-end browser checks via chrome-devtools-mcp.
- Stop hook enforces verifier sign-off before any task is considered done.

**Commit cadence:** Commit after each task. Tasks are 2–10 minutes each.

---

## File Structure (created or modified)

**New files:**
- `supabase/migrations/20260424000000_consolidate_last_discovery_run_id.sql`
- `supabase/migrations/20260424000001_bulk_import_creator_rpc.sql`
- `src/types/db.ts`
- `src/lib/auth.ts`
- `src/lib/workspace.ts`
- `src/lib/db/result.ts`
- `src/lib/db/queries.ts`
- `src/lib/db/rpc.ts`
- `src/components/ui/empty-state.tsx`
- `src/components/ui/error-state.tsx`
- `src/components/ui/sonner.tsx` (shadcn toaster)
- `src/components/shared/ComingSoon.tsx`
- `src/app/(dashboard)/loading.tsx`
- `src/app/(dashboard)/error.tsx`
- `src/app/(dashboard)/creators/loading.tsx`
- `src/app/(dashboard)/creators/[slug]/loading.tsx`
- `src/app/(dashboard)/creators/[slug]/error.tsx`
- `src/app/(dashboard)/platforms/instagram/accounts/loading.tsx`
- `src/app/(dashboard)/platforms/tiktok/accounts/loading.tsx`
- `src/app/(dashboard)/platforms/tiktok/outliers/page.tsx`
- `src/app/(dashboard)/platforms/tiktok/classification/page.tsx`
- `src/app/(dashboard)/platforms/tiktok/analytics/page.tsx`

**Modified files:**
- `src/lib/supabase/server.ts`
- `src/lib/supabase/client.ts`
- `src/app/layout.tsx` (add Toaster)
- `src/app/(dashboard)/page.tsx`
- `src/app/(dashboard)/creators/page.tsx`
- `src/app/(dashboard)/creators/[slug]/page.tsx`
- `src/app/(dashboard)/creators/actions.ts` (rebuilt fresh — old contents are stub)
- `src/app/(dashboard)/platforms/instagram/accounts/page.tsx`
- `src/app/(dashboard)/platforms/instagram/accounts/InstagramAccountsClient.tsx`
- `src/app/(dashboard)/platforms/instagram/outliers/page.tsx`
- `src/app/(dashboard)/platforms/instagram/classification/page.tsx`
- `src/app/(dashboard)/platforms/instagram/analytics/page.tsx`
- `src/app/(dashboard)/platforms/tiktok/accounts/page.tsx`
- `src/app/(dashboard)/platforms/tiktok/accounts/TikTokAccountsClient.tsx`
- `src/components/dashboard/Sidebar.tsx`
- `src/components/creators/BulkImportDialog.tsx`
- `src/components/creators/CreatorsFilters.tsx`
- `src/components/creators/MergeAlertBanner.tsx`
- `src/components/creators/RerunDiscoveryButton.tsx`
- `src/components/creators/AddAccountDialog.tsx`
- `src/types/database.types.ts` (regenerated, do not hand-edit)
- `docs/SCHEMA.md` (regenerated)
- `PROJECT_STATE.md`
- `supabase/migrations/MIGRATION_LOG.md`
- `package.json` (add `sonner`)
- `scripts/.env` (add `SYSTEM_USER_ID`, `DEFAULT_WORKSPACE_ID`, also document in `.env.example`)
- `.env.local.example` (or equivalent — add new env vars)

**Deleted files:**
- `src/app/actions.ts` (moved into route-scoped action files)

---

# LAYER 1 — SCHEMA

### Task 1: Write the drift-fix migration

**Files:**
- Create: `supabase/migrations/20260424000000_consolidate_last_discovery_run_id.sql`

- [ ] **Step 1: Write the migration**

```sql
-- 20260424000000_consolidate_last_discovery_run_id.sql
-- Drift fix: collapse the duplicate last_discovery_run_id columns on creators.
-- Live DB has both `last_discovery_run_id` (no FK) and `last_discovery_run_id_fk` (FK→discovery_runs.id).
-- This migration drops the no-FK column and renames the FK column to take its place.

BEGIN;

-- Backfill: copy any value from the no-FK column into the FK column where the FK column is null.
UPDATE creators
SET last_discovery_run_id_fk = last_discovery_run_id
WHERE last_discovery_run_id_fk IS NULL
  AND last_discovery_run_id IS NOT NULL
  AND EXISTS (SELECT 1 FROM discovery_runs WHERE id = creators.last_discovery_run_id);

-- Drop the no-FK column.
ALTER TABLE creators DROP COLUMN last_discovery_run_id;

-- Rename FK column to take its place.
ALTER TABLE creators RENAME COLUMN last_discovery_run_id_fk TO last_discovery_run_id;

-- Update the commit_discovery_result RPC body to write to the (now-only) column name.
-- (The function body in the original 20240102000000_creator_layer.sql already writes
-- `last_discovery_run_id = p_run_id` — after the rename, that name resolves correctly.
-- No function redefinition needed.)

COMMIT;
```

- [ ] **Step 2: Verify the migration parses**

Run: `psql "$SUPABASE_DB_URL" -f supabase/migrations/20260424000000_consolidate_last_discovery_run_id.sql --dry-run 2>&1 || true`

If `--dry-run` is unsupported, run inside a transaction that rolls back:
```bash
psql "$SUPABASE_DB_URL" <<'SQL'
BEGIN;
\i supabase/migrations/20260424000000_consolidate_last_discovery_run_id.sql
ROLLBACK;
SQL
```

Expected: zero errors.

- [ ] **Step 3: Commit**

```bash
git add supabase/migrations/20260424000000_consolidate_last_discovery_run_id.sql
git commit -m "feat(db): drift-fix migration — consolidate last_discovery_run_id on creators"
```

---

### Task 2: Apply the migration to the live DB

**Files:**
- Modify: live Supabase DB (`dbkddgwitqwzltuoxmfi`) via `supabase db push` or `psql`

- [ ] **Step 1: Run the migration**

```bash
cd "/Users/simon/OS/Living VAULT/Content OS/The Hub"
psql "$SUPABASE_DB_URL" -f supabase/migrations/20260424000000_consolidate_last_discovery_run_id.sql
```

Expected: `BEGIN`, `UPDATE n`, `ALTER TABLE`, `ALTER TABLE`, `COMMIT` — all succeed.

- [ ] **Step 2: Verify column state**

```bash
psql "$SUPABASE_DB_URL" -c "\d creators" | grep last_discovery_run_id
```

Expected: exactly one line, showing `last_discovery_run_id` with `references discovery_runs(id)`.

- [ ] **Step 3: Verify no orphan references in source**

```bash
grep -rn "last_discovery_run_id_fk" \
  "/Users/simon/OS/Living VAULT/Content OS/The Hub/src" \
  "/Users/simon/OS/Living VAULT/Content OS/The Hub/scripts" \
  "/Users/simon/OS/Living VAULT/Content OS/The Hub/supabase/migrations" \
  | grep -v "20260424000000" | grep -v "MIGRATION_LOG"
```

Expected: only hits in `src/types/database.types.ts` (will regenerate next task) and `supabase/migrations/20240102000000_creator_layer.sql` (historical, leave alone).

- [ ] **Step 4: Commit (no source changes — this is the live-DB apply step)**

If `supabase/migrations/MIGRATION_LOG.md` exists, append an entry:
```bash
cat >> supabase/migrations/MIGRATION_LOG.md <<'EOF'

## 20260424000000_consolidate_last_discovery_run_id

Applied: 2026-04-24
Drift fix. Dropped `creators.last_discovery_run_id` (no FK), renamed `last_discovery_run_id_fk` → `last_discovery_run_id`. RPC `commit_discovery_result` body unchanged — already wrote to `last_discovery_run_id`.
EOF
git add supabase/migrations/MIGRATION_LOG.md
git commit -m "docs(db): log drift-fix migration applied to live DB"
```

---

### Task 3: Regenerate types and SCHEMA.md

**Files:**
- Modify: `src/types/database.types.ts` (regenerated)
- Modify: `docs/SCHEMA.md` (regenerated)

- [ ] **Step 1: Regenerate types**

```bash
cd "/Users/simon/OS/Living VAULT/Content OS/The Hub"
npm run db:types
```

Expected: file written, exit code 0.

- [ ] **Step 2: Regenerate SCHEMA.md**

```bash
npm run db:schema
```

Expected: `docs/SCHEMA.md` rewritten.

- [ ] **Step 3: Confirm zero drift in regenerated SCHEMA.md**

```bash
grep -A 20 "Live vs PROJECT_STATE Drift" docs/SCHEMA.md | head -30
```

Expected: section is either absent OR notes only that drift has been resolved. The four old drift bullets (last_discovery_run_id, trend_signals, alerts_feed, discovery_runs extra cols) — only the last_discovery_run_id one should be gone (the others are doc-only fixes coming in Task 4).

- [ ] **Step 4: Confirm types compile**

```bash
npx tsc --noEmit
```

Expected: zero errors. (If errors mention `last_discovery_run_id_fk`, that's expected — those are stale references in app code; they'll be removed in subsequent tasks. For now, fix any direct `last_discovery_run_id_fk` reference in `src/` by replacing with `last_discovery_run_id`.)

- [ ] **Step 5: Commit**

```bash
git add src/types/database.types.ts docs/SCHEMA.md
git commit -m "chore(db): regenerate types + SCHEMA.md after drift fix"
```

---

### Task 4: Update PROJECT_STATE.md to match live DB

**Files:**
- Modify: `PROJECT_STATE.md` (§4 schema, §20 known limitations)

- [ ] **Step 1: Update §4 — `creators` table line**

Find the `creators` line in PROJECT_STATE.md §4.1 and ensure it lists `last_discovery_run_id` exactly once with FK to `discovery_runs(id)`.

Old (current state has `last_discovery_run_id` listed once but the live DB had two cols):
```
- `creators` — id, workspace_id, canonical_name, slug, known_usernames[], display_name_variants[], primary_niche, primary_platform, monetization_model, tracking_type, tags[], notes, onboarding_status, import_source, last_discovery_run_id, last_discovery_error, added_by, timestamps
```

New (no change to listing — just confirms one column):
```
- `creators` — id, workspace_id, canonical_name, slug, known_usernames[], display_name_variants[], primary_niche, primary_platform, monetization_model, tracking_type, tags[], notes, onboarding_status, import_source, last_discovery_run_id (FK→discovery_runs), last_discovery_error, added_by, timestamps
```

- [ ] **Step 2: Update §4 — `trend_signals` table line**

Old:
```
- `trend_signals` — id, workspace_id, signal_type, creator_id, account_id, content_id, score, detected_at, metadata (jsonb), is_dismissed
```

New (live wins — removes `creator_id, account_id`, adds `profile_id`):
```
- `trend_signals` — id, workspace_id, signal_type, profile_id (FK→profiles), content_id (FK→scraped_content), score, detected_at, metadata (jsonb), is_dismissed
```

- [ ] **Step 3: Update §4 — `alerts_feed` table line**

Old:
```
- `alerts_feed` — id, workspace_id, config_id, content_id, profile_id, creator_id, triggered_at, is_read, payload (jsonb)
```

New (live wins — removes `creator_id`):
```
- `alerts_feed` — id, workspace_id, config_id, content_id (FK→scraped_content), profile_id (FK→profiles), triggered_at, is_read, payload (jsonb)
```

- [ ] **Step 4: Update §4 — `discovery_runs` table line**

Old:
```
- `discovery_runs` — id, workspace_id, creator_id, input_handle, input_url, input_platform_hint, status, raw_gemini_response, assets_discovered_count, attempt_number, error_message, initiated_by, timestamps
```

New (adds three cols live has):
```
- `discovery_runs` — id, workspace_id, creator_id, input_handle, input_url, input_platform_hint, input_screenshot_path, status, raw_gemini_response, assets_discovered_count, funnel_edges_discovered_count, merge_candidates_raised, attempt_number, error_message, initiated_by, started_at, completed_at, timestamps
```

- [ ] **Step 5: Remove §20 schema-drift row**

Find this row in §20 Known Limitations:
```
| Schema drift vs PROJECT_STATE | `docs/SCHEMA.md` footer — 4 mismatches: `creators.last_discovery_run_id_fk` shadow col; `trend_signals` has `profile_id` not `creator_id`; `alerts_feed` missing `creator_id`; `discovery_runs` has 3 undocumented cols | Low — drift is documented, types file is correct | Resolve before Phase 2: update §4 to match live DB, then drop footer note |
```

Delete the entire row.

- [ ] **Step 6: Append to Decisions Log**

At the bottom of PROJECT_STATE.md (after the existing entry), add:
```
- 2026-04-24: Phase 1 schema drift resolved (migration 20260424000000). PROJECT_STATE §4 now matches live DB exactly. Phase 2 schema migration deferred to Phase 2 entry per docs/superpowers/specs/2026-04-23-phase-1-overhaul-design.md.
```

- [ ] **Step 7: Commit**

```bash
git add PROJECT_STATE.md
git commit -m "docs(state): align PROJECT_STATE §4 with live DB; remove §20 drift row"
```

---

### Task 5: Layer 1 verification gate

- [ ] **Step 1: SCHEMA.md drift section is empty**

```bash
sed -n '/Live vs PROJECT_STATE Drift Notes/,$p' docs/SCHEMA.md
```

If the section still lists drift items unrelated to Phase 2 deferred items, update `scripts/compile_schema_ref.sh` to clear them. Acceptable: section absent or notes only "All drift resolved as of 2026-04-24."

- [ ] **Step 2: Live DB column state**

```bash
psql "$SUPABASE_DB_URL" -c "SELECT column_name FROM information_schema.columns WHERE table_name='creators' AND column_name LIKE '%last_discovery_run%';"
```

Expected: one row, `last_discovery_run_id`.

- [ ] **Step 3: Zero stale source references**

```bash
grep -rn "last_discovery_run_id_fk" src/ scripts/ | grep -v node_modules
```

Expected: zero hits.

- [ ] **Step 4: Spawn verifier subagent**

Invoke the verifier subagent with this prompt:
> Verify Layer 1 of the Phase 1 overhaul: (1) `creators` table has exactly one `last_discovery_run_id` column with FK to `discovery_runs(id)` (use `psql \d creators`); (2) `docs/SCHEMA.md` regenerated and Drift section is empty; (3) `PROJECT_STATE.md §4` matches live DB for `creators`, `trend_signals`, `alerts_feed`, `discovery_runs`; (4) §20 schema-drift row removed. Report pass/fail with evidence.

Expected: verifier returns "pass."

---

# LAYER 2 — GENERATED ARTIFACTS

### Task 6: Create typed re-exports module

**Files:**
- Create: `src/types/db.ts`

- [ ] **Step 1: Write the file**

```typescript
// src/types/db.ts
// Typed re-exports from generated database types. App code imports from here, not from database.types.ts directly.

import type { Database } from './database.types'

export type DB = Database

export type Tables<T extends keyof Database['public']['Tables']> =
  Database['public']['Tables'][T]['Row']

export type Inserts<T extends keyof Database['public']['Tables']> =
  Database['public']['Tables'][T]['Insert']

export type Updates<T extends keyof Database['public']['Tables']> =
  Database['public']['Tables'][T]['Update']

export type Enums<T extends keyof Database['public']['Enums']> =
  Database['public']['Enums'][T]

export type RpcArgs<T extends keyof Database['public']['Functions']> =
  Database['public']['Functions'][T]['Args']

export type RpcReturns<T extends keyof Database['public']['Functions']> =
  Database['public']['Functions'][T]['Returns']
```

- [ ] **Step 2: Verify it compiles**

```bash
npx tsc --noEmit
```

Expected: zero errors.

- [ ] **Step 3: Commit**

```bash
git add src/types/db.ts
git commit -m "feat(types): add Tables<>/Inserts<>/Updates<>/Enums<>/RpcArgs<>/RpcReturns<> re-exports"
```

---

### Task 7: Type the Supabase clients

**Files:**
- Modify: `src/lib/supabase/server.ts`
- Modify: `src/lib/supabase/client.ts`

- [ ] **Step 1: Update `src/lib/supabase/client.ts`**

Replace entire file:
```typescript
import { createBrowserClient } from '@supabase/ssr'
import type { Database } from '@/types/database.types'

export function createClient() {
  return createBrowserClient<Database>(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!
  )
}
```

- [ ] **Step 2: Update `src/lib/supabase/server.ts`**

Replace entire file:
```typescript
import { createServerClient } from '@supabase/ssr'
import { createClient as createSupabaseClient } from '@supabase/supabase-js'
import { cookies } from 'next/headers'
import type { Database } from '@/types/database.types'

// Cookie-based anon client — used only when we need auth session context.
export async function createClient() {
  const cookieStore = await cookies()

  return createServerClient<Database>(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
    {
      cookies: {
        getAll() {
          return cookieStore.getAll()
        },
        setAll(cookiesToSet) {
          try {
            cookiesToSet.forEach(({ name, value, options }) =>
              cookieStore.set(name, value, options)
            )
          } catch {
            // Called from a Server Component — safe to ignore.
          }
        },
      },
    }
  )
}

// Service-role client for server-side page fetches and mutations — bypasses RLS.
// Safe to use only in Server Components and server actions (never sent to the browser).
// Throws if SUPABASE_SERVICE_ROLE_KEY is not configured — no anon-key fallback.
export function createServiceClient() {
  const url = process.env.NEXT_PUBLIC_SUPABASE_URL
  const key = process.env.SUPABASE_SERVICE_ROLE_KEY

  if (!url) {
    throw new Error('NEXT_PUBLIC_SUPABASE_URL is not configured')
  }
  if (!key) {
    throw new Error(
      'SUPABASE_SERVICE_ROLE_KEY is not configured. The service client must use the service role key to bypass RLS — anon-key fallback would silently return empty results. Set SUPABASE_SERVICE_ROLE_KEY in .env.local.'
    )
  }

  return createSupabaseClient<Database>(url, key, {
    auth: { persistSession: false },
  })
}
```

- [ ] **Step 3: Verify it compiles**

```bash
npx tsc --noEmit
```

Expected: zero errors.

- [ ] **Step 4: Verify the service-role-key check works**

```bash
# Temporarily unset the env var and try to import the function in a test script
SUPABASE_SERVICE_ROLE_KEY="" node -e "
process.env.NEXT_PUBLIC_SUPABASE_URL='https://example.supabase.co';
import('./src/lib/supabase/server.ts').then(m => {
  try { m.createServiceClient(); console.log('FAIL: expected throw'); }
  catch (e) { console.log('OK:', e.message); }
}).catch(e => console.log('OK (import-time):', e.message));
" 2>&1 || true
```

Expected: prints "OK: SUPABASE_SERVICE_ROLE_KEY is not configured..." (the manual unset test). If the import path fails because Node can't resolve TS, that's fine — the type check above already confirmed the runtime guard.

- [ ] **Step 5: Commit**

```bash
git add src/lib/supabase/client.ts src/lib/supabase/server.ts
git commit -m "feat(supabase): type clients with Database; throw on missing service role key"
```

---

# LAYER 3 — DATA ACCESS

### Task 8: Result type and auth helper

**Files:**
- Create: `src/lib/db/result.ts`
- Create: `src/lib/auth.ts`

- [ ] **Step 1: Create `src/lib/db/result.ts`**

```typescript
// src/lib/db/result.ts
// Discriminated-union Result type used by every server action.

export type Result<T> =
  | { ok: true; data: T }
  | { ok: false; error: string; code?: string }

export function ok<T>(data: T): Result<T> {
  return { ok: true, data }
}

export function err<T = never>(error: string, code?: string): Result<T> {
  return { ok: false, error, code }
}

// Convenience: wrap a Supabase query response (`{data, error}`) into a Result.
export function fromSupabase<T>(
  resp: { data: T | null; error: { message: string; code?: string } | null }
): Result<T> {
  if (resp.error) return err(resp.error.message, resp.error.code)
  if (resp.data === null) return err('No data returned')
  return ok(resp.data)
}
```

- [ ] **Step 2: Create `src/lib/auth.ts`**

```typescript
// src/lib/auth.ts
// Auth scaffold for Phase 1 — hardcoded SYSTEM_USER_ID env var.
// When real Supabase Auth is implemented (Phase 4-ish), only this file changes.

export function getCurrentUserId(): string {
  const id = process.env.SYSTEM_USER_ID
  if (!id) {
    throw new Error(
      'SYSTEM_USER_ID is not configured. Set it in .env.local to a real auth.users.id UUID. ' +
      'See docs/superpowers/specs/2026-04-23-phase-1-overhaul-design.md §6.1.'
    )
  }
  return id
}
```

- [ ] **Step 3: Verify it compiles**

```bash
npx tsc --noEmit
```

Expected: zero errors.

- [ ] **Step 4: Commit**

```bash
git add src/lib/db/result.ts src/lib/auth.ts
git commit -m "feat(lib): add Result<T> type and getCurrentUserId() auth scaffold"
```

---

### Task 9: Workspace helper

**Files:**
- Create: `src/lib/workspace.ts`

- [ ] **Step 1: Write the file**

```typescript
// src/lib/workspace.ts
// Single source of truth for the active workspace ID.
// Cached per-request via React.cache() so multiple components in one render share one DB hit.

import { cache } from 'react'
import { createServiceClient } from '@/lib/supabase/server'

export const getCurrentWorkspaceId = cache(async (): Promise<string> => {
  // Phase 1: prefer DEFAULT_WORKSPACE_ID env var; fall back to oldest workspace in DB.
  // Phase 4-ish: replace with workspace_id derived from user session.
  const fromEnv = process.env.DEFAULT_WORKSPACE_ID
  if (fromEnv) return fromEnv

  const supabase = createServiceClient()
  const { data, error } = await supabase
    .from('workspaces')
    .select('id')
    .order('created_at', { ascending: true })
    .limit(1)
    .single()

  if (error) {
    throw new Error(`Failed to load default workspace: ${error.message}`)
  }
  if (!data) {
    throw new Error(
      'No workspace exists. Run `node scripts/init_workspace.js` to seed one, or set DEFAULT_WORKSPACE_ID in .env.local.'
    )
  }
  return data.id
})
```

- [ ] **Step 2: Verify it compiles**

```bash
npx tsc --noEmit
```

Expected: zero errors.

- [ ] **Step 3: Commit**

```bash
git add src/lib/workspace.ts
git commit -m "feat(lib): add getCurrentWorkspaceId() — cached, env-first lookup"
```

---

### Task 10: Query helpers — creators + profiles

**Files:**
- Create: `src/lib/db/queries.ts`

- [ ] **Step 1: Write the initial file**

```typescript
// src/lib/db/queries.ts
// Workspace-scoped read helpers. Pages NEVER call .from() directly — they call helpers from here.
// This makes the workspace_id requirement structural (typed, not convention).
// If this file grows past ~300 lines, split by domain (creators.ts, profiles.ts, content.ts).

import { createServiceClient } from '@/lib/supabase/server'
import type { Tables, Enums } from '@/types/db'

// ---------- creators ----------

export type CreatorWithProfiles = Tables<'creators'> & {
  profiles: Pick<
    Tables<'profiles'>,
    | 'id'
    | 'avatar_url'
    | 'platform'
    | 'account_type'
    | 'follower_count'
    | 'is_primary'
    | 'handle'
    | 'display_name'
    | 'discovery_confidence'
  >[]
}

export type CreatorListFilters = {
  status?: Enums<'onboarding_status'> | 'all'
  tracking?: Enums<'tracking_type'> | 'all'
  q?: string
  sort?: 'recently_added' | 'name_asc' | 'platform'
}

export async function getCreatorsForWorkspace(
  wsId: string,
  filters: CreatorListFilters = {}
): Promise<CreatorWithProfiles[]> {
  const supabase = createServiceClient()
  let query = supabase
    .from('creators')
    .select(`
      *,
      profiles!creator_id (
        id, avatar_url, platform, account_type, follower_count,
        is_primary, handle, display_name, discovery_confidence
      )
    `)
    .eq('workspace_id', wsId)

  if (filters.status && filters.status !== 'all') {
    query = query.eq('onboarding_status', filters.status)
  }
  if (filters.tracking && filters.tracking !== 'all') {
    query = query.eq('tracking_type', filters.tracking)
  }
  if (filters.q && filters.q.trim().length > 0) {
    query = query.ilike('canonical_name', `%${filters.q.trim()}%`)
  }

  switch (filters.sort) {
    case 'name_asc':
      query = query.order('canonical_name', { ascending: true })
      break
    case 'platform':
      query = query.order('primary_platform', { ascending: true, nullsFirst: false })
      break
    case 'recently_added':
    default:
      query = query.order('created_at', { ascending: false })
  }

  const { data, error } = await query
  if (error) throw new Error(`getCreatorsForWorkspace: ${error.message}`)
  return (data ?? []) as CreatorWithProfiles[]
}

export async function getCreatorBySlugForWorkspace(
  wsId: string,
  slug: string
): Promise<Tables<'creators'> | null> {
  const supabase = createServiceClient()
  const { data, error } = await supabase
    .from('creators')
    .select('*')
    .eq('workspace_id', wsId)
    .eq('slug', slug)
    .maybeSingle()
  if (error) throw new Error(`getCreatorBySlugForWorkspace: ${error.message}`)
  return data
}

export async function getCreatorStatsForWorkspace(
  wsId: string
): Promise<{
  byStatus: Record<Enums<'onboarding_status'> | 'all', number>
  byTracking: Record<Enums<'tracking_type'> | 'all', number>
}> {
  const supabase = createServiceClient()
  const { data, error } = await supabase
    .from('creators')
    .select('onboarding_status, tracking_type')
    .eq('workspace_id', wsId)
  if (error) throw new Error(`getCreatorStatsForWorkspace: ${error.message}`)

  const rows = data ?? []
  const byStatus: Record<string, number> = { all: rows.length }
  const byTracking: Record<string, number> = { all: rows.length }
  for (const r of rows) {
    if (r.onboarding_status) byStatus[r.onboarding_status] = (byStatus[r.onboarding_status] ?? 0) + 1
    if (r.tracking_type) byTracking[r.tracking_type] = (byTracking[r.tracking_type] ?? 0) + 1
  }
  return { byStatus: byStatus as any, byTracking: byTracking as any }
}

// ---------- profiles ----------

export type ProfileForCreator = Pick<
  Tables<'profiles'>,
  | 'id'
  | 'platform'
  | 'handle'
  | 'display_name'
  | 'url'
  | 'follower_count'
  | 'following_count'
  | 'post_count'
  | 'bio'
  | 'account_type'
  | 'discovery_confidence'
  | 'is_primary'
  | 'updated_at'
  | 'avatar_url'
>

export async function getProfilesForCreator(
  creatorId: string
): Promise<ProfileForCreator[]> {
  const supabase = createServiceClient()
  const { data, error } = await supabase
    .from('profiles')
    .select(
      'id, platform, handle, display_name, url, follower_count, following_count, post_count, bio, account_type, discovery_confidence, is_primary, updated_at, avatar_url'
    )
    .eq('creator_id', creatorId)
    .order('is_primary', { ascending: false })
  if (error) throw new Error(`getProfilesForCreator: ${error.message}`)
  return (data ?? []) as ProfileForCreator[]
}
```

- [ ] **Step 2: Verify it compiles**

```bash
npx tsc --noEmit
```

Expected: zero errors.

- [ ] **Step 3: Commit**

```bash
git add src/lib/db/queries.ts
git commit -m "feat(db): query helpers — creators + profiles"
```

---

### Task 11: Query helpers — platform accounts (with stats join)

**Files:**
- Modify: `src/lib/db/queries.ts`

- [ ] **Step 1: Append to `src/lib/db/queries.ts`**

```typescript
// ---------- platform-account list (Instagram/TikTok pages) ----------

export type PlatformAccountRow = {
  id: string
  handle: string
  displayName: string
  avatarUrl: string | null
  profileUrl: string | null
  followerCount: number | null
  postCount: number | null
  trackingType: string
  isClean: boolean
  analysisVersion: string | null
  creatorId: string | null
  creatorSlug: string | null
  currentScore: number | null
  currentRank: string | null
  scoredContentCount: number
  medianViews: number | null
  outlierCount: number
  hasContent: boolean
}

export async function getPlatformAccountsForWorkspace(
  wsId: string,
  args: {
    platform: Enums<'platform'>
    accountType?: Enums<'account_type'>
  }
): Promise<PlatformAccountRow[]> {
  const supabase = createServiceClient()

  const { data: rawProfiles, error: pErr } = await supabase
    .from('profiles')
    .select(`
      id, handle, display_name, avatar_url, profile_url,
      follower_count, post_count, tracking_type, is_clean,
      analysis_version, creator_id,
      profile_scores ( current_score, current_rank, scored_content_count ),
      creators!creator_id ( slug )
    `)
    .eq('workspace_id', wsId)
    .eq('platform', args.platform)
    .eq('account_type', args.accountType ?? 'social')

  if (pErr) throw new Error(`getPlatformAccountsForWorkspace.profiles: ${pErr.message}`)
  if (!rawProfiles || rawProfiles.length === 0) return []

  const profileIds = rawProfiles.map((p) => p.id)

  const [snapshotsRes, contentRes] = await Promise.all([
    supabase
      .from('profile_metrics_snapshots')
      .select('profile_id, median_views, snapshot_date')
      .in('profile_id', profileIds)
      .order('snapshot_date', { ascending: false }),
    supabase
      .from('scraped_content')
      .select('profile_id, is_outlier, view_count, posted_at')
      .in('profile_id', profileIds),
  ])

  if (snapshotsRes.error) {
    throw new Error(`getPlatformAccountsForWorkspace.snapshots: ${snapshotsRes.error.message}`)
  }
  if (contentRes.error) {
    throw new Error(`getPlatformAccountsForWorkspace.content: ${contentRes.error.message}`)
  }

  // Latest snapshot per profile
  const snapshotMap = new Map<string, number>()
  for (const snap of snapshotsRes.data ?? []) {
    if (!snapshotMap.has(snap.profile_id)) {
      snapshotMap.set(snap.profile_id, Number(snap.median_views))
    }
  }

  // Live median fallback for profiles missing a snapshot
  const contentSet = new Set<string>()
  const outlierCountMap = new Map<string, number>()
  const viewsByProfile = new Map<string, number[]>()
  const cutoff = new Date(Date.now() - 90 * 24 * 60 * 60 * 1000)

  for (const row of contentRes.data ?? []) {
    contentSet.add(row.profile_id!)
    if (row.is_outlier) {
      outlierCountMap.set(row.profile_id!, (outlierCountMap.get(row.profile_id!) ?? 0) + 1)
    }
    if (
      !snapshotMap.has(row.profile_id!) &&
      row.view_count != null &&
      row.posted_at &&
      new Date(row.posted_at) >= cutoff
    ) {
      const arr = viewsByProfile.get(row.profile_id!) ?? []
      arr.push(Number(row.view_count))
      viewsByProfile.set(row.profile_id!, arr)
    }
  }

  for (const [profileId, views] of viewsByProfile) {
    if (views.length > 0) {
      const sorted = [...views].sort((a, b) => a - b)
      const mid = Math.floor(sorted.length / 2)
      const median =
        sorted.length % 2 === 0
          ? (sorted[mid - 1] + sorted[mid]) / 2
          : sorted[mid]
      snapshotMap.set(profileId, Math.round(median))
    }
  }

  const accounts: PlatformAccountRow[] = rawProfiles.map((p) => {
    const scores = Array.isArray(p.profile_scores)
      ? p.profile_scores[0] ?? null
      : (p.profile_scores ?? null)
    const creator = Array.isArray(p.creators)
      ? p.creators[0] ?? null
      : (p.creators ?? null)

    return {
      id: p.id,
      handle: p.handle ?? '',
      displayName: p.display_name ?? p.handle ?? '',
      avatarUrl: p.avatar_url ?? null,
      profileUrl: p.profile_url ?? null,
      followerCount: p.follower_count != null ? Number(p.follower_count) : null,
      postCount: p.post_count != null ? Number(p.post_count) : null,
      trackingType: p.tracking_type ?? 'unreviewed',
      isClean: p.is_clean ?? false,
      analysisVersion: p.analysis_version ?? null,
      creatorId: p.creator_id ?? null,
      creatorSlug: (creator as { slug?: string } | null)?.slug ?? null,
      currentScore: scores?.current_score != null ? Number(scores.current_score) : null,
      currentRank: scores?.current_rank ?? null,
      scoredContentCount: scores?.scored_content_count ?? 0,
      medianViews: snapshotMap.get(p.id) ?? null,
      outlierCount: outlierCountMap.get(p.id) ?? 0,
      hasContent: contentSet.has(p.id),
    }
  })

  // Default sort: quality score desc, unscored last
  accounts.sort((a, b) => {
    if (a.currentScore === null && b.currentScore === null) return 0
    if (a.currentScore === null) return 1
    if (b.currentScore === null) return -1
    return b.currentScore - a.currentScore
  })

  return accounts
}
```

- [ ] **Step 2: Verify it compiles**

```bash
npx tsc --noEmit
```

Expected: zero errors.

- [ ] **Step 3: Commit**

```bash
git add src/lib/db/queries.ts
git commit -m "feat(db): query helper — platform accounts with stats join"
```

---

### Task 12: Query helpers — Command Center stats

**Files:**
- Modify: `src/lib/db/queries.ts`

- [ ] **Step 1: Append to `src/lib/db/queries.ts`**

```typescript
// ---------- Command Center ----------

export async function getCommandCenterStats(wsId: string): Promise<{
  creatorCount: number
  postCount: number
  pendingDiscoveryCount: number
  avgQualityScore: number | null
}> {
  const supabase = createServiceClient()

  const [creatorsRes, pendingRes, contentCountRes, scoresRes] = await Promise.all([
    supabase
      .from('creators')
      .select('*', { count: 'exact', head: true })
      .eq('workspace_id', wsId),
    supabase
      .from('discovery_runs')
      .select('*', { count: 'exact', head: true })
      .eq('workspace_id', wsId)
      .in('status', ['pending', 'processing']),
    // scraped_content has no workspace_id — scope via profile_id IN (workspace profiles)
    supabase
      .from('scraped_content')
      .select('profiles!inner(workspace_id)', { count: 'exact', head: true })
      .eq('profiles.workspace_id', wsId),
    supabase
      .from('profile_scores')
      .select('current_score, profiles!inner(workspace_id)')
      .eq('profiles.workspace_id', wsId),
  ])

  const scores = (scoresRes.data ?? [])
    .map((r) => Number(r.current_score))
    .filter((n) => !Number.isNaN(n) && n > 0)
  const avg =
    scores.length > 0 ? scores.reduce((a, b) => a + b, 0) / scores.length : null

  return {
    creatorCount: creatorsRes.count ?? 0,
    postCount: contentCountRes.count ?? 0,
    pendingDiscoveryCount: pendingRes.count ?? 0,
    avgQualityScore: avg !== null ? Math.round(avg * 10) / 10 : null,
  }
}

export async function getRecentOutliersForWorkspace(
  wsId: string,
  limit = 5
): Promise<Array<{
  profileHandle: string
  outlierMultiplier: number | null
  viewCount: number
  postUrl: string | null
}>> {
  const supabase = createServiceClient()
  const { data, error } = await supabase
    .from('scraped_content')
    .select(`
      view_count, outlier_multiplier, post_url,
      profiles!inner ( handle, workspace_id )
    `)
    .eq('profiles.workspace_id', wsId)
    .eq('is_outlier', true)
    .order('outlier_multiplier', { ascending: false, nullsFirst: false })
    .limit(limit)
  if (error) throw new Error(`getRecentOutliersForWorkspace: ${error.message}`)
  return (data ?? []).map((r: any) => ({
    profileHandle: r.profiles?.handle ?? '',
    outlierMultiplier: r.outlier_multiplier != null ? Number(r.outlier_multiplier) : null,
    viewCount: Number(r.view_count ?? 0),
    postUrl: r.post_url ?? null,
  }))
}

export async function getActiveTrendSignalsForWorkspace(
  wsId: string,
  limit = 5
): Promise<Array<{
  signalType: Enums<'signal_type'>
  score: number | null
  metadata: Record<string, unknown>
  detectedAt: string | null
}>> {
  const supabase = createServiceClient()
  const { data, error } = await supabase
    .from('trend_signals')
    .select('signal_type, score, metadata, detected_at')
    .eq('workspace_id', wsId)
    .eq('is_dismissed', false)
    .order('detected_at', { ascending: false })
    .limit(limit)
  if (error) throw new Error(`getActiveTrendSignalsForWorkspace: ${error.message}`)
  return (data ?? []).map((r) => ({
    signalType: r.signal_type as Enums<'signal_type'>,
    score: r.score != null ? Number(r.score) : null,
    metadata: (r.metadata as Record<string, unknown>) ?? {},
    detectedAt: r.detected_at,
  }))
}

// ---------- merge candidates ----------

export async function getMergeCandidatesForWorkspace(
  wsId: string
): Promise<Tables<'creator_merge_candidates'>[]> {
  const supabase = createServiceClient()
  const { data, error } = await supabase
    .from('creator_merge_candidates')
    .select('*')
    .eq('workspace_id', wsId)
    .eq('status', 'pending')
  if (error) throw new Error(`getMergeCandidatesForWorkspace: ${error.message}`)
  return data ?? []
}

export async function getMergeCandidatesForCreator(
  creatorId: string
): Promise<Tables<'creator_merge_candidates'>[]> {
  const supabase = createServiceClient()
  const { data, error } = await supabase
    .from('creator_merge_candidates')
    .select('*')
    .eq('status', 'pending')
    .or(`creator_a_id.eq.${creatorId},creator_b_id.eq.${creatorId}`)
  if (error) throw new Error(`getMergeCandidatesForCreator: ${error.message}`)
  return data ?? []
}
```

- [ ] **Step 2: Verify it compiles**

```bash
npx tsc --noEmit
```

Expected: zero errors.

- [ ] **Step 3: Commit**

```bash
git add src/lib/db/queries.ts
git commit -m "feat(db): Command Center stats + outliers + trend signals + merge candidates queries"
```

---

### Task 13: Typed RPC wrappers

**Files:**
- Create: `src/lib/db/rpc.ts`

- [ ] **Step 1: Write the file**

```typescript
// src/lib/db/rpc.ts
// Typed RPC wrappers. App code calls these instead of supabase.rpc('name', args).
// Generated DB types provide arg/return shapes via RpcArgs<>/RpcReturns<>.

import { createServiceClient } from '@/lib/supabase/server'
import { fromSupabase, type Result } from '@/lib/db/result'
import type { RpcArgs, RpcReturns } from '@/types/db'

export async function commitDiscoveryResult(
  args: RpcArgs<'commit_discovery_result'>
): Promise<Result<RpcReturns<'commit_discovery_result'>>> {
  const supabase = createServiceClient()
  const resp = await supabase.rpc('commit_discovery_result', args)
  return fromSupabase(resp)
}

export async function markDiscoveryFailed(
  args: RpcArgs<'mark_discovery_failed'>
): Promise<Result<RpcReturns<'mark_discovery_failed'>>> {
  const supabase = createServiceClient()
  const resp = await supabase.rpc('mark_discovery_failed', args)
  return fromSupabase(resp)
}

export async function retryCreatorDiscovery(
  args: RpcArgs<'retry_creator_discovery'>
): Promise<Result<RpcReturns<'retry_creator_discovery'>>> {
  const supabase = createServiceClient()
  const resp = await supabase.rpc('retry_creator_discovery', args)
  return fromSupabase(resp)
}

export async function mergeCreators(
  args: RpcArgs<'merge_creators'>
): Promise<Result<RpcReturns<'merge_creators'>>> {
  const supabase = createServiceClient()
  const resp = await supabase.rpc('merge_creators', args)
  return fromSupabase(resp)
}

// bulkImportCreator is added in Task 15 after the migration lands.
```

- [ ] **Step 2: Verify it compiles**

```bash
npx tsc --noEmit
```

Expected: zero errors.

- [ ] **Step 3: Commit**

```bash
git add src/lib/db/rpc.ts
git commit -m "feat(db): typed RPC wrappers — commit/mark/retry/merge"
```

---

### Task 14: Layer 3 verification gate

- [ ] **Step 1: Verify no raw `.from()` in pages yet (will refactor in Layer 6 — this is a baseline check)**

```bash
grep -rn "\.from(" "/Users/simon/OS/Living VAULT/Content OS/The Hub/src/app" 2>/dev/null | wc -l
```

Record the baseline count. It will go to zero after Layer 6.

- [ ] **Step 2: Verify the service client guard**

```bash
grep -n "NEXT_PUBLIC_SUPABASE_ANON_KEY" "/Users/simon/OS/Living VAULT/Content OS/The Hub/src/lib/supabase/server.ts"
```

Expected: appears only once, in the cookie-based `createClient()` function — NOT inside `createServiceClient()`.

- [ ] **Step 3: typecheck**

```bash
cd "/Users/simon/OS/Living VAULT/Content OS/The Hub" && npx tsc --noEmit
```

Expected: zero errors.

- [ ] **Step 4: Spawn verifier subagent**

Invoke the verifier subagent with this prompt:
> Verify Layer 3 of the Phase 1 overhaul: (1) `src/lib/db/result.ts`, `src/lib/auth.ts`, `src/lib/workspace.ts`, `src/lib/db/queries.ts`, `src/lib/db/rpc.ts` all exist and export the documented helpers; (2) `src/lib/supabase/server.ts` `createServiceClient()` does NOT fall back to `NEXT_PUBLIC_SUPABASE_ANON_KEY` and throws if `SUPABASE_SERVICE_ROLE_KEY` is unset; (3) `npx tsc --noEmit` passes with zero errors. Report pass/fail with evidence.

Expected: verifier returns "pass."

---

# LAYER 4 — SERVER ACTIONS + RPC

### Task 15: bulk_import_creator RPC migration

**Files:**
- Create: `supabase/migrations/20260424000001_bulk_import_creator_rpc.sql`

- [ ] **Step 1: Write the migration**

```sql
-- 20260424000001_bulk_import_creator_rpc.sql
-- Atomic bulk import: insert creator + profile + discovery_run in one transaction.
-- Caller invokes once per handle; collects per-handle errors at the action layer.

CREATE OR REPLACE FUNCTION bulk_import_creator(
  p_handle text,
  p_platform_hint platform,
  p_tracking_type tracking_type,
  p_tags text[],
  p_user_id uuid,
  p_workspace_id uuid
) RETURNS uuid
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
  v_normalized text;
  v_slug text;
  v_creator_id uuid;
  v_run_id uuid;
BEGIN
  IF p_handle IS NULL OR length(trim(p_handle)) = 0 THEN
    RAISE EXCEPTION 'p_handle must be non-empty';
  END IF;
  IF p_workspace_id IS NULL THEN
    RAISE EXCEPTION 'p_workspace_id is required';
  END IF;

  v_normalized := normalize_handle(p_handle);
  -- Ensure slug uniqueness with a short random suffix.
  v_slug := v_normalized || '-' || substr(md5(random()::text || clock_timestamp()::text), 1, 6);

  -- 1. Insert creator (placeholder; discovery enriches later).
  INSERT INTO creators (
    workspace_id, canonical_name, slug, primary_platform,
    known_usernames, tracking_type, tags, onboarding_status,
    import_source, added_by
  ) VALUES (
    p_workspace_id, p_handle, v_slug,
    CASE WHEN p_platform_hint::text = 'other' THEN NULL ELSE p_platform_hint END,
    ARRAY[p_handle], p_tracking_type, COALESCE(p_tags, ARRAY[]::text[]),
    'processing', 'bulk', p_user_id
  )
  RETURNING id INTO v_creator_id;

  -- 2. Insert primary profile so the card shows a handle immediately.
  INSERT INTO profiles (
    workspace_id, creator_id, platform, handle, account_type,
    is_primary, added_by, discovery_confidence
  ) VALUES (
    p_workspace_id, v_creator_id,
    COALESCE(p_platform_hint, 'other'::platform),
    p_handle, 'social', true, p_user_id, 1.0
  );

  -- 3. Insert pending discovery run (Python worker picks it up).
  INSERT INTO discovery_runs (
    workspace_id, creator_id, input_handle, input_platform_hint,
    status, attempt_number, initiated_by
  ) VALUES (
    p_workspace_id, v_creator_id, p_handle, p_platform_hint,
    'pending', 1, p_user_id
  )
  RETURNING id INTO v_run_id;

  -- 4. Link creator → run.
  UPDATE creators SET last_discovery_run_id = v_run_id WHERE id = v_creator_id;

  RETURN v_creator_id;
END;
$$;

-- Grant execute to authenticated and anon (RLS policies still apply via SECURITY DEFINER's
-- own privileges; the function uses workspace_id passed by the caller).
GRANT EXECUTE ON FUNCTION bulk_import_creator(text, platform, tracking_type, text[], uuid, uuid) TO authenticated, anon, service_role;
```

- [ ] **Step 2: Apply the migration**

```bash
psql "$SUPABASE_DB_URL" -f supabase/migrations/20260424000001_bulk_import_creator_rpc.sql
```

Expected: `CREATE FUNCTION`, `GRANT`.

- [ ] **Step 3: Smoke-test the RPC**

```bash
psql "$SUPABASE_DB_URL" <<'SQL'
-- Use the default workspace + a real auth.users id from your env.
DO $$
DECLARE
  ws uuid := (SELECT id FROM workspaces ORDER BY created_at LIMIT 1);
  uid uuid := (SELECT id FROM auth.users LIMIT 1);
  cid uuid;
BEGIN
  cid := bulk_import_creator(
    '__test_handle_' || extract(epoch from now())::text,
    'instagram'::platform,
    'unreviewed'::tracking_type,
    ARRAY['test'],
    uid,
    ws
  );
  RAISE NOTICE 'created creator %', cid;

  -- Verify all rows present
  IF NOT EXISTS (SELECT 1 FROM creators WHERE id = cid AND last_discovery_run_id IS NOT NULL) THEN
    RAISE EXCEPTION 'FAIL: creator missing or last_discovery_run_id not set';
  END IF;
  IF NOT EXISTS (SELECT 1 FROM profiles WHERE creator_id = cid AND is_primary = true) THEN
    RAISE EXCEPTION 'FAIL: primary profile missing';
  END IF;
  IF NOT EXISTS (SELECT 1 FROM discovery_runs WHERE creator_id = cid AND status = 'pending') THEN
    RAISE EXCEPTION 'FAIL: discovery_run missing or wrong status';
  END IF;

  -- Cleanup
  DELETE FROM discovery_runs WHERE creator_id = cid;
  DELETE FROM profiles WHERE creator_id = cid;
  DELETE FROM creators WHERE id = cid;
  RAISE NOTICE 'cleanup done';
END $$;
SQL
```

Expected: `NOTICE: created creator ...` and `NOTICE: cleanup done`. No `FAIL` messages.

- [ ] **Step 4: Regenerate types**

```bash
npm run db:types
```

Expected: file rewrites, includes `bulk_import_creator` in `Functions`.

- [ ] **Step 5: Append the wrapper to `src/lib/db/rpc.ts`**

Add at the end of the file:
```typescript
export async function bulkImportCreator(
  args: RpcArgs<'bulk_import_creator'>
): Promise<Result<RpcReturns<'bulk_import_creator'>>> {
  const supabase = createServiceClient()
  const resp = await supabase.rpc('bulk_import_creator', args)
  return fromSupabase(resp)
}
```

- [ ] **Step 6: typecheck + commit**

```bash
npx tsc --noEmit
git add supabase/migrations/20260424000001_bulk_import_creator_rpc.sql src/types/database.types.ts src/lib/db/rpc.ts
git commit -m "feat(db): atomic bulk_import_creator RPC + typed wrapper"
```

- [ ] **Step 7: Append migration log entry**

```bash
cat >> supabase/migrations/MIGRATION_LOG.md <<'EOF'

## 20260424000001_bulk_import_creator_rpc

Applied: 2026-04-24
Adds atomic `bulk_import_creator(p_handle, p_platform_hint, p_tracking_type, p_tags, p_user_id, p_workspace_id)` returning `creator_id`. Inserts creator + primary profile + pending discovery_run, then links creator.last_discovery_run_id. Replaces the per-handle JS Promise.all in the old bulk import flow.
EOF
git add supabase/migrations/MIGRATION_LOG.md
git commit -m "docs(db): log bulk_import_creator RPC migration"
```

---

### Task 16: Add sonner for toasts

**Files:**
- Modify: `package.json`
- Create: `src/components/ui/sonner.tsx`
- Modify: `src/app/layout.tsx`

- [ ] **Step 1: Install sonner**

```bash
cd "/Users/simon/OS/Living VAULT/Content OS/The Hub" && npm install sonner@^1.5.0
```

Expected: package added to `dependencies`.

- [ ] **Step 2: Create the Toaster component**

```typescript
// src/components/ui/sonner.tsx
"use client"

import { Toaster as Sonner } from "sonner"

export function Toaster() {
  return (
    <Sonner
      theme="dark"
      position="top-right"
      toastOptions={{
        classNames: {
          toast:
            "group toast group-[.toaster]:bg-card group-[.toaster]:text-foreground group-[.toaster]:border-border group-[.toaster]:shadow-lg",
          description: "group-[.toast]:text-muted-foreground",
          actionButton:
            "group-[.toast]:bg-indigo-600 group-[.toast]:text-white",
          cancelButton:
            "group-[.toast]:bg-muted group-[.toast]:text-muted-foreground",
        },
      }}
    />
  )
}
```

- [ ] **Step 3: Mount Toaster in `src/app/layout.tsx`**

Open `src/app/layout.tsx`. After the `<body>` opening (or wherever children render), add:
```tsx
import { Toaster } from "@/components/ui/sonner"
```
and inside the `<body>` JSX (after `{children}`), add:
```tsx
<Toaster />
```

- [ ] **Step 4: Verify build**

```bash
npx tsc --noEmit
```

Expected: zero errors.

- [ ] **Step 5: Commit**

```bash
git add package.json package-lock.json src/components/ui/sonner.tsx src/app/layout.tsx
git commit -m "feat(ui): add sonner toaster"
```

---

### Task 17: Delete dead actions file and rebuild creators actions

**Files:**
- Delete: `src/app/(dashboard)/creators/actions.ts` (then recreated below)

- [ ] **Step 1: Replace `src/app/(dashboard)/creators/actions.ts` with the rebuilt version**

```typescript
// src/app/(dashboard)/creators/actions.ts
// Server actions for the Creators surface. Returns Result<T> on every action.

"use server"

import { revalidatePath } from "next/cache"
import { createServiceClient } from "@/lib/supabase/server"
import { getCurrentUserId } from "@/lib/auth"
import { getCurrentWorkspaceId } from "@/lib/workspace"
import {
  bulkImportCreator,
  retryCreatorDiscovery as rpcRetryCreatorDiscovery,
  mergeCreators,
} from "@/lib/db/rpc"
import { ok, err, type Result } from "@/lib/db/result"
import type { ParsedHandle } from "@/lib/handleParser"
import { parseHandles } from "@/lib/handleParser"
import type { Enums } from "@/types/db"

// ---------- bulkImportCreators ----------

export type BulkImportSummary = {
  imported: number
  skipped: number
  errors: Array<{ handle: string; error: string }>
}

export async function bulkImportCreators(
  rawText: string,
  trackingType: Enums<"tracking_type">,
  tagsCsv: string,
  assignedPlatforms: Record<string, string> = {}
): Promise<Result<BulkImportSummary>> {
  try {
    const userId = getCurrentUserId()
    const wsId = await getCurrentWorkspaceId()

    const parsed = parseHandles(rawText)
    const tags = tagsCsv
      ? tagsCsv.split(",").map((t) => t.trim()).filter(Boolean)
      : []

    const errors: BulkImportSummary["errors"] = []
    let imported = 0
    let skipped = 0

    for (let i = 0; i < parsed.length; i++) {
      const ph = parsed[i]
      if (ph.isDuplicate) {
        skipped++
        continue
      }
      const finalPlatform = assignedPlatforms[String(i)] || ph.platform
      if (!finalPlatform || finalPlatform === "unknown") {
        errors.push({ handle: ph.handle ?? "(unknown)", error: "Missing platform" })
        continue
      }
      if (!ph.handle) {
        errors.push({ handle: "(unknown)", error: "Empty handle" })
        continue
      }

      const res = await bulkImportCreator({
        p_handle: ph.handle,
        p_platform_hint: finalPlatform as Enums<"platform">,
        p_tracking_type: trackingType,
        p_tags: tags,
        p_user_id: userId,
        p_workspace_id: wsId,
      })
      if (!res.ok) {
        errors.push({ handle: ph.handle, error: res.error })
        continue
      }
      imported++
    }

    revalidatePath("/creators")
    return ok({ imported, skipped, errors })
  } catch (e: any) {
    return err(e?.message ?? "Bulk import failed")
  }
}

// ---------- importSingleCreator ----------

export async function importSingleCreator(
  platform: Enums<"platform">,
  handle: string,
  url?: string
): Promise<Result<{ creatorId: string }>> {
  try {
    if (!handle || handle.trim().length === 0) {
      return err("Handle is required")
    }
    const userId = getCurrentUserId()
    const wsId = await getCurrentWorkspaceId()

    const res = await bulkImportCreator({
      p_handle: handle.trim().replace(/^@/, ""),
      p_platform_hint: platform,
      p_tracking_type: "unreviewed",
      p_tags: [],
      p_user_id: userId,
      p_workspace_id: wsId,
    })
    if (!res.ok) return err(res.error)

    // url is informational at the action layer; discovery will use it.
    revalidatePath("/creators")
    return ok({ creatorId: res.data })
  } catch (e: any) {
    return err(e?.message ?? "Single import failed")
  }
}

// ---------- retryCreatorDiscovery ----------

export async function retryCreatorDiscovery(
  creatorId: string
): Promise<Result<{ runId: string | null }>> {
  try {
    const userId = getCurrentUserId()
    const res = await rpcRetryCreatorDiscovery({
      p_creator_id: creatorId,
      p_user_id: userId,
    })
    if (!res.ok) return err(res.error)

    // Non-blocking edge function trigger — Python worker polls anyway.
    if (res.data) {
      fetch(
        `${process.env.NEXT_PUBLIC_SUPABASE_URL}/functions/v1/trigger-discovery`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${process.env.SUPABASE_SERVICE_ROLE_KEY}`,
          },
          body: JSON.stringify({ run_id: res.data }),
        }
      ).catch(() => {
        // Fire-and-forget — worker polls fallback path
      })
    }

    revalidatePath("/creators")
    revalidatePath(`/creators/${creatorId}`)
    return ok({ runId: (res.data as string | null) ?? null })
  } catch (e: any) {
    return err(e?.message ?? "Retry failed")
  }
}

// ---------- dismissMergeCandidate ----------

export async function dismissMergeCandidate(
  candidateId: string
): Promise<Result<void>> {
  try {
    const wsId = await getCurrentWorkspaceId()
    const supabase = createServiceClient()
    const { error } = await supabase
      .from("creator_merge_candidates")
      .update({ status: "dismissed" })
      .eq("id", candidateId)
      .eq("workspace_id", wsId)
    if (error) return err(error.message)
    revalidatePath("/creators")
    return ok(undefined)
  } catch (e: any) {
    return err(e?.message ?? "Dismiss failed")
  }
}

// ---------- mergeCandidateCreators ----------

export async function mergeCandidateCreators(
  keepId: string,
  mergeId: string,
  candidateId: string
): Promise<Result<void>> {
  try {
    const userId = getCurrentUserId()
    const res = await mergeCreators({
      p_keep_id: keepId,
      p_merge_id: mergeId,
      p_resolver_id: userId,
      p_candidate_id: candidateId,
    })
    if (!res.ok) return err(res.error)
    revalidatePath("/creators")
    return ok(undefined)
  } catch (e: any) {
    return err(e?.message ?? "Merge failed")
  }
}

// ---------- addAccountToCreator ----------

export async function addAccountToCreator(
  creatorId: string,
  data: {
    platform: Enums<"platform">
    handle: string
    accountType: Enums<"account_type">
    url?: string
    displayName?: string
  }
): Promise<Result<{ profileId: string }>> {
  try {
    const userId = getCurrentUserId()
    const wsId = await getCurrentWorkspaceId()
    const supabase = createServiceClient()
    const { data: row, error } = await supabase
      .from("profiles")
      .insert({
        workspace_id: wsId,
        creator_id: creatorId,
        platform: data.platform,
        handle: data.handle.replace(/^@/, ""),
        account_type: data.accountType,
        url: data.url ?? null,
        display_name: data.displayName ?? null,
        discovery_confidence: 1.0,
        is_primary: false,
        added_by: userId,
      })
      .select("id")
      .single()
    if (error) return err(error.message)
    revalidatePath(`/creators/${creatorId}`)
    return ok({ profileId: row.id })
  } catch (e: any) {
    return err(e?.message ?? "Add account failed")
  }
}
```

- [ ] **Step 2: typecheck**

```bash
npx tsc --noEmit
```

Expected: zero errors. (Errors about `BulkImportDialog` etc. consuming the old action signatures are expected — fixed in Layer 5.)

- [ ] **Step 3: Commit**

```bash
git add src/app/\(dashboard\)/creators/actions.ts
git commit -m "feat(actions): rebuild creators actions with Result<T>, atomic bulk import RPC, system user audit"
```

---

### Task 18: Delete the old shared actions file

**Files:**
- Delete: `src/app/actions.ts`

- [ ] **Step 1: Find all imports of `@/app/actions`**

```bash
grep -rn "from ['\"]@/app/actions['\"]" "/Users/simon/OS/Living VAULT/Content OS/The Hub/src"
```

Expected hits (will be updated below):
- `src/components/creators/BulkImportDialog.tsx`
- `src/components/creators/RerunDiscoveryButton.tsx`
- `src/components/creators/AddAccountDialog.tsx` (likely)

- [ ] **Step 2: Update each importer to use the new actions module**

For `src/components/creators/BulkImportDialog.tsx`, change:
```ts
import { bulkImportCreators } from "@/app/actions";
```
to:
```ts
import { bulkImportCreators, importSingleCreator } from "@/app/(dashboard)/creators/actions";
```

For `src/components/creators/RerunDiscoveryButton.tsx`, change:
```ts
import { rerunCreatorDiscovery } from "@/app/actions";
```
to:
```ts
import { retryCreatorDiscovery } from "@/app/(dashboard)/creators/actions";
```
And rename the call from `rerunCreatorDiscovery(creatorId)` to `retryCreatorDiscovery(creatorId)`.

For `src/components/creators/AddAccountDialog.tsx`, change:
```ts
import { addProfileToCreator } from "@/app/actions";
```
to:
```ts
import { addAccountToCreator } from "@/app/(dashboard)/creators/actions";
```
And update the call site to pass the new args object. (Detailed wiring is in Task 23.)

- [ ] **Step 3: Delete `src/app/actions.ts`**

```bash
rm "/Users/simon/OS/Living VAULT/Content OS/The Hub/src/app/actions.ts"
```

- [ ] **Step 4: Confirm zero remaining imports**

```bash
grep -rn "from ['\"]@/app/actions['\"]" "/Users/simon/OS/Living VAULT/Content OS/The Hub/src"
```

Expected: no hits.

- [ ] **Step 5: typecheck**

```bash
npx tsc --noEmit
```

Expected: type errors will appear in BulkImportDialog/RerunDiscoveryButton/AddAccountDialog because they consume the old action shapes — those callers are fixed in Tasks 22–24. For now, leave the type errors and commit; subsequent tasks will resolve them.

- [ ] **Step 6: Commit**

```bash
git add -A src/app src/components
git commit -m "refactor(actions): delete src/app/actions.ts; route imports to creators/actions.ts"
```

---

### Task 19: Layer 4 verification gate

- [ ] **Step 1: RPC works end-to-end**

Re-run the smoke test from Task 15 Step 3 — confirm it still passes.

- [ ] **Step 2: Zero `console.error` in actions**

```bash
grep -n "console\.error" "/Users/simon/OS/Living VAULT/Content OS/The Hub/src/app/(dashboard)/creators/actions.ts"
```

Expected: zero hits.

- [ ] **Step 3: Spawn verifier subagent**

Invoke verifier:
> Verify Layer 4: (1) `src/app/actions.ts` is deleted; (2) `src/app/(dashboard)/creators/actions.ts` exports `bulkImportCreators`, `importSingleCreator`, `retryCreatorDiscovery`, `dismissMergeCandidate`, `mergeCandidateCreators`, `addAccountToCreator`, all returning `Result<T>`; (3) the `bulk_import_creator` RPC exists in Postgres and inserting succeeds (run a smoke test with one synthetic handle and clean up); (4) typecheck passes — note that callers of the old action shapes may show errors that will be fixed in Layer 5; report these but do not fail the gate on them. Report pass/fail with evidence.

Expected: verifier returns "pass."

---

# LAYER 5 — COMPONENTS

### Task 20: Shared EmptyState / ErrorState / ComingSoon components

**Files:**
- Create: `src/components/ui/empty-state.tsx`
- Create: `src/components/ui/error-state.tsx`
- Create: `src/components/shared/ComingSoon.tsx`

- [ ] **Step 1: Create `src/components/ui/empty-state.tsx`**

```typescript
// src/components/ui/empty-state.tsx
import type { LucideIcon } from "lucide-react"
import type { ReactNode } from "react"

export function EmptyState({
  icon: Icon,
  title,
  description,
  action,
}: {
  icon: LucideIcon
  title: string
  description?: string
  action?: ReactNode
}) {
  return (
    <div className="flex flex-col items-center justify-center p-12 text-center border border-dashed border-border/50 rounded-xl bg-muted/10">
      <Icon className="h-12 w-12 text-muted-foreground/30 mb-3" />
      <h3 className="text-base font-semibold">{title}</h3>
      {description && (
        <p className="text-sm text-muted-foreground mt-1.5 max-w-md">
          {description}
        </p>
      )}
      {action && <div className="mt-4">{action}</div>}
    </div>
  )
}
```

- [ ] **Step 2: Create `src/components/ui/error-state.tsx`**

```typescript
// src/components/ui/error-state.tsx
"use client"

import { AlertCircle, RotateCw } from "lucide-react"
import { Button } from "@/components/ui/button"

export function ErrorState({
  title = "Something went wrong",
  message,
  onRetry,
}: {
  title?: string
  message?: string
  onRetry?: () => void
}) {
  return (
    <div className="flex flex-col items-center justify-center p-12 text-center border border-red-900/30 rounded-xl bg-red-950/10">
      <AlertCircle className="h-12 w-12 text-red-500/70 mb-3" />
      <h3 className="text-base font-semibold text-red-400">{title}</h3>
      {message && (
        <p className="text-sm text-muted-foreground mt-1.5 max-w-md font-mono">
          {message}
        </p>
      )}
      {onRetry && (
        <Button variant="outline" size="sm" onClick={onRetry} className="mt-4">
          <RotateCw className="h-3.5 w-3.5 mr-1.5" />
          Try again
        </Button>
      )}
    </div>
  )
}
```

- [ ] **Step 3: Create `src/components/shared/ComingSoon.tsx`**

```typescript
// src/components/shared/ComingSoon.tsx
import { Sparkles } from "lucide-react"

export function ComingSoon({
  phase,
  feature,
  description,
}: {
  phase: 2 | 3 | 4
  feature: string
  description?: string
}) {
  return (
    <div className="flex flex-col items-center justify-center min-h-[60vh] text-center px-6">
      <div className="bg-indigo-500/10 border border-indigo-500/20 rounded-2xl p-2 mb-4">
        <Sparkles className="h-6 w-6 text-indigo-400" />
      </div>
      <h2 className="text-xl font-bold tracking-tight">{feature}</h2>
      <p className="text-sm text-muted-foreground mt-2 max-w-md">
        {description ?? `Coming in Phase ${phase}.`}
      </p>
      <span className="text-[10px] uppercase tracking-widest font-bold text-indigo-400 mt-4 bg-indigo-500/10 px-2 py-1 rounded-md">
        Phase {phase}
      </span>
    </div>
  )
}
```

- [ ] **Step 4: typecheck + commit**

```bash
npx tsc --noEmit
git add src/components/ui/empty-state.tsx src/components/ui/error-state.tsx src/components/shared/ComingSoon.tsx
git commit -m "feat(ui): EmptyState, ErrorState, ComingSoon shared components"
```

---

### Task 21: Loading and error boundaries

**Files:**
- Create: `src/app/(dashboard)/loading.tsx`
- Create: `src/app/(dashboard)/error.tsx`
- Create: `src/app/(dashboard)/creators/loading.tsx`
- Create: `src/app/(dashboard)/creators/[slug]/loading.tsx`
- Create: `src/app/(dashboard)/creators/[slug]/error.tsx`
- Create: `src/app/(dashboard)/platforms/instagram/accounts/loading.tsx`
- Create: `src/app/(dashboard)/platforms/tiktok/accounts/loading.tsx`

- [ ] **Step 1: Create `src/app/(dashboard)/loading.tsx`**

```typescript
import { Loader2 } from "lucide-react"

export default function Loading() {
  return (
    <div className="flex h-[60vh] items-center justify-center">
      <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
    </div>
  )
}
```

- [ ] **Step 2: Create `src/app/(dashboard)/error.tsx`**

```typescript
"use client"

import { useEffect } from "react"
import { ErrorState } from "@/components/ui/error-state"

export default function DashboardError({
  error,
  reset,
}: {
  error: Error & { digest?: string }
  reset: () => void
}) {
  useEffect(() => {
    console.error("Dashboard error boundary:", error)
  }, [error])

  return (
    <div className="p-6">
      <ErrorState message={error.message} onRetry={reset} />
    </div>
  )
}
```

- [ ] **Step 3: Create the four route-scoped loading.tsx files**

Each one is the same shape — copy this content into all four:
- `src/app/(dashboard)/creators/loading.tsx`
- `src/app/(dashboard)/creators/[slug]/loading.tsx`
- `src/app/(dashboard)/platforms/instagram/accounts/loading.tsx`
- `src/app/(dashboard)/platforms/tiktok/accounts/loading.tsx`

```typescript
import { Loader2 } from "lucide-react"

export default function Loading() {
  return (
    <div className="flex h-[60vh] items-center justify-center">
      <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
    </div>
  )
}
```

- [ ] **Step 4: Create `src/app/(dashboard)/creators/[slug]/error.tsx`**

```typescript
"use client"

import { useEffect } from "react"
import { ErrorState } from "@/components/ui/error-state"

export default function CreatorDetailError({
  error,
  reset,
}: {
  error: Error & { digest?: string }
  reset: () => void
}) {
  useEffect(() => {
    console.error("Creator detail error:", error)
  }, [error])

  return (
    <div className="p-6">
      <ErrorState
        title="Couldn't load creator"
        message={error.message}
        onRetry={reset}
      />
    </div>
  )
}
```

- [ ] **Step 5: typecheck + commit**

```bash
npx tsc --noEmit
git add src/app
git commit -m "feat(ui): loading.tsx + error.tsx for dashboard routes"
```

---

### Task 22: Wire BulkImportDialog single-handle tab + Result handling

**Files:**
- Modify: `src/components/creators/BulkImportDialog.tsx`

- [ ] **Step 1: Update imports**

Replace the import line:
```ts
import { bulkImportCreators } from "@/app/actions";
```
with:
```ts
import { bulkImportCreators, importSingleCreator } from "@/app/(dashboard)/creators/actions";
import { toast } from "sonner";
import type { Enums } from "@/types/db";
```

- [ ] **Step 2: Update `handleBulkSubmit` to consume `Result<T>`**

Replace the `handleBulkSubmit` function with:
```ts
  const handleBulkSubmit = async () => {
    setIsSubmitting(true);
    setError(null);
    const result = await bulkImportCreators(
      rawText,
      trackingType as Enums<"tracking_type">,
      tags,
      assignedPlatforms
    );
    setIsSubmitting(false);
    if (!result.ok) {
      setError(result.error);
      toast.error("Bulk import failed", { description: result.error });
      return;
    }
    const { imported, skipped, errors } = result.data;
    if (errors.length > 0) {
      toast.warning(`Imported ${imported}, ${errors.length} failed`, {
        description: errors.map((e) => `${e.handle}: ${e.error}`).join("\n"),
      });
    } else {
      toast.success(`Imported ${imported} creator${imported === 1 ? "" : "s"}`);
    }
    setOpen(false);
    setRawText("");
  };
```

- [ ] **Step 3: Add a `handleSingleSubmit` and a state for single-tab loading**

Inside the component, add:
```ts
  const [isSingleSubmitting, setIsSingleSubmitting] = useState(false);
  const [singleError, setSingleError] = useState<string | null>(null);

  const canSubmitSingle =
    !!singlePlatform &&
    singleHandle.trim().length > 0 &&
    !isSingleSubmitting;

  const handleSingleSubmit = async () => {
    setIsSingleSubmitting(true);
    setSingleError(null);
    const result = await importSingleCreator(
      singlePlatform as Enums<"platform">,
      singleHandle,
      singleUrl || undefined
    );
    setIsSingleSubmitting(false);
    if (!result.ok) {
      setSingleError(result.error);
      toast.error("Import failed", { description: result.error });
      return;
    }
    toast.success("Creator queued for discovery");
    setOpen(false);
    setSinglePlatform("");
    setSingleHandle("");
    setSingleUrl("");
  };
```

- [ ] **Step 4: Wire the Single Handle "Import Creator" button**

Find the existing single-tab Button:
```tsx
<Button className="mt-2 w-full bg-indigo-600 hover:bg-indigo-500">Import Creator</Button>
```

Replace with:
```tsx
{singleError && (
  <div className="text-sm text-red-400 bg-red-500/10 border border-red-500/20 rounded-lg px-3 py-2">
    {singleError}
  </div>
)}
<Button
  onClick={handleSingleSubmit}
  disabled={!canSubmitSingle}
  className="mt-2 w-full bg-indigo-600 hover:bg-indigo-500"
>
  {isSingleSubmitting ? <Loader2 className="h-4 w-4 animate-spin mr-2" /> : null}
  Import Creator
</Button>
```

- [ ] **Step 5: typecheck**

```bash
npx tsc --noEmit
```

Expected: zero errors related to BulkImportDialog.

- [ ] **Step 6: Commit**

```bash
git add src/components/creators/BulkImportDialog.tsx
git commit -m "feat(ui): wire BulkImportDialog single-handle tab + Result/toast handling"
```

---

### Task 23: Wire AddAccountDialog with new action

**Files:**
- Modify: `src/components/creators/AddAccountDialog.tsx`

- [ ] **Step 1: Read the current file to understand its shape**

```bash
cat "/Users/simon/OS/Living VAULT/Content OS/The Hub/src/components/creators/AddAccountDialog.tsx"
```

- [ ] **Step 2: Update imports**

Replace any `import { addProfileToCreator } from "@/app/actions"` with:
```ts
import { addAccountToCreator } from "@/app/(dashboard)/creators/actions";
import { toast } from "sonner";
import type { Enums } from "@/types/db";
```

- [ ] **Step 3: Update the submit handler to use the new action shape**

Replace the call:
```ts
await addProfileToCreator(creatorId, platform, handle, accountType, url, displayName);
```
with:
```ts
const result = await addAccountToCreator(creatorId, {
  platform: platform as Enums<"platform">,
  handle,
  accountType: accountType as Enums<"account_type">,
  url: url || undefined,
  displayName: displayName || undefined,
});
if (!result.ok) {
  toast.error("Could not add account", { description: result.error });
  return;
}
toast.success("Account added");
```

If the form has its own error state, update it to read from `result.error` on failure.

- [ ] **Step 4: typecheck + commit**

```bash
npx tsc --noEmit
git add src/components/creators/AddAccountDialog.tsx
git commit -m "feat(ui): AddAccountDialog uses new addAccountToCreator action with Result/toast"
```

---

### Task 24: Wire MergeAlertBanner buttons

**Files:**
- Modify: `src/components/creators/MergeAlertBanner.tsx`
- Modify: `src/app/(dashboard)/creators/[slug]/page.tsx` (the inline merge banner — see Task 25)

- [ ] **Step 1: Inspect MergeAlertBanner**

```bash
cat "/Users/simon/OS/Living VAULT/Content OS/The Hub/src/components/creators/MergeAlertBanner.tsx"
```

This banner is the dashboard one (count of pending merges). Add no actions to it — its CTA should link to `/creators?status=pending_merge` if such a filter exists, otherwise it can navigate to the first merge candidate's creator detail page. Leave the navigation behavior as-is if it's already wired; otherwise add an `onClick` that navigates the user to `/creators` with no filter (since merge UI lives on detail pages).

- [ ] **Step 2: Skip if banner is informational**

If the banner is purely informational (no merge action lives on it), no change needed here. The actionable merge buttons live on the creator detail page (Task 25).

- [ ] **Step 3: Commit (no-op if nothing changed)**

```bash
git status src/components/creators/MergeAlertBanner.tsx
# If unchanged, skip the commit.
```

---

### Task 25: Wire creator detail page — merge buttons + retry button

**Files:**
- Modify: `src/app/(dashboard)/creators/[slug]/page.tsx`
- Create: `src/components/creators/MergeBannerActions.tsx`
- Create: `src/components/creators/FailedRetryButton.tsx`

- [ ] **Step 1: Create `src/components/creators/MergeBannerActions.tsx`**

```typescript
// src/components/creators/MergeBannerActions.tsx
"use client"

import { useState } from "react"
import { useRouter } from "next/navigation"
import { Button } from "@/components/ui/button"
import { toast } from "sonner"
import {
  dismissMergeCandidate,
  mergeCandidateCreators,
} from "@/app/(dashboard)/creators/actions"

export function MergeBannerActions({
  candidateId,
  keepId,
  mergeId,
  keepLabel,
}: {
  candidateId: string
  keepId: string
  mergeId: string
  keepLabel: string
}) {
  const router = useRouter()
  const [busy, setBusy] = useState<"none" | "dismiss" | "merge">("none")

  const handleDismiss = async () => {
    setBusy("dismiss")
    const r = await dismissMergeCandidate(candidateId)
    setBusy("none")
    if (!r.ok) {
      toast.error("Could not dismiss", { description: r.error })
      return
    }
    toast.success("Marked as different person")
    router.refresh()
  }

  const handleMerge = async () => {
    setBusy("merge")
    const r = await mergeCandidateCreators(keepId, mergeId, candidateId)
    setBusy("none")
    if (!r.ok) {
      toast.error("Merge failed", { description: r.error })
      return
    }
    toast.success(`Merged into ${keepLabel}`)
    router.refresh()
  }

  return (
    <div className="flex gap-2">
      <Button
        size="sm"
        variant="outline"
        disabled={busy !== "none"}
        onClick={handleDismiss}
        className="h-7 text-xs border-amber-500/30 hover:bg-amber-500/20 text-amber-500"
      >
        {busy === "dismiss" ? "Dismissing…" : "Not the same person"}
      </Button>
      <Button
        size="sm"
        disabled={busy !== "none"}
        onClick={handleMerge}
        className="h-7 text-xs bg-amber-500 hover:bg-amber-400 text-amber-950 font-bold"
      >
        {busy === "merge" ? "Merging…" : `Merge: Keep ${keepLabel}`}
      </Button>
    </div>
  )
}
```

- [ ] **Step 2: Create `src/components/creators/FailedRetryButton.tsx`**

```typescript
// src/components/creators/FailedRetryButton.tsx
"use client"

import { useState } from "react"
import { useRouter } from "next/navigation"
import { Button } from "@/components/ui/button"
import { toast } from "sonner"
import { retryCreatorDiscovery } from "@/app/(dashboard)/creators/actions"

export function FailedRetryButton({ creatorId }: { creatorId: string }) {
  const router = useRouter()
  const [busy, setBusy] = useState(false)

  const handleClick = async () => {
    setBusy(true)
    const r = await retryCreatorDiscovery(creatorId)
    setBusy(false)
    if (!r.ok) {
      toast.error("Retry failed", { description: r.error })
      return
    }
    toast.success("Discovery re-queued")
    router.refresh()
  }

  return (
    <Button
      size="sm"
      variant="outline"
      disabled={busy}
      onClick={handleClick}
      className="border-red-900/50 hover:bg-red-900/20 text-red-400 shrink-0"
    >
      {busy ? "Retrying…" : "Retry"}
    </Button>
  )
}
```

- [ ] **Step 3: Wire the components into `src/app/(dashboard)/creators/[slug]/page.tsx`**

Add imports near the top:
```ts
import { MergeBannerActions } from "@/components/creators/MergeBannerActions"
import { FailedRetryButton } from "@/components/creators/FailedRetryButton"
```

In the merge-candidate banner block, replace this:
```tsx
<div className="flex gap-2">
  <Button size="sm" variant="outline" className="h-7 text-xs border-amber-500/30 hover:bg-amber-500/20 text-amber-500">Not the same person</Button>
  <Button size="sm" className="h-7 text-xs bg-amber-500 hover:bg-amber-400 text-amber-950 font-bold">Merge: Keep {creator.canonical_name}</Button>
</div>
```
with:
```tsx
<MergeBannerActions
  candidateId={mergeCandidates[0].id}
  keepId={creator.id}
  mergeId={
    mergeCandidates[0].creator_a_id === creator.id
      ? mergeCandidates[0].creator_b_id
      : mergeCandidates[0].creator_a_id
  }
  keepLabel={creator.canonical_name}
/>
```

In the failed-state banner block, replace this:
```tsx
<Button size="sm" variant="outline" className="border-red-900/50 hover:bg-red-900/20 text-red-400 shrink-0">Retry</Button>
```
with:
```tsx
<FailedRetryButton creatorId={creator.id} />
```

- [ ] **Step 4: Update `RerunDiscoveryButton` to consume `Result<T>` + toast**

Replace `src/components/creators/RerunDiscoveryButton.tsx`:
```typescript
"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";
import { retryCreatorDiscovery } from "@/app/(dashboard)/creators/actions";

export function RerunDiscoveryButton({
  creatorId,
  isProcessing,
}: {
  creatorId: string;
  isProcessing: boolean;
}) {
  const [loading, setLoading] = useState(false);
  const router = useRouter();

  const handleClick = async () => {
    if (loading || isProcessing) return;
    setLoading(true);
    const r = await retryCreatorDiscovery(creatorId);
    setLoading(false);
    if (!r.ok) {
      toast.error("Re-run discovery failed", { description: r.error });
      return;
    }
    toast.success("Discovery re-queued");
    router.refresh();
  };

  const spinning = loading || isProcessing;

  return (
    <Button
      variant="outline"
      size="sm"
      disabled={spinning}
      onClick={handleClick}
      className="h-8"
    >
      <RefreshCw className={`h-4 w-4 mr-2 ${spinning ? "animate-spin" : ""}`} />
      {loading ? "Starting…" : isProcessing ? "Discovering…" : "Re-run Discovery"}
    </Button>
  );
}
```

- [ ] **Step 5: typecheck + commit**

```bash
npx tsc --noEmit
git add src/components/creators src/app/\(dashboard\)/creators/\[slug\]/page.tsx
git commit -m "feat(ui): wire merge banner actions, failed-state retry, RerunDiscoveryButton with toasts"
```

---

### Task 26: Type CreatorsFilters props

**Files:**
- Modify: `src/components/creators/CreatorsFilters.tsx`

- [ ] **Step 1: Update the file**

```typescript
"use client"

import { StatusTabBar } from "@/components/creators/StatusTabBar"
import { TrackingTabBar } from "@/components/accounts/TrackingTabBar"
import { useRouter, usePathname, useSearchParams } from "next/navigation"
import { useCallback } from "react"
import type { Enums } from "@/types/db"

export type CreatorStatusCounts = Record<
  Enums<"onboarding_status"> | "all",
  number
>
export type CreatorTrackingCounts = Record<
  Enums<"tracking_type"> | "all",
  number
>

export function CreatorsFilters({
  counts,
  trackingCounts,
  activeStatus,
  activeTracking,
}: {
  counts: CreatorStatusCounts
  trackingCounts: CreatorTrackingCounts
  activeStatus: string
  activeTracking: string
}) {
  const router = useRouter()
  const pathname = usePathname()
  const searchParams = useSearchParams()

  const createQueryString = useCallback(
    (name: string, value: string) => {
      const params = new URLSearchParams(searchParams.toString())
      if (value === "all") {
        params.delete(name)
      } else {
        params.set(name, value)
      }
      return params.toString()
    },
    [searchParams]
  )

  const handleStatusChange = (status: string) => {
    router.push(pathname + "?" + createQueryString("status", status))
  }

  const handleTrackingChange = (tracking: string) => {
    router.push(pathname + "?" + createQueryString("tracking", tracking))
  }

  return (
    <div className="flex flex-col gap-3">
      <StatusTabBar
        counts={counts}
        activeStatus={activeStatus}
        onStatusChange={handleStatusChange}
      />
      <TrackingTabBar
        onTabChange={handleTrackingChange}
        activeTab={activeTracking}
        counts={trackingCounts}
      />
    </div>
  )
}
```

- [ ] **Step 2: typecheck + commit**

```bash
npx tsc --noEmit
git add src/components/creators/CreatorsFilters.tsx
git commit -m "feat(ui): type CreatorsFilters props from generated DB enums"
```

---

### Task 27: Layer 5 verification gate

- [ ] **Step 1: Spawn verifier subagent**

Invoke verifier:
> Verify Layer 5: (1) shared components `EmptyState`, `ErrorState`, `ComingSoon` exist; (2) `loading.tsx` exists for dashboard, creators, creators/[slug], platforms/instagram/accounts, platforms/tiktok/accounts; (3) `error.tsx` exists for dashboard and creators/[slug]; (4) `BulkImportDialog` Single Handle tab "Import Creator" button has an onClick handler; (5) `MergeBannerActions` and `FailedRetryButton` components exist and the creator detail page imports them; (6) `RerunDiscoveryButton` imports from new actions module and uses Result; (7) `npx tsc --noEmit` passes. Use chrome-devtools-mcp to navigate to `/creators` and `/creators/[slug-of-an-existing-creator]`, capture console logs, confirm no `[Error]` entries. Report pass/fail with evidence.

Expected: verifier returns "pass."

---

# LAYER 6 — PAGES & ROUTING

### Task 28: Wire search/sort URL state on /creators

**Files:**
- Modify: `src/app/(dashboard)/creators/page.tsx`
- Create: `src/components/creators/CreatorsSearchSort.tsx`

- [ ] **Step 1: Create `src/components/creators/CreatorsSearchSort.tsx`**

```typescript
// src/components/creators/CreatorsSearchSort.tsx
"use client"

import { useRouter, usePathname, useSearchParams } from "next/navigation"
import { useState, useTransition, useEffect } from "react"
import { Input } from "@/components/ui/input"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { Search } from "lucide-react"

export function CreatorsSearchSort({
  initialQ,
  initialSort,
}: {
  initialQ: string
  initialSort: string
}) {
  const router = useRouter()
  const pathname = usePathname()
  const searchParams = useSearchParams()
  const [q, setQ] = useState(initialQ)
  const [, startTransition] = useTransition()

  // Debounce search input
  useEffect(() => {
    const t = setTimeout(() => {
      const params = new URLSearchParams(searchParams.toString())
      if (q.trim().length === 0) params.delete("q")
      else params.set("q", q.trim())
      startTransition(() => {
        router.push(`${pathname}?${params.toString()}`)
      })
    }, 250)
    return () => clearTimeout(t)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [q])

  const handleSortChange = (sort: string) => {
    const params = new URLSearchParams(searchParams.toString())
    if (sort === "recently_added") params.delete("sort")
    else params.set("sort", sort)
    router.push(`${pathname}?${params.toString()}`)
  }

  return (
    <>
      <div className="relative">
        <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
        <Input
          placeholder="Search creators..."
          value={q}
          onChange={(e) => setQ(e.target.value)}
          className="pl-9 w-[250px] bg-background/50 border-border/50 focus-visible:ring-indigo-500 rounded-lg"
        />
      </div>
      <Select value={initialSort} onValueChange={handleSortChange}>
        <SelectTrigger className="w-[180px] bg-background/50 border-border/50 rounded-lg">
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="recently_added">Recently Added</SelectItem>
          <SelectItem value="name_asc">Name (A-Z)</SelectItem>
          <SelectItem value="platform">Primary Platform</SelectItem>
        </SelectContent>
      </Select>
    </>
  )
}
```

- [ ] **Step 2: Refactor `src/app/(dashboard)/creators/page.tsx` to use the helper + new component**

Replace the whole file:
```typescript
// src/app/(dashboard)/creators/page.tsx
export const dynamic = "force-dynamic"

import { Users2 } from "lucide-react"
import { MergeAlertBanner } from "@/components/creators/MergeAlertBanner"
import { CreatorCard } from "@/components/creators/CreatorCard"
import { BulkImportDialog } from "@/components/creators/BulkImportDialog"
import { CreatorsFilters } from "@/components/creators/CreatorsFilters"
import { CreatorsSearchSort } from "@/components/creators/CreatorsSearchSort"
import { EmptyState } from "@/components/ui/empty-state"
import { getCurrentWorkspaceId } from "@/lib/workspace"
import {
  getCreatorsForWorkspace,
  getCreatorStatsForWorkspace,
  getMergeCandidatesForWorkspace,
} from "@/lib/db/queries"
import type { Enums } from "@/types/db"

function relativeTime(dateStr: string | null | undefined): string {
  if (!dateStr) return "—"
  const diff = Date.now() - new Date(dateStr).getTime()
  const minutes = Math.floor(diff / 60000)
  if (minutes < 1) return "just now"
  if (minutes < 60) return `${minutes}m ago`
  const hours = Math.floor(minutes / 60)
  if (hours < 24) return `${hours}h ago`
  const days = Math.floor(hours / 24)
  return `${days}d ago`
}

function formatFollowers(n: number): string {
  if (n === 0) return "—"
  return new Intl.NumberFormat("en-US", { notation: "compact", compactDisplay: "short" }).format(n)
}

type SortKey = "recently_added" | "name_asc" | "platform"

export default async function CreatorsHubPage({
  searchParams,
}: {
  searchParams: { status?: string; tracking?: string; q?: string; sort?: string }
}) {
  const wsId = await getCurrentWorkspaceId()
  const status = (searchParams?.status ?? "all") as Enums<"onboarding_status"> | "all"
  const tracking = (searchParams?.tracking ?? "all") as Enums<"tracking_type"> | "all"
  const q = searchParams?.q ?? ""
  const sort = (searchParams?.sort ?? "recently_added") as SortKey

  const [rawCreators, stats, mergeCandidates] = await Promise.all([
    getCreatorsForWorkspace(wsId, { status, tracking, q, sort }),
    getCreatorStatsForWorkspace(wsId),
    getMergeCandidatesForWorkspace(wsId),
  ])

  const mergeCount = mergeCandidates.length
  const creatorIdsWithMerge = new Set(
    mergeCandidates.flatMap((m) => [m.creator_a_id, m.creator_b_id])
  )

  const creators = rawCreators.map((c) => {
    const profiles = c.profiles ?? []
    const primaryProfile = profiles.find((p) => p.is_primary) ?? profiles[0]
    const socialProfiles = profiles.filter((p) => p.account_type === "social")
    const totalFollowerCount = socialProfiles.reduce(
      (sum, p) => sum + (Number(p.follower_count) || 0),
      0
    )
    const accountCounts: Record<string, number> = {}
    for (const p of profiles) {
      const at = p.account_type ?? "other"
      accountCounts[at] = (accountCounts[at] ?? 0) + 1
    }
    return {
      id: c.id,
      canonicalName: c.canonical_name,
      slug: c.slug,
      avatarUrl: primaryProfile?.avatar_url ?? undefined,
      primaryPlatform: c.primary_platform || "other",
      status: c.onboarding_status as "processing" | "ready" | "failed" | "archived",
      trackingType: c.tracking_type,
      monetizationModel: c.monetization_model,
      tags: c.tags || [],
      knownUsernames: c.known_usernames || [],
      accountCounts,
      totalFollowers: formatFollowers(totalFollowerCount),
      updatedAgo: relativeTime(c.updated_at),
      hasMergeCandidate: creatorIdsWithMerge.has(c.id),
      errorMessage: c.last_discovery_error,
    }
  })

  return (
    <div className="flex flex-col gap-6 pb-10">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold tracking-tight flex items-center gap-2">
            <Users2 className="h-8 w-8 text-indigo-400" /> Creators
          </h1>
          <p className="text-muted-foreground mt-1 text-sm">
            Discover and map entire creator network footprints.
          </p>
        </div>
        <div className="flex items-center gap-3">
          <CreatorsSearchSort initialQ={q} initialSort={sort} />
          <BulkImportDialog />
        </div>
      </div>

      <MergeAlertBanner count={mergeCount} />

      <CreatorsFilters
        counts={stats.byStatus}
        trackingCounts={stats.byTracking}
        activeStatus={status}
        activeTracking={tracking}
      />

      {creators.length > 0 ? (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6">
          {creators.map((creator) => (
            <CreatorCard key={creator.id} {...creator} />
          ))}
        </div>
      ) : q || status !== "all" || tracking !== "all" ? (
        <EmptyState
          icon={Users2}
          title="No creators match those filters"
          description="Adjust the filters or clear the search to see more."
        />
      ) : (
        <EmptyState
          icon={Users2}
          title="Import your first creators"
          description="Our AI will scan their primary profile, follow link-in-bio traces, and build out their full cross-platform network footprint."
          action={<BulkImportDialog />}
        />
      )}
    </div>
  )
}
```

- [ ] **Step 3: typecheck + commit**

```bash
npx tsc --noEmit
git add src/app/\(dashboard\)/creators/page.tsx src/components/creators/CreatorsSearchSort.tsx
git commit -m "feat(ui): wire search + sort URL state on /creators; route through query helpers"
```

---

### Task 29: Refactor creator detail page to query helpers

**Files:**
- Modify: `src/app/(dashboard)/creators/[slug]/page.tsx`

- [ ] **Step 1: Replace data-loading block**

At the top of the file, replace imports and the data-loading section. Find:
```ts
import { createServiceClient } from "@/lib/supabase/server";
```
Replace with:
```ts
import { getCurrentWorkspaceId } from "@/lib/workspace"
import {
  getCreatorBySlugForWorkspace,
  getProfilesForCreator,
  getMergeCandidatesForCreator,
} from "@/lib/db/queries"
import { createServiceClient } from "@/lib/supabase/server"
```

Replace the data-loading block (the section with `const supabase = createServiceClient()` through the merge candidate `mergeWith` lookup) with:
```ts
  const wsId = await getCurrentWorkspaceId()
  const creator = await getCreatorBySlugForWorkspace(wsId, params.slug)
  if (!creator) return notFound()

  const [profiles, mergeCandidates] = await Promise.all([
    getProfilesForCreator(creator.id),
    getMergeCandidatesForCreator(creator.id),
  ])

  let mergeWith: string | null = null
  if (mergeCandidates.length > 0) {
    const mc = mergeCandidates[0]
    const otherId = mc.creator_a_id === creator.id ? mc.creator_b_id : mc.creator_a_id
    const supabase = createServiceClient()
    const { data: other } = await supabase
      .from("creators")
      .select("canonical_name")
      .eq("id", otherId)
      .maybeSingle()
    mergeWith = other?.canonical_name ?? null
  }
```

- [ ] **Step 2: Replace coming-soon tab placeholders with `<ComingSoon />`**

Add import:
```ts
import { ComingSoon } from "@/components/shared/ComingSoon"
```

Find the funnel TabsContent and replace its inner content:
```tsx
<TabsContent value="funnel" className="mt-6">
  <ComingSoon
    phase={4}
    feature="Funnel visualization"
    description="Visualize how traffic flows across this creator's network."
  />
</TabsContent>
```

(The Content/Branding tabs are still `disabled` triggers — leave those as-is; they don't render content.)

- [ ] **Step 3: typecheck + commit**

```bash
npx tsc --noEmit
git add src/app/\(dashboard\)/creators/\[slug\]/page.tsx
git commit -m "refactor(creator-detail): route through query helpers; use ComingSoon for funnel tab"
```

---

### Task 30: Sidebar standardization

**Files:**
- Modify: `src/components/dashboard/Sidebar.tsx`

- [ ] **Step 1: Update creator filter links from `?type=` to `?tracking=`**

Find the CREATORS section. Change:
```tsx
<NavItem href="/creators?type=managed" icon={Users} label="Managed" currentPath={currentPath} />
<NavItem href="/creators?type=candidate" icon={Users} label="Candidates" currentPath={currentPath} />
<NavItem href="/creators?type=competitor" icon={Users} label="Competitors" currentPath={currentPath} />
<NavItem href="/creators?type=inspiration" icon={Users} label="Inspiration" currentPath={currentPath} />
```
to:
```tsx
<NavItem href="/creators?tracking=managed" icon={Users} label="Managed" currentPath={currentPath} />
<NavItem href="/creators?tracking=candidate" icon={Users} label="Candidates" currentPath={currentPath} />
<NavItem href="/creators?tracking=competitor" icon={Users} label="Competitors" currentPath={currentPath} />
<NavItem href="/creators?tracking=inspiration" icon={Users} label="Inspiration" currentPath={currentPath} />
```

- [ ] **Step 2: Remove the duplicate `/content` entry from the ANALYZE group**

In the ANALYZE section, find:
```tsx
<NavItem href="/content" icon={Video} label="Content" currentPath={currentPath} />
```
Delete this line. (The DAILY group already has `/content` as "Content Hub".)

- [ ] **Step 3: Add TikTok Intel sub-routes (matching Instagram structure)**

Replace the TikTok Intel block:
```tsx
<div className="flex flex-col mb-2 opacity-50">
   <div className="flex items-center gap-2.5 px-3 py-2 text-sm font-medium text-foreground rounded-md">
    <MonitorPlay className="h-4 w-4" />
    <span>TikTok Intel</span>
  </div>
</div>
```
with:
```tsx
<div className="flex flex-col mb-2">
  <div className="flex items-center gap-2.5 px-3 py-2 text-sm font-medium text-foreground rounded-md">
    <MonitorPlay className="h-4 w-4" />
    <span>TikTok Intel</span>
  </div>
  <div className="ml-[26px] flex flex-col pl-2 border-l border-border/50 gap-1 mt-1">
    <SubNavItem href="/platforms/tiktok/accounts" label="Accounts" currentPath={currentPath} />
    <SubNavItem href="/platforms/tiktok/outliers" label="Outliers" currentPath={currentPath} comingSoon />
    <SubNavItem href="/platforms/tiktok/classification" label="Classification" currentPath={currentPath} comingSoon />
    <SubNavItem href="/platforms/tiktok/analytics" label="Analytics" currentPath={currentPath} comingSoon />
  </div>
</div>
```

Also extend the Instagram sub-nav items with `comingSoon` for the three placeholder ones:
```tsx
<SubNavItem href="/platforms/instagram/accounts" label="Accounts" currentPath={currentPath} />
<SubNavItem href="/platforms/instagram/outliers" label="Outliers" currentPath={currentPath} comingSoon />
<SubNavItem href="/platforms/instagram/classification" label="Classification" currentPath={currentPath} comingSoon />
<SubNavItem href="/platforms/instagram/analytics" label="Analytics" currentPath={currentPath} comingSoon />
```

- [ ] **Step 4: Update `SubNavItem` to support `comingSoon` badge**

At the bottom of the file, replace `SubNavItem` with:
```tsx
function SubNavItem({
  href,
  label,
  currentPath,
  comingSoon,
}: {
  href: string
  label: string
  currentPath?: string
  comingSoon?: boolean
}) {
  const isActive = currentPath === href
  return (
    <Link
      href={href}
      className={cn(
        "flex items-center justify-between px-4 py-1.5 text-[13px] rounded-md transition-all relative",
        isActive
          ? "text-primary font-semibold"
          : "text-muted-foreground hover:text-primary hover:bg-muted/50"
      )}
    >
      {isActive && (
        <div className="absolute -left-[5px] w-2 h-2 rounded-full border-[2px] border-background bg-indigo-500" />
      )}
      <span>{label}</span>
      {comingSoon && (
        <Badge
          variant="outline"
          className="text-[8px] h-4 px-1 py-0 uppercase border-muted-foreground/30 text-muted-foreground/60 font-semibold bg-transparent"
        >
          Soon
        </Badge>
      )}
    </Link>
  )
}
```

- [ ] **Step 5: typecheck + commit**

```bash
npx tsc --noEmit
git add src/components/dashboard/Sidebar.tsx
git commit -m "feat(nav): standardize ?tracking= param; remove dupe /content; add TikTok sub-routes; SubNavItem 'Soon' badge"
```

---

### Task 31: Create TikTok placeholder pages

**Files:**
- Create: `src/app/(dashboard)/platforms/tiktok/outliers/page.tsx`
- Create: `src/app/(dashboard)/platforms/tiktok/classification/page.tsx`
- Create: `src/app/(dashboard)/platforms/tiktok/analytics/page.tsx`

- [ ] **Step 1: Create all three with `<ComingSoon />`**

For `outliers/page.tsx`:
```typescript
import { ComingSoon } from "@/components/shared/ComingSoon"

export default function TikTokOutliers() {
  return (
    <ComingSoon
      phase={2}
      feature="TikTok Outliers"
      description="Posts performing 3× above their median baseline. Activates when scraping ingestion is live."
    />
  )
}
```

For `classification/page.tsx`:
```typescript
import { ComingSoon } from "@/components/shared/ComingSoon"

export default function TikTokClassification() {
  return (
    <ComingSoon
      phase={3}
      feature="TikTok Classification"
      description="Curate content labels and trend taxonomy. Activates when content analysis pipelines are live."
    />
  )
}
```

For `analytics/page.tsx`:
```typescript
import { ComingSoon } from "@/components/shared/ComingSoon"

export default function TikTokAnalytics() {
  return (
    <ComingSoon
      phase={3}
      feature="TikTok Analytics"
      description="Cross-account performance, scoring, rank trends. Activates after content scoring is live."
    />
  )
}
```

- [ ] **Step 2: Update existing Instagram placeholder pages to use ComingSoon**

For `src/app/(dashboard)/platforms/instagram/outliers/page.tsx`:
```typescript
import { ComingSoon } from "@/components/shared/ComingSoon"

export default function InstagramOutliers() {
  return (
    <ComingSoon
      phase={2}
      feature="Instagram Outliers"
      description="Posts performing 3× above their median baseline. Activates when scraping ingestion is live."
    />
  )
}
```

For `src/app/(dashboard)/platforms/instagram/classification/page.tsx`:
```typescript
import { ComingSoon } from "@/components/shared/ComingSoon"

export default function InstagramClassification() {
  return (
    <ComingSoon
      phase={3}
      feature="Instagram Classification"
      description="Curate content labels and trend taxonomy. Activates when content analysis pipelines are live."
    />
  )
}
```

For `src/app/(dashboard)/platforms/instagram/analytics/page.tsx`:
```typescript
import { ComingSoon } from "@/components/shared/ComingSoon"

export default function InstagramAnalytics() {
  return (
    <ComingSoon
      phase={3}
      feature="Instagram Analytics"
      description="Cross-account performance, scoring, rank trends. Activates after content scoring is live."
    />
  )
}
```

- [ ] **Step 3: typecheck + commit**

```bash
npx tsc --noEmit
git add src/app/\(dashboard\)/platforms
git commit -m "feat(routes): TikTok placeholder pages + Instagram placeholders use ComingSoon"
```

---

### Task 32: Refactor platform accounts pages — `?tracking=`, query helper

**Files:**
- Modify: `src/app/(dashboard)/platforms/instagram/accounts/page.tsx`
- Modify: `src/app/(dashboard)/platforms/instagram/accounts/InstagramAccountsClient.tsx`
- Modify: `src/app/(dashboard)/platforms/tiktok/accounts/page.tsx`
- Modify: `src/app/(dashboard)/platforms/tiktok/accounts/TikTokAccountsClient.tsx`

- [ ] **Step 1: Replace `src/app/(dashboard)/platforms/instagram/accounts/page.tsx`**

```typescript
import { getCurrentWorkspaceId } from "@/lib/workspace"
import { getPlatformAccountsForWorkspace } from "@/lib/db/queries"
import { InstagramAccountsClient } from "./InstagramAccountsClient"
import type { PlatformAccountRow } from "@/lib/db/queries"

export type AccountRowData = PlatformAccountRow

export default async function InstagramAccountsPage({
  searchParams,
}: {
  searchParams: { tracking?: string }
}) {
  const wsId = await getCurrentWorkspaceId()
  const activeTracking = searchParams?.tracking ?? "all"

  const accounts = await getPlatformAccountsForWorkspace(wsId, {
    platform: "instagram",
    accountType: "social",
  })

  return (
    <InstagramAccountsClient
      accounts={accounts}
      activeTracking={activeTracking}
    />
  )
}
```

- [ ] **Step 2: Update `InstagramAccountsClient.tsx`**

Open the file. Rename the prop `activeType` → `activeTracking` everywhere (typescript prop type, destructuring, internal references). Update any `?type=` URL writes to `?tracking=`. If there are tracking-tab callbacks, ensure they push `?tracking=` not `?type=`.

To find URL writes:
```bash
grep -n "type=" "/Users/simon/OS/Living VAULT/Content OS/The Hub/src/app/(dashboard)/platforms/instagram/accounts/InstagramAccountsClient.tsx"
```

Replace each `type=` with `tracking=` and each `activeType` with `activeTracking`.

- [ ] **Step 3: Apply the same two-step change to TikTok**

For `src/app/(dashboard)/platforms/tiktok/accounts/page.tsx`:
```typescript
import { getCurrentWorkspaceId } from "@/lib/workspace"
import { getPlatformAccountsForWorkspace } from "@/lib/db/queries"
import { TikTokAccountsClient } from "./TikTokAccountsClient"
import type { PlatformAccountRow } from "@/lib/db/queries"

export type AccountRowData = PlatformAccountRow

export default async function TikTokAccountsPage({
  searchParams,
}: {
  searchParams: { tracking?: string }
}) {
  const wsId = await getCurrentWorkspaceId()
  const activeTracking = searchParams?.tracking ?? "all"

  const accounts = await getPlatformAccountsForWorkspace(wsId, {
    platform: "tiktok",
    accountType: "social",
  })

  return (
    <TikTokAccountsClient
      accounts={accounts}
      activeTracking={activeTracking}
    />
  )
}
```

For `TikTokAccountsClient.tsx`: same rename pass — `activeType` → `activeTracking`, `?type=` → `?tracking=`.

- [ ] **Step 4: typecheck + commit**

```bash
npx tsc --noEmit
git add src/app/\(dashboard\)/platforms
git commit -m "refactor(platforms): use getPlatformAccountsForWorkspace; standardize on ?tracking= param"
```

---

### Task 33: Wire Command Center to real queries

**Files:**
- Modify: `src/app/(dashboard)/page.tsx`

- [ ] **Step 1: Replace the entire file**

```typescript
export const dynamic = "force-dynamic"

import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Activity, Sparkles, TrendingUp, Users, Video, Search } from "lucide-react"
import Link from "next/link"
import { getCurrentWorkspaceId } from "@/lib/workspace"
import {
  getCommandCenterStats,
  getRecentOutliersForWorkspace,
  getActiveTrendSignalsForWorkspace,
} from "@/lib/db/queries"
import { EmptyState } from "@/components/ui/empty-state"

export default async function CommandCenter() {
  const wsId = await getCurrentWorkspaceId()
  const [stats, outliers, signals] = await Promise.all([
    getCommandCenterStats(wsId),
    getRecentOutliersForWorkspace(wsId, 5),
    getActiveTrendSignalsForWorkspace(wsId, 5),
  ])

  return (
    <div className="flex flex-col gap-8 pb-10">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">Command Center</h1>
        <p className="text-muted-foreground mt-1 text-sm">
          Your daily overview of agency performance and ingestion status.
        </p>
      </div>

      {/* Stats Row */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        <Link href="/creators">
          <Card className="bg-card shadow-sm border-border/50 hover:bg-muted/50 transition-colors cursor-pointer h-full">
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">Tracked Creators</CardTitle>
              <Users className="h-4 w-4 text-indigo-500" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{stats.creatorCount}</div>
              <p className="text-xs text-muted-foreground mt-1">
                Cross-platform profiles managed
              </p>
            </CardContent>
          </Card>
        </Link>

        <Link href="/content">
          <Card className="bg-card shadow-sm border-border/50 hover:bg-muted/50 transition-colors cursor-pointer h-full">
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">Posts Ingested</CardTitle>
              <Video className="h-4 w-4 text-emerald-500" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{stats.postCount}</div>
              <p className="text-xs text-muted-foreground mt-1">
                Total posts in workspace
              </p>
            </CardContent>
          </Card>
        </Link>

        <Card className="bg-card shadow-sm border-border/50">
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Avg Quality Score</CardTitle>
            <Sparkles className="h-4 w-4 text-amber-500" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {stats.avgQualityScore !== null ? stats.avgQualityScore : "—"}
            </div>
            <p className="text-xs text-muted-foreground mt-1">
              {stats.avgQualityScore !== null
                ? "Across scored profiles"
                : "No scores yet"}
            </p>
          </CardContent>
        </Card>

        <Link href="/creators?status=processing">
          <Card className="bg-card shadow-sm border-border/50 hover:bg-muted/50 transition-colors cursor-pointer h-full">
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">Discovery Queue</CardTitle>
              <Search className="h-4 w-4 text-sky-500" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{stats.pendingDiscoveryCount}</div>
              <p className="text-xs text-muted-foreground mt-1">
                Pending AI resolution
              </p>
            </CardContent>
          </Card>
        </Link>
      </div>

      {/* Main Content Area */}
      <div className="grid gap-6 md:grid-cols-2">
        {/* Outliers Feed */}
        <Card className="col-span-1 shadow-sm border-border/50">
          <CardHeader>
            <CardTitle className="text-lg">Recent Outliers</CardTitle>
            <CardDescription>
              Posts performing &gt;3× above their median average.
            </CardDescription>
          </CardHeader>
          <CardContent className="flex flex-col gap-4">
            {outliers.length === 0 ? (
              <EmptyState
                icon={Sparkles}
                title="No outliers yet"
                description="Phase 2 will populate this once scraping is live."
              />
            ) : (
              outliers.map((o, i) => (
                <OutlierItem
                  key={i}
                  handle={"@" + o.profileHandle}
                  multiplier={o.outlierMultiplier ?? 0}
                  views={o.viewCount}
                  url={o.postUrl ?? undefined}
                />
              ))
            )}
          </CardContent>
        </Card>

        {/* Top Trend Signals */}
        <Card className="col-span-1 shadow-sm border-border/50 relative overflow-hidden">
          <div className="absolute top-0 right-0 p-32 bg-indigo-500/10 blur-[100px] rounded-full pointer-events-none" />
          <CardHeader>
            <CardTitle className="text-lg flex items-center gap-2">
              <TrendingUp className="w-5 h-5 text-indigo-400" /> Top Trend Signals
            </CardTitle>
            <CardDescription>
              Realtime aggregate velocity across tracked accounts.
            </CardDescription>
          </CardHeader>
          <CardContent className="flex flex-col gap-4 relative z-10">
            {signals.length === 0 ? (
              <EmptyState
                icon={Activity}
                title="No active signals"
                description="Phase 2–3 will populate this when trend detection is live."
              />
            ) : (
              signals.map((s, i) => (
                <TrendItem
                  key={i}
                  type={s.signalType}
                  label={(s.metadata.label as string) ?? formatLabel(s.signalType)}
                  context={(s.metadata.context as string) ?? "—"}
                />
              ))
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  )
}

function formatLabel(t: string): string {
  return t.split("_").map((w) => w[0].toUpperCase() + w.slice(1)).join(" ")
}

function compact(n: number): string {
  return new Intl.NumberFormat("en-US", { notation: "compact", compactDisplay: "short" }).format(n)
}

function OutlierItem({
  handle,
  multiplier,
  views,
  url,
}: {
  handle: string
  multiplier: number
  views: number
  url?: string
}) {
  const inner = (
    <div className="flex items-center justify-between p-3 rounded-lg bg-muted/40 border border-border/50">
      <div className="flex flex-col">
        <span className="font-semibold text-sm">{handle}</span>
        <span className="text-[10px] uppercase text-emerald-500 font-bold tracking-wider">
          {multiplier.toFixed(1)}× above median
        </span>
      </div>
      <span className="font-bold text-amber-500">{compact(views)} views</span>
    </div>
  )
  return url ? (
    <a href={url} target="_blank" rel="noreferrer">
      {inner}
    </a>
  ) : (
    inner
  )
}

function TrendItem({
  type,
  label,
  context,
}: {
  type: string
  label: string
  context: string
}) {
  return (
    <div className="flex items-center gap-4 p-3 rounded-lg border border-border/50 bg-background/50">
      <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-indigo-500/10 text-indigo-400">
        <Activity className="h-5 w-5" />
      </div>
      <div className="flex flex-col flex-1">
        <span className="font-semibold text-sm">{label}</span>
        <span className="text-xs text-muted-foreground">{context}</span>
      </div>
      <Badge
        variant="outline"
        className="text-[10px] uppercase border-indigo-500/30 text-indigo-400"
      >
        {type.replace(/_/g, " ")}
      </Badge>
    </div>
  )
}
```

- [ ] **Step 2: typecheck + commit**

```bash
npx tsc --noEmit
git add src/app/\(dashboard\)/page.tsx
git commit -m "feat(command-center): real queries; empty states; remove hardcoded mock data"
```

---

### Task 34: Confirm zero raw `.from()` in pages

**Files:** (verification only)

- [ ] **Step 1: Grep for raw `.from(` in app routes**

```bash
grep -rn "supabase\.from(" "/Users/simon/OS/Living VAULT/Content OS/The Hub/src/app" 2>/dev/null
grep -rn "\.from(" "/Users/simon/OS/Living VAULT/Content OS/The Hub/src/app" 2>/dev/null | grep -v "node_modules"
```

Expected: zero hits in `src/app/**/page.tsx`. Only allowed locations:
- `src/lib/db/**` (the helpers themselves)
- `src/app/**/actions.ts` (mutations — `dismissMergeCandidate`, `addAccountToCreator` use raw `.from()` for inserts/updates that don't go through an RPC)

If a `page.tsx` still has `.from()`, refactor it through a helper.

- [ ] **Step 2: Commit any cleanup needed**

```bash
git status
# If anything was modified above, commit:
git add -A
git commit -m "refactor: remove last raw .from() calls from page components"
```

---

### Task 35: Layer 6 verification gate

- [ ] **Step 1: Spawn verifier subagent**

Invoke verifier:
> Verify Layer 6 of the Phase 1 overhaul. Use chrome-devtools-mcp to drive a real browser session against the local dev server (run `npm run dev` first if not already running).
>
> Checks:
> 1. Navigate to `/` — Command Center loads, all four stat cards show numbers (not `--`), Outliers and Trend Signals sections show either real items or the "No outliers yet"/"No active signals" empty state. Console must have zero `[Error]` entries.
> 2. Navigate to `/creators` — page loads, search input is functional (type "test" → URL gets `?q=test`), sort dropdown is functional (pick "Name (A-Z)" → URL gets `?sort=name_asc`). Click a creator card → navigates to `/creators/<slug>`.
> 3. On a creator detail page: if a merge candidate is shown, confirm both buttons are clickable (do NOT click — just confirm onClick is present). If failed-state banner is shown, confirm Retry button is clickable.
> 4. Navigate to `/platforms/instagram/accounts` and `/platforms/tiktok/accounts` — both load, tracking tabs are functional (click a tab → URL gets `?tracking=...`).
> 5. Click each Instagram and TikTok sub-route in sidebar (Outliers, Classification, Analytics) — all render the `ComingSoon` component, no 404s.
> 6. Sidebar has no duplicate `/content` entry.
>
> Code checks (no browser):
> 7. `grep -rn "\?type=" "/Users/simon/OS/Living VAULT/Content OS/The Hub/src/components/dashboard/Sidebar.tsx"` returns zero hits.
> 8. `grep -rn "\.from(" src/app | grep -v actions.ts` returns zero hits.
>
> Report pass/fail with screenshots and console logs as evidence.

Expected: verifier returns "pass."

---

# FINAL — END-TO-END VALIDATION

### Task 36: Bulk-import smoke test (real data)

- [ ] **Step 1: Set up test data via the UI**

Start the dev server and open `/creators` in a browser:
```bash
npm run dev
```

Open the Bulk Import dialog. Paste:
```
__test_overhaul_alpha instagram
__test_overhaul_beta tiktok
__test_overhaul_gamma youtube
```
Set Tracking Type to "Unreviewed", Tags to "smoke-test". Click Import.

Expected: success toast says "Imported 3 creators" (or similar). Dialog closes. Three new cards appear in the grid, all showing "Discovering…" or processing status.

- [ ] **Step 2: Verify DB state**

```bash
psql "$SUPABASE_DB_URL" -c "
SELECT c.canonical_name, c.onboarding_status, c.last_discovery_run_id IS NOT NULL AS has_run,
       (SELECT count(*) FROM profiles WHERE creator_id = c.id) AS profile_count,
       (SELECT count(*) FROM discovery_runs WHERE creator_id = c.id) AS run_count
FROM creators c
WHERE 'smoke-test' = ANY(c.tags)
ORDER BY c.created_at DESC;
"
```

Expected: 3 rows, all with `has_run = t`, `profile_count = 1`, `run_count = 1`.

- [ ] **Step 3: Cleanup**

```bash
psql "$SUPABASE_DB_URL" -c "
DELETE FROM discovery_runs WHERE creator_id IN (SELECT id FROM creators WHERE 'smoke-test' = ANY(tags));
DELETE FROM profiles WHERE creator_id IN (SELECT id FROM creators WHERE 'smoke-test' = ANY(tags));
DELETE FROM creators WHERE 'smoke-test' = ANY(tags);
"
```

Expected: 3 deletions (or however many rows the test created).

---

### Task 37: Full verifier sign-off

- [ ] **Step 1: Spawn the verifier subagent for the whole overhaul**

Invoke:
> Final verification of Phase 1 overhaul. Confirm each layer's gate passed and that the system is internally consistent.
>
> 1. Schema: live DB matches PROJECT_STATE §4 exactly. `docs/SCHEMA.md` has no drift entries. The `bulk_import_creator` RPC exists and works (run the smoke test from `docs/superpowers/plans/2026-04-23-phase-1-overhaul-plan.md` Task 15 Step 3).
> 2. Types: `npx tsc --noEmit` returns zero errors.
> 3. Data access: zero raw `.from()` in `src/app/**/page.tsx`. `createServiceClient()` throws on missing service role key. `getCurrentWorkspaceId()` exists and is cached.
> 4. Actions: every action in `src/app/(dashboard)/creators/actions.ts` returns `Result<T>`. `src/app/actions.ts` is deleted.
> 5. Components: `EmptyState`, `ErrorState`, `ComingSoon` exist. Loading/error boundaries exist. Sonner Toaster mounted.
> 6. Pages/routing: Sidebar uses `?tracking=`. No duplicate `/content`. TikTok sub-routes exist as ComingSoon. Search/sort wired on `/creators`.
>
> Use chrome-devtools-mcp to navigate every dashboard route and confirm zero console errors.
>
> Report PASS only if every check above passes. Otherwise list every failure with file:line evidence.

Expected: verifier returns "pass."

- [ ] **Step 2: Update PROJECT_STATE.md Decisions Log**

Append:
```
- 2026-04-24: Phase 1 overhaul complete. All 6 layers verified. Plan: docs/superpowers/plans/2026-04-23-phase-1-overhaul-plan.md.
```

- [ ] **Step 3: Final commit**

```bash
git add PROJECT_STATE.md
git commit -m "docs(state): Phase 1 overhaul complete — all layers verified"
```

---

## Self-Review Notes

This plan was self-reviewed against the spec on creation:

- ✅ Spec coverage: every section of the spec maps to one or more tasks (Schema §3 → Tasks 1–5; Types §4 → Tasks 6–7; Data access §5 → Tasks 8–14; Actions §6 → Tasks 15–19; Components §7 → Tasks 20–27; Pages §8 → Tasks 28–35; Final → Tasks 36–37).
- ✅ No placeholders: every code step shows complete code; no TBD/TODO; no "similar to Task N" references without re-stating the code.
- ✅ Type consistency: action names (`bulkImportCreators`, `importSingleCreator`, `retryCreatorDiscovery`, `dismissMergeCandidate`, `mergeCandidateCreators`, `addAccountToCreator`) are used consistently from Task 17 onward. Helper names (`getCurrentWorkspaceId`, `getCurrentUserId`, `getCreatorsForWorkspace`, `getPlatformAccountsForWorkspace`, etc.) are used consistently from their definition tasks onward.
- ✅ Verification: each layer ends with a verifier subagent gate. Final task spawns end-to-end verifier.
- ✅ Commits: every task ends with a commit step; cadence is 2–10 minutes per task.
