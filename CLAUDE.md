# CLAUDE.md — The Hub

Read `PROJECT_STATE.md` first at the start of every session.

## Verification Protocol

Before declaring ANY task complete, the verifier subagent must be invoked
and return "pass." This is enforced by the Stop hook.

The verifier is at .claude/agents/verifier.md and has read-only tools only.
You (the implementer) fix issues the verifier reports; you never rubber-stamp
your own work.

For scraper-related work, also run `/verify-scrape` slash command before
declaring done. This is documented in 04-Pipeline/Agent Catalog.md.

Never mark anything "working" without evidence from the verifier.

## Autonomous Execution

For subagent-driven or multi-task work where the user has granted autonomy
("just do it", "keep working", "proceed"), invoke the `autonomous-execution`
skill at the start. It codifies which decisions warrant interrupting the
user vs. proceeding with best judgment, and how subagents should inherit
the same policy.

## Database Query Protocol

### Ground Truth — READ FIRST
1. `docs/SCHEMA.md` — compressed reference of all 18 tables (regenerate via `npm run db:schema`)
2. `src/types/database.types.ts` — generated TypeScript types (regenerate via `npm run db:types`)
3. `supabase/migrations/` — source of truth for schema changes

**Note:** `docs/SCHEMA.md` has a "Drift" section at the bottom flagging known mismatches between the live DB and PROJECT_STATE.md. The live DB wins. Trust SCHEMA.md, not PROJECT_STATE.md, for column names.

### Hard Rules
1. Never write a column name you have not seen in `docs/SCHEMA.md`. If you think a column exists but cannot find it (e.g. `is_primary`, `follower_count`), ASK before writing the query. Do not guess.
2. Never write an enum value you have not seen in the Enums section. `"not_found"` is not valid unless literally listed.
3. `workspace_id` filter is MANDATORY on every query touching a tenant-scoped table (see Tenant-Scoped Tables list in `docs/SCHEMA.md`).
4. For INSERT/UPDATE with an enum-typed column: list values, cross-check against `docs/SCHEMA.md`, validate in Pydantic/Zod BEFORE sending the query.
5. When in doubt, ONE clarifying question beats THREE failed SQL attempts.

### Supabase MCP
- MCP is configured read-only for schema lookups only.
- Writes go through typed Next.js API routes or Python pipelines — never `execute_sql`.
- On Postgres `22P02` error: STOP. Do not retry with a different enum value. The Python enum has drifted from Postgres — fix the Pydantic schema and regenerate.
