# AGENTS.md — The Hub (Codex Handoff)

> **You are Codex, picking up from Claude Code mid-project.** This document gives you complete operational context: project identity, hard rules, workflows, tool mappings, memory facts, current state, and what's lossy in the model swap so you can compensate. Read it end-to-end before any work. After reading, also read `PROJECT_STATE.md` (master technical reference), then proceed.
>
> **Why this file exists:** Simon swaps from Claude Code to Codex when Claude credit is tight or when a task is more architectural / solution-oriented. The Claude-side conventions (Stop hook, subagent dispatch, auto-memory, Skill tool) don't translate directly. This doc carries the conventions across so the project doesn't lose continuity.
>
> **Last update:** 2026-04-28, after sync 20. Maintained by Claude Code/Codex; if you make changes that affect handoff (new tools, new rules, new phase), update the relevant section before ending the session.

---

## Table of Contents

1. [TL;DR — First 5 actions on every session](#1-tldr)
2. [Project identity — what The Hub is](#2-project-identity)
3. [Read order — the canonical files](#3-read-order)
4. [Hard rules — must not violate](#4-hard-rules)
5. [Tool mapping — Claude Code → Codex equivalents](#5-tool-mapping)
6. [Memory facts — what Claude knew about Simon](#6-memory-facts)
7. [Current state at handoff](#7-current-state)
8. [Build order — phases, what's queued, what's shelved](#8-build-order)
9. [MCP servers — what's wired and how to use them](#9-mcp-servers)
10. [Workflows you must run](#10-workflows)
11. [Verification protocol — without the Stop hook](#11-verification-protocol)
12. [Skills inventory — what each does, when to invoke](#12-skills-inventory)
13. [Autonomous execution policy](#13-autonomous-execution)
14. [Code style and quality rules](#14-code-style)
15. [Git and commit conventions](#15-git-conventions)
16. [What's lossy in the Claude → Codex migration](#16-lossy-items)
17. [Common commands cheat sheet](#17-commands-cheat-sheet)
18. [End-of-session protocol](#18-end-of-session)

---

## 1. TL;DR

**On every session, in order:**

1. **Read** `PROJECT_STATE.md` (this repo root). Master technical reference. Cite it as ground truth except for column names — see rule below.
2. **Read** `docs/SCHEMA.md` for live DB column names + enum values. Live DB wins over PROJECT_STATE if they conflict.
3. **Check** `git status` and `git log --oneline -10`. Confirm current branch and recent commits before any work.
4. **Match scope to ask.** If Simon hands you a task, do that task. Don't refactor surrounding code, don't add features he didn't request, don't introduce abstractions for hypothetical future requirements.
5. **Verify before claiming done.** No Stop-hook enforcement on Codex — see [§11](#11-verification-protocol) for the manual verification protocol that replaces it.

**Trigger phrases that change behavior** (from Simon's auto-memory; embedded here because Codex has no memory file):

| Phrase | Meaning |
|---|---|
| "just do it" / "keep working" / "proceed" / "go ahead" | Autonomy granted — escalate ONLY major decisions, decide routine stuff yourself, report decisions in summary. See [§13](#13-autonomous-execution). |
| "full autonomy" / "every permission granted" / "don't come back and ask" / "use subagents to run everything" / "minimal input from my end" / "stay within our parameters" | Run the full plan → execute → verify → push playbook end-to-end without check-ins. See [§13](#13-autonomous-execution) "Autonomous Fix-List Workflow". |
| "update project state" / "sync project" / "sync project state" / "update the project" / "close out the session" | Run the sync-project-state workflow. See [§10](#10-workflows). |
| "ignore memory" / "don't use memory" | Don't apply remembered facts from [§6](#6-memory-facts). |

---

## 2. Project Identity

**The Hub** — Creator Intelligence Platform.

- **Purpose:** Internal tool for a 2–5 person creator-management agency. **NOT a SaaS.** Workspace-isolated single-tenant on shared infra.
- **Daily job:** Discover creators → scrape their content across platforms → AI-score and label → surface outliers and winning patterns → feed insights into agency workflows.
- **Source-of-truth entity:** `creators`. Every other entity (accounts, content, analyses, funnel edges, trends) links back to a creator.
- **Tech stack:**
  - **Frontend:** Next.js 16.2.4 (App Router, Server Components where possible), TypeScript strict, Tailwind, shadcn/ui, Recharts, lucide-react, framer-motion, @xyflow/react, Playwright browser smoke tests
  - **Backend:** Supabase (Postgres 17, Auth, RLS, Realtime, Storage, Edge Functions). Project ref: `dbkddgwitqwzltuoxmfi`, region us-east-1, project name "Content OS"
  - **Pipeline:** Python 3.11+, `supabase-py`, `apify-client`, `google-generativeai`, `anthropic`, `pydantic v2`, `tenacity`, `rapidfuzz`, `httpx`, `beautifulsoup4`
  - **LLM routing:** Gemini for vision/multimodal/cheap-classification. Claude for nuanced writing/reasoning/agent loops. Stored per-row via `model_version`.
  - **Aesthetic:** Dark mode default. `bg=#0A0A0F`, card surface `#13131A`, border `white/[0.06]`, indigo/violet accent.
- **Repo + Obsidian vault are the same folder.** `/Users/simon/OS/Living VAULT/Content OS/The Hub`. PROJECT_STATE.md lives at the repo root and is rendered in both.
- **User:** Simon Lim (`simon.dylim@gmail.com`). Solo operator; the "agency" is conceptual scope. He values terse, concrete output.

---

## 3. Read Order

On every session, before code work, read in this order:

1. **`PROJECT_STATE.md`** — master technical reference. Sections you'll consult most:
   - §4 Schema (live + pending tables)
   - §5 Enums
   - §6 RPCs
   - §7 Routes (wiring status)
   - §14 Build Order (current phase + next)
   - §20 Known Limitations
   - §21 Discovery Pipeline Invariants
   - **Decisions Log** at the bottom (last ~15 syncs as narrative changelog)
2. **`docs/SCHEMA.md`** — live DB ground truth. Compressed reference of all 24 tables + enums. Has a "Drift" section flagging known mismatches between live DB and PROJECT_STATE.
3. **`src/types/database.types.ts`** — Supabase-generated TypeScript types. Don't hand-write column types.
4. **`supabase/migrations/`** — chronological source of truth for schema changes. New schema work writes a migration here; never edit the live DB out-of-band except via MCP/SQL editor for trivial data fixes.
5. **`docs/superpowers/specs/`** + **`docs/superpowers/plans/`** — design docs (specs) and execution plans for past major work. Reference when picking up Phase work to understand the existing pattern.
6. **`06-Sessions/YYYY-MM-DD.md`** — daily session notes (Obsidian). Write here when you escalate or finish a session.
7. **`CLAUDE.md`** — superseded by this file for Codex sessions. Don't follow CLAUDE.md verbatim; the verification protocol there assumes Stop hook + verifier subagent which you don't have.

---

## 4. Hard Rules

These are non-negotiable. Violating them caused real bugs in past syncs. The tests in `scripts/tests/` enforce many of them — don't disable a test to make it pass.

### 4.1 Database query rules

1. **Never write a column name you have not seen in `docs/SCHEMA.md`.** If you think a column exists but cannot find it (e.g. `is_primary`, `follower_count`), ASK before writing the query. Do not guess.
2. **Never write an enum value you have not seen** in §5 of PROJECT_STATE.md. `"not_found"` is not a valid status unless it appears in the enum.
3. **`workspace_id` filter is MANDATORY** on every query touching a tenant-scoped table. Tenant-scoped tables are listed in `docs/SCHEMA.md`. The hardcoded fallback workspace id you may encounter in legacy code is `00000000-0000-0000-0000-000000000001`.
4. **For INSERT/UPDATE with an enum-typed column:** list values, cross-check against `docs/SCHEMA.md`, validate in Pydantic/Zod BEFORE sending the query.
5. **On Postgres `22P02` error: STOP.** Do not retry with a different enum value. The Pydantic enum has drifted from Postgres — fix the Pydantic schema and regenerate. There's a regression test for this at `scripts/tests/test_platform_enum_drift.py`.
6. **One clarifying question beats three failed SQL attempts.** When in doubt, ask.

### 4.2 Supabase MCP usage

- **MCP is configured read-only** for schema lookups (`list_tables`, `list_extensions`, `list_migrations`, `get_logs`, `get_advisors`, `search_docs`, `generate_typescript_types`).
- **Writes go through typed Next.js API routes or Python pipelines** — never `execute_sql` for mutations.
- **Migrations:** `apply_migration` is available but treat it as a permission-gated action. For non-trivial DDL, write a `.sql` file in `supabase/migrations/` first, get Simon's eyes on it, then apply.

### 4.3 Discovery pipeline invariants

PROJECT_STATE.md §21 lists 9 invariants enforced by tests at `scripts/tests/`. The headline ones:

- **Handle normalization** — every account written via `_commit_v2` (in `scripts/discover_creator.py`) passes through `_normalize_handle(handle, platform)`. Strips leading `@`, lowercases for the 35 case-insensitive platforms in `_CASE_INSENSITIVE_PLATFORMS`. Don't bypass it.
- **URL canonicalization** — `canonicalize_url()` (in `scripts/pipeline/canonicalize.py`) strips tracking params (`utm_*`, `fbclid`, `igsh`, `_r`, `lang`, `l_`, `t`, `s`, `aff`, `ref_id`, others), lowercases hosts, normalizes `twitter.com → x.com`, lowercases first path segment for known social platforms.
- **`is_noise_url()`** drops API/CDN/legal/empty-path URLs at resolver entry AND harvester orchestrator. Don't add a new URL source that bypasses this.
- **`visit.link.me` redirector classification** runs FIRST in `pipeline/classifier.py::classify()` — parses `?sensitiveLinkLabel=OF/Fanvue/Fanfix/Fanplace/Patreon` and returns `(<platform>, monetization)` at confidence 1.0.
- **Specific platform values in the Postgres `platform` enum (~37 values)** are the right abstraction for unique-constraint collisions. Don't add a new aggregator or monetization platform without (a) extending the enum, (b) extending the Pydantic `Platform` Literal, (c) adding a gazetteer rule, (d) adding to `src/lib/platforms.ts::PLATFORMS`, (e) adding to `HOST_PLATFORM_MAP`.

### 4.4 Code-side guardrails

- **No half-finished implementations.** If you can't complete it in this turn, surface the partial state explicitly and stop; don't ship a stub commented `// TODO finish later`.
- **Don't add features Simon didn't request.** A bug fix doesn't need surrounding cleanup. A one-shot operation doesn't need a helper. Don't design for hypothetical future requirements.
- **Don't add error handling, fallbacks, or validation for scenarios that can't happen.** Trust internal code and framework guarantees. Only validate at system boundaries (user input, external APIs).
- **Don't add backwards-compatibility shims** when the codebase is small enough that you can just change all callers in one pass.
- **Default to writing no comments.** Only add a comment when the WHY is non-obvious — a hidden constraint, subtle invariant, workaround for a specific bug, behavior that would surprise a reader. If removing the comment wouldn't confuse a future reader, don't write it.
- **Don't reference the current task in code** — no `// added for sync 18`, `// fixes issue #123`, `// used by the new flow`. Those rot. Put context in commit messages, plans, or PROJECT_STATE.

---

## 5. Tool Mapping

Claude Code tools you'll see referenced in skills, agent files, and prior commit messages have these Codex equivalents. The skills under `.claude/skills/` are written for Claude Code's tool names — translate as you go.

| Claude Code | Codex equivalent | Notes |
|---|---|---|
| `Read` | `read_file` (or `cat`/`open` via shell) | Same: read absolute paths |
| `Edit` | `apply_patch` | Codex's diff-based editor; Claude's Edit is search-replace |
| `Write` | `apply_patch` (new file) | New-file mode in apply_patch |
| `Bash` | `shell` | Same shell, same OS, same `zsh` on darwin 25.3.0 |
| `Grep` | `shell` (`rg <pattern>`) | Just use ripgrep |
| `Glob` | `shell` (`find` / `ls`) | |
| `Agent` (subagent dispatch) | **No direct equivalent** | See [§16](#16-lossy-items) — sequence work yourself or use shell scripts to parallelize. The "dispatch 6 implementers + 12 reviewers" pattern from sync 14 doesn't transfer 1:1. |
| `TaskCreate` / `TaskList` / `TaskUpdate` | Codex's task system, or maintain a local `TODO.md` | Use whatever your harness offers. The principle is: track progress on multi-step work, don't batch updates. |
| `Skill` tool | **No direct equivalent** | Skills are markdown files. When a workflow applies, just read the relevant `.claude/skills/*/SKILL.md` and follow its content. The most important ones are inlined in this doc — see [§12](#12-skills-inventory). |
| `WebFetch` / `WebSearch` | Use whatever Codex provides; otherwise `curl` via shell | |
| MCP tools (`mcp__claude_ai_Supabase__*`, `mcp__plugin_chrome-devtools-mcp_chrome-devtools__*`, etc.) | Same MCP servers, accessed via Codex's MCP harness | MCP is a cross-tool standard; the servers themselves don't change. See [§9](#9-mcp-servers). |

---

## 6. Memory Facts

These are the persisted facts Claude carried across sessions via its auto-memory at `~/.claude/projects/.../memory/`. Codex doesn't have that store, so they're inlined here. Update this section when something material changes.

### User identity
- **Name:** Simon Lim
- **Email:** `simon.dylim@gmail.com`
- **Git global config** is set under that name + email. Match it on commits.

### Autonomy threshold
When Simon grants autonomy, escalate ONLY critical decisions; decide routine stuff from project context. **Critical** = destructive, irreversible, externally visible, cost-incurring beyond approved ceiling, scope/architecture deviation, security-sensitive, new dependency, fork with material downstream consequences, or verification failure with ambiguous root cause. **Routine** = naming, error-message wording, picking between equivalent idioms, where to place a helper. See [§13](#13-autonomous-execution) for the full rubric.

### Autonomous fix-list workflow
When Simon hands a fix list with "full autonomy / don't ask / use subagents / minimal input / stay within our parameters", run plan → execute → verify → push end-to-end without check-ins. The full skill content is in `.claude/skills/autonomous-fix-list/SKILL.md`; gist inlined in [§13](#13-autonomous-execution).

### Schema reference tooling
- `npm run db:schema` regenerates `docs/SCHEMA.md` (calls `bash scripts/compile_schema_ref.sh`)
- `npm run db:types` regenerates `src/types/database.types.ts`
- **Both are blocked** on `SUPABASE_DB_URL` in `scripts/.env` being unset. PROJECT_STATE §4.1 has been hand-updated to reflect the 24-table reality. Simon needs to fill that env var; documented as a §20 known limitation.

### Local dev tool availability
- `psql` at `/opt/homebrew/opt/libpq/bin/psql` (Homebrew libpq, not full Postgres)
- `supabase` CLI is a devDependency only (`npx supabase ...`)
- Xcode Command Line Tools blocks `brew install` — do not attempt `brew install` of new tooling without checking with Simon first

### Recursive funnel resolution
- **STATUS:** shipped sync 14 (2026-04-25). The plan at `docs/superpowers/plans/2026-04-25-recursive-funnel-resolution.md` was the basis. Bounded follow-until-terminus expansion through `_expand` in `scripts/pipeline/resolver.py`. Triple-bounded: visited_canonical cycle dedup + BudgetTracker + `MAX_DEPTH=6` (env: `DISCOVERY_MAX_DEPTH`). Confidence drops linearly with depth via `_confidence_at_depth`.
- **Outdated memory note:** older auto-memory described it as "open plan"; that's stale.

### Highlights v1+v2 — SHELVED
Code lives in repo, runtime gated off (`DISCOVERY_HIGHLIGHTS_ENABLED=0`). The `apify/instagram-scraper resultsType="stories"` actor returns `no_items` without IG `sessionCookies`. Recursive funnel + Universal URL Harvester are currently good-enough. **Thaw conditions** documented in PROJECT_STATE §20 row "Highlights v1 — shelved 2026-04-25". Spec/plan exist at `docs/superpowers/specs/2026-04-25-highlights-v1-design.md` + `docs/superpowers/plans/2026-04-25-highlights-v1.md`.

### Apify actor schema drift
When fetchers silently return empty: dispatch the actor with a small diagnostic script in `.tmp/` (gitignored) and inspect the raw shape before assuming the bug is in our code. Apify actors mutate their output schema between releases — don't blame the fetcher first.

### Communication style preferences (inferred from session history)
- **Terse and concrete.** Single-sentence updates between actions. End-of-turn summary in 1–2 sentences max. No headers/sections for simple questions.
- **No emojis** unless he explicitly uses them first. Avoid them in commit messages too.
- **Show your work in the final message, not in narration.** Don't write "let me think about this" — just deliver the answer.
- **Don't restate what the diff already shows.** When a change is small, the commit message + diff are enough. Don't add a 3-paragraph summary.
- **He calls out drift fast.** If you're about to take a destructive action without authorization, he'll stop you mid-task. Default to confirmation on actions visible outside your sandbox.

---

## 7. Current State at Handoff

**Date:** 2026-04-28 (you are reading this on or after this date — confirm via `date`).

**Branch:** `phase-2-discovery-v2`. Clean working tree at last sync. Possibly 1+ commits ahead of `main` since last PR merge — check `git log --oneline origin/main..HEAD`.

**Last PROJECT_STATE sync:** sync 20 (90-day scrape + filtered content/outlier/audio trend UI).

**Latest commits:** check `git log --oneline -10`; this handoff is updated through sync 20 work.

**What just shipped (sync 18–20):**
- Content scraper v1 manual CLI: `scripts/scrape_content.py` + `scripts/content_scraper/` for batched IG/TT Apify ingestion, Pydantic normalizers, `commit_scrape_result`, `flag_outliers`, and profile snapshots.
- Scraper observability: migration `20260427000200_scrape_runs_observability` adds `scrape_runs`; local migration file is committed but live apply is pending. The scraper catches `scrape_runs` insert failures and still updates content/profile snapshots.
- Live scrape: 18 active IG/TT profiles targeted over 90 days; 13 scraped, 5 skipped `no_posts`, 643 posts upserted, 0 failures. Current 90-day library: 639 posts, 75 outliers, 528 posts with audio signatures.
- Audio trends: `scripts/extract_audio_trends.py --min-usage 2` linked 49 repeated audio trends to 137 scraped posts.
- Live surfaces: `/scraped-content`, `/platforms/instagram/outliers`, `/platforms/tiktok/outliers`, `/trends` Audio Trends. `/content` is reserved for agency creation tools / Content Hub.
- Deterministic/manual tooling: `scripts/validate_scraped_content.py`, `scripts/judge_suspicious_content.py`, `scripts/extract_audio_trends.py`, `schemas/social_post.schema.json`.
- Simon deferred the 12-hour automatic scrape/cron; do not resurrect it unless explicitly asked.

**Test status as of sync 20:** content scraper tests previously 43/43; full pytest previously 298/298 + 1 skip; latest close-out ran `npm run typecheck` 0, `npm run lint` 0 errors (2 pre-existing creator-page warnings), content quality/trends pytest 5/5, and route smokes 200 for scraped content, both outlier pages, and audio trends.

---

## 8. Build Order

Per PROJECT_STATE.md §14:

1. ✅ Phase 1 — Schema, Creators hub, discovery pipeline, bulk import, merge candidates, live card grid
2. ✅ Phase 1 UX hardening
3. ✅ Phase 1 agents — `verify-and-fix` skill
4. ✅ Vault merged into repo
5. 🔄 Wire stub routes — IG accounts ✅, TT accounts ✅, scraped content ✅, platform outliers ✅, audio trends ✅; `/content` intentionally reserved for agency creation tools
6. ✅ Phase 2 discovery rebuild
7. ✅ Phase 2 schema migration (`20260424170000_phase_2_schema_migration`)
8. ✅ Discovery v2 (SP1) — two-stage resolver, classifier, identity scorer, multi-platform fetchers
   - ✅ Recursive funnel (sync 14)
   - ✅ Universal URL Harvester (sync 15)
   - ✅ Profile noise cleanup + specific platforms + AccountRow + banner foundation (sync 16)
   - ✅ Duplicate prevention hardened + regression tests + Gemini-enriched watchdog (sync 17)
9. 🟡 **Phase 2 scraping** — manual-trigger path is live and hardened. Cron/automatic 12h scraping is explicitly deferred by Simon. Current assets: `scripts/scrape_content.py`, `scripts/content_scraper/`, pending `scrape_runs` migration, live `/scraped-content`, live platform outlier pages, deterministic validator, audio trend extractor, results-checker JSON schema.
10. 🟡 Phase 2 trends — repeated-audio extraction exists via `scripts/extract_audio_trends.py`; `/trends` is live for Audio Trends, broader `trend_signals` feed still pending.
11. 🔜 Phase 3 content analysis — Gemini scoring, `profile_scores` + rank tier on UI
12. 🔜 Phase 3 brand analysis — Claude-driven brand report per creator
13. 🔜 Phase 3 classification UI — taxonomy curation tabs
14. 🔜 Phase 4 funnel editor — React Flow drag-to-connect for `funnel_edges`
15. 🔜 Phase 4 monetization intel — dashboards across creators

**Shelved (explicit decisions to not do):**
- **Highlights v1 + v2** — shelved 2026-04-25. See [§6](#6-memory-facts) and PROJECT_STATE §20 for thaw conditions.

**Deferred (no decision against, no scheduled date):**
See PROJECT_STATE §20 Known Limitations for the full list. Notable:
- Apify details not written to profile (wasteful second Apify call; dual-call works but should be unified)
- Dead-letter file has no replay tooling (`scripts/discovery_dead_letter.jsonl` is write-only)
- Banner UI bare-bones until Phase 3 scraper writes `cover_image_url`
- Pydantic Platform Literal vs Postgres enum live-DB drift check is a placeholder skip — needs CI `SUPABASE_DB_URL`
- `auth.uid()` returns null in server actions (RLS + Auth not yet wired)

---

## 9. MCP Servers

These MCP servers are wired and useful. Configuration lives in `.claude/settings.json` for Claude Code; you'll need to mirror in your Codex MCP config if not auto-imported.

| Server | Purpose | Connection notes |
|---|---|---|
| **Supabase** | Schema/query/logs/migrations. **Read-only** for safety. Use for `list_tables`, `list_extensions`, `list_migrations`, `get_logs`, `get_advisors`, `search_docs`, `generate_typescript_types`. | URL: `https://mcp.supabase.com/mcp?project_ref=dbkddgwitqwzltuoxmfi&read_only=true`. Project ref `dbkddgwitqwzltuoxmfi`. Mutations go through API routes or migrations, not MCP. |
| **Chrome DevTools** | Real-Chrome browser smoke tests — detects auth walls, console errors, redirects. **Critical for the verification protocol** since you don't have Stop hook + verifier subagent. | `npx chrome-devtools-mcp`. The verifier subagent at `.claude/agents/verifier.md` uses this for HTTP 200 + console-error checks. |
| **Apify** | Actor runs, dataset inspection, logs for scraper debugging. | `npx @apify/actors-mcp-server`. Used during Phase 2 work and now Phase 2 scraping. |
| **Airtable** | Reference / brainstorming surface for Simon's other operations. | Multi-base; usually not relevant to coding tasks. |
| **Sentry** (optional) | Production error stack traces in dev sessions. | `https://mcp.sentry.dev/mcp`. Wire via `SENTRY_AUTH_TOKEN` + `SENTRY_ORG_SLUG` env vars. |
| **Google Drive / n8n** | Background integrations. Not used in coding tasks. | |

**Operational note for Supabase MCP:** the MCP server is configured read-only. If you need to apply a migration, use `apply_migration` (write-capable) and treat it as a permission-gated action — preview the SQL, get Simon's eyes, then apply. For trivial data fixes (one-off UPDATEs on a stale row), you may use `execute_sql` if `read_only=false`; default posture is to write a migration.

---

## 10. Workflows

### 10.1 Brainstorm → Plan → Execute (the canonical pattern)

For any non-trivial feature/system work:

1. **Brainstorm** — read relevant code, understand the existing pattern, surface tradeoffs to Simon. The skill `superpowers:brainstorming` applies; gist: ask clarifying questions about user intent, requirements, design before touching code. Output is alignment, not code.
2. **Write the plan** — `docs/superpowers/plans/YYYY-MM-DD-<slug>.md`. Structure (matching existing plans):
   - Goal (1–2 paragraphs)
   - Out-of-scope (explicitly)
   - Task breakdown (numbered, each one a single-subagent-sized chunk)
   - Tests to add per task
   - Files to read first / files to modify
   - Verification steps
   - Commit messages (pre-write them)
3. **Execute** — task by task. After each task: write/run tests, run `npm run typecheck`, run `pytest`, commit. Don't batch commits across multiple tasks.
4. **Verify the whole** — see [§11](#11-verification-protocol).
5. **Sync project state** — see §10.3.

Existing plans you can reference for shape: `docs/superpowers/plans/2026-04-25-universal-url-harvester.md` is the most recent and well-structured one.

### 10.2 Subagent dispatch (Claude pattern; Codex compensation)

Claude Code parallelized tasks via `Agent` tool calls (multiple in one message → ran concurrently). Codex doesn't have that. Compensation strategies:

- **Sequence the tasks yourself.** It's slower but the same outcome. Most plans don't actually need parallel execution — the wins from "6 implementers + 12 reviewers in parallel" are real but not load-bearing for solo work.
- **Use shell scripts for genuine parallelism** when independent: e.g. run `npm run typecheck` and `pytest` in parallel via `&` and `wait`. Don't try to parallelize edits across files; sequence them.
- **Commit per task.** Even when sequencing, the git history should still show 1 commit per task — that gives Simon the same review surface as the parallel-dispatch pattern would.

### 10.3 Sync project state (the close-out)

When Simon says "sync project" / "update project state" / "close out the session" or after any architectural change, run the `sync-project-state` workflow. Full skill at `.claude/skills/sync-project-state/SKILL.md`; gist:

1. Read current `PROJECT_STATE.md` from repo root.
2. Detect changes since last sync:
   - `git log --oneline -20` and `git diff HEAD~5 --name-only`
   - Compare `supabase/migrations/*.sql` against §4 documented schema
   - Compare routes under `src/app/` against §7
   - Compare components under `src/components/` for new dirs
   - Use Supabase MCP `list_tables` schema=public to verify §4.1 matches live DB
3. Update `PROJECT_STATE.md`:
   - §4.1 Live schema (add/remove tables, columns, enums)
   - §4.2 Pending migration (mark items applied, move to §4.1)
   - §5 Enums (new values)
   - §6 RPCs (new function signatures)
   - §7 Routes (wiring status: ⬜ Placeholder → 🟡 Partial → ✅ Live)
   - §14 Build Order (mark phases complete, update "next")
   - §20 Known Limitations (add new ones, remove resolved ones)
   - §21 Discovery Pipeline Invariants (if you added new ones)
   - "Last synced" date at the top
   - Append a new entry to the "Decisions Log" at the bottom with the sync number, date, branch, what shipped, test status, architectural takeaways
4. Update `supabase/migrations/MIGRATION_LOG.md` with any new migration files.
5. Update `README.md` only if setup commands or env vars changed.
6. Commit with message `chore: sync project state — sync N (<one-line summary>)` and push (only if Simon authorized).

### 10.4 Manual database query / schema check

Before writing a query touching unfamiliar tables:

```bash
# 1. Check the compressed schema reference
cat docs/SCHEMA.md | grep -A 20 'creators\|profiles\|<table>'

# 2. If still unsure, query live
# (via Supabase MCP, or via psql if SUPABASE_DB_URL is set)
/opt/homebrew/opt/libpq/bin/psql "$SUPABASE_DB_URL" -c "\\d <table>"
```

---

## 11. Verification Protocol

**You don't have the Stop hook + verifier subagent.** That gate is the single biggest thing lost in the Claude → Codex swap. The Claude harness ran `.claude/hooks/verify-before-stop.sh` automatically before allowing the turn to end; that script ran `npm run typecheck`, optionally `playwright test`, and warned on UI changes. The verifier subagent at `.claude/agents/verifier.md` ran an end-to-end check (typecheck → curl → DB query shape → Chrome console errors → screenshot). Codex must run this manually. Do not skip.

### 11.1 Verification levels — what to run when

| Change | Minimum verification |
|---|---|
| Comment / docs only | none |
| Single-line bugfix in a leaf function | unit test for that function |
| New helper / refactor of a leaf | `npm run typecheck` + relevant `pytest` |
| Schema migration (Python pipeline path) | `pytest scripts/tests` + apply migration to dev DB + spot-check live shape via Supabase MCP `list_tables` |
| Schema migration (UI path) | above + `npm run db:types` regen + `npm run typecheck` + manually open the affected route in Chrome |
| New route / component / server action | full end-to-end (see 11.2) |
| Pipeline change touching `_commit_v2`, classifier, harvester | full end-to-end + `pytest scripts/tests` (especially `test_commit_v2_dedup.py`, `test_platform_enum_drift.py`, `test_classifier_*.py`) |
| Apify actor swap or fetcher change | full end-to-end + live smoke on at least one creator |

### 11.2 Full end-to-end check (replaces the verifier subagent)

For UI changes, server actions, or anything with a route surface:

```bash
# 1. TypeScript
npm run typecheck         # must return 0 errors

# 2. Lint (optional but cheap)
npm run lint              # warnings OK; errors = fix

# 3. Python pipeline
cd scripts && python3 -m pytest tests -q && cd -

# 4. Build a fresh dev server (in background) and probe routes
npm run dev &              # starts on :3000 unless taken
sleep 4
curl -s -o /dev/null -w "%{http_code}\n" http://localhost:3000/<changed-route>
# expect 200

# 5. Chrome DevTools MCP — open the route, check console, take a screenshot.
# Use mcp__chrome_devtools__navigate_page, list_console_messages, take_screenshot.
# Assert: zero console errors, key DOM elements present.

# 6. DB query shape — for pages that read data, run the expected query via Supabase MCP read-only.
# Confirm row count, null rates, shape match what the UI expects.
```

For pipeline changes:

```bash
# 1. Tests
cd scripts && python3 -m pytest tests -q && cd -

# 2. Type check (Pydantic schemas may affect TS types via codegen)
npm run typecheck

# 3. Live smoke — re-run discovery on one creator, watch worker logs
# Worker is launchd-managed; logs at ~/Library/Logs/the-hub-worker.log
tail -f ~/Library/Logs/the-hub-worker.log
# In another terminal:
bash scripts/worker_ctl.sh restart        # picks up code changes
# Trigger a discovery run via UI or `bulk_import_creator` RPC
```

### 11.3 Scraper-specific verification

For scraping work (will become relevant in Phase 2 scraping), run these checks:

- **Row count sanity** — assert scraped row count is non-zero and within expected range for the actor's typical output
- **Schema validation** — every row passes Pydantic validation; reject runs where >5% of rows fail
- **Auth-wall regex** — match `sign in|captcha|cf-chl|access denied|log in` against raw HTML sample. Fail if found.
- **Chrome DevTools MCP smoke** on the rendered Outliers page (or whatever surfaces the new data)

### 11.4 When to ESCALATE rather than fix

After 3 fix attempts that don't pass verification, **stop**. Write to `06-Sessions/YYYY-MM-DD.md` (today's date) under an "Agent Escalations" heading:

```markdown
## Agent Escalations

### <task name> — <timestamp>
**Trigger:** <what changed>
**Outcome:** fail (3 iterations exhausted)
**Evidence:**
- <verbatim test failures or error messages>
**Proposed next action:** <what needs Simon's input>
```

Then stop. Don't attempt iteration 4.

---

## 12. Skills Inventory

Claude Code skills live as markdown files at `.claude/skills/<name>/SKILL.md` (project-level) and `~/.claude/skills/<name>/SKILL.md` (user-level). Codex can't auto-invoke them, but the content is still useful — read the relevant SKILL.md when the situation matches.

### 12.1 Project-level skills (this repo)

| Skill | Path | When to read |
|---|---|---|
| **verify-and-fix** | `.claude/skills/verify-and-fix/SKILL.md` | After any edit to `src/app/`, `src/components/`, or `scripts/` before declaring complete. Defines the verifier-loop the Stop hook used to enforce. |
| **sync-project-state** | `.claude/skills/sync-project-state/SKILL.md` | When Simon says "sync project state" or after any architectural change. See §10.3. |
| **autonomous-fix-list** | `.claude/skills/autonomous-fix-list/SKILL.md` | When Simon hands a fix list with full-autonomy phrasing. See §13. |
| **autonomous-execution** | `.claude/skills/autonomous-execution/SKILL.md` | At the start of any subagent-driven or multi-task autonomous run. Decision-gating policy (major vs routine). |
| **a11y-audit** | `.claude/skills/a11y-audit/SKILL.md` | When Simon asks for accessibility audit / WCAG check. |
| **shadcn** | `.claude/skills/shadcn/SKILL.md` | Working with shadcn components — adding, fixing, debugging. |
| **web-design-guidelines** | `.claude/skills/web-design-guidelines/SKILL.md` | When asked to "review my UI", "check accessibility", "audit design", "review UX". |

### 12.2 User-level skills (cross-project, lower priority for handoff)

These live at `~/.claude/skills/` and are Simon's personal toolkit. They apply across all his projects:

- `simplify` — review changed code for reuse, quality, efficiency
- `loop` — recurring task scheduling (Claude harness specific; not portable to Codex)
- `schedule` — cron scheduling for remote agents (Claude-specific)
- `defuddle` — extract clean markdown from web pages (CLI tool; works in any harness)
- `obsidian-markdown`, `obsidian-bases`, `obsidian-cli`, `json-canvas` — Obsidian vault tooling
- `superpowers:*` — the brainstorming / writing-plans / executing-plans / TDD / debugging skill bundle from `obra/superpowers`. Most important content already inlined in this doc.

### 12.3 The superpowers bundle — what carries over

The `superpowers` skill bundle has explicit Codex support — the `using-superpowers` skill ships a `references/codex-tools.md` that maps Claude tool names to Codex equivalents. The high-leverage skills:

- **`superpowers:brainstorming`** — required before creative work. Asks clarifying questions about user intent, requirements, design before code. Outputs alignment, not code.
- **`superpowers:writing-plans`** — required when you have a spec for a multi-step task, before touching code.
- **`superpowers:executing-plans`** — required when executing a written plan.
- **`superpowers:verification-before-completion`** — required before claiming work complete. Run verification commands and confirm output before making any success claims. Evidence before assertions, always.
- **`superpowers:systematic-debugging`** — required when encountering any bug, test failure, or unexpected behavior, before proposing fixes.
- **`superpowers:test-driven-development`** — required when implementing any feature or bugfix, before writing implementation code.
- **`superpowers:requesting-code-review`** — required when completing tasks, before merging.

**Translation note:** the superpowers skills reference Claude tools like `Agent`, `TaskCreate`. When you read them, mentally substitute Codex equivalents per [§5](#5-tool-mapping).

---

## 13. Autonomous Execution

Simon often works in autonomous mode — he hands you a task or fix list and expects you to run it without check-ins. Two related skills govern this:

### 13.1 The decision-gating rubric (`autonomous-execution`)

When autonomy is granted, escalate to Simon ONLY for **MAJOR** decisions:

1. **Destructive or irreversible actions** — deleting data, dropping tables, force-pushing, `rm -rf`, overwriting uncommitted work, amending published commits
2. **External / shared-state mutations** — pushing to remote, creating/merging PRs, sending messages, posting to third-party services, modifying shared infrastructure or permissions
3. **Cost-incurring beyond pre-approved ceiling** — LLM calls, API runs, Apify scrapes that exceed budget Simon signed off on
4. **Scope or architecture deviations** — when the plan doesn't cover the situation and the resolution changes what gets built
5. **Security-sensitive choices** — auth, secrets, permissions, RLS changes
6. **New dependencies** — adding a package/library not in the approved plan
7. **Genuine forks with real downstream consequences** — when picking either path commits the project to materially different follow-up work
8. **Verification failure with ambiguous root cause** — tests/smoke fail and you can't confidently identify the fix after one focused debugging pass

**ROUTINE** decisions, just decide and report in the summary:
- Naming variables, functions, helpers, files
- Error-message wording, log phrasing
- Test-assertion phrasing and ordering
- Picking between two equivalent idioms already used in the codebase
- Where to place a helper / how to organize imports
- Small cosmetic deviations from the plan when the plan is unclear

### 13.2 The autonomous fix-list workflow

When Simon's prompt includes any of: "full autonomy", "every permission granted", "don't come back and ask", "use subagents to run everything", "minimal input from my end", "stay within our parameters" — and a numbered or bulleted list of fixes — run this playbook end-to-end:

**Step 1 — Plan in one message.** Output a single response containing:
- Phase grouping (A=functional bugs/blocked flows, B=UI/polish/restructure, C=verification + ship)
- Step-by-step outline (one bullet per concrete step, each step single-task-sized)
- Out-of-scope callout (explicitly list what you're NOT doing)
- Single sentence "Starting now." Then immediately begin executing.

**Step 2 — Execute task by task.**
- For each task, decide: inline edit (single file, <10 lines, obvious correct answer) vs. spawning a subagent if available. On Codex, treat all as inline since you don't have parallel subagent dispatch.
- After each task: tests, typecheck, commit. Don't batch commits across tasks unless the tasks are genuinely a single unit.
- Catch unrelated bugs inline only if the fix is one line and clearly safe; otherwise note in the report and move on.

**Step 3 — Final verification.**
- Full `npm run typecheck` + `pytest scripts/tests` + Chrome DevTools MCP smoke on changed routes.
- If any check fails, fix and re-verify. Loop max 3 times; escalate if still failing.

**Step 4 — Push.**
- Push the branch with `git push origin <branch>` (only if Simon's playbook authorized it; the trigger phrases above generally authorize push).
- Don't merge or open PRs without explicit ask.

**Step 5 — Report.**
- Summarize: tasks completed, commits pushed, verification results, decisions taken inline, items deferred.

---

## 14. Code Style

### TypeScript / React
- **Strict mode.** No `any` unless genuinely unavoidable; prefer `unknown` + narrowing.
- **Server Components by default** in Next.js App Router. Add `"use client"` only when needed (state, effects, browser APIs, event handlers).
- **Imports:** absolute via `@/` alias for `src/`.
- **Components:** `PascalCase.tsx`, `kebab-case.tsx` is wrong here.
- **shadcn/ui patterns:** primitive components in `src/components/ui/`; composed feature components live alongside the route they serve.
- **State:** server state via React Server Components; client state via `useState` for local, no global state library yet.
- **Styling:** Tailwind + `cn()` from `src/lib/utils.ts`. shadcn variants via `class-variance-authority`. Dark-mode default; don't add light-mode-only styles.
- **Icons:** `react-icons/si` for brand icons (Si* prefix); `react-icons/fa` as fallback (FaLinkedin, FaAmazon); `lucide-react` for generic. See `src/lib/platforms.ts::PLATFORMS` for the full mapping.

### Python pipeline
- **Pydantic v2** for all data models. Literals for closed enums (Platform, EdgeType).
- **`tenacity`** for retry on transient errors (network, Apify rate limits, Postgres serialization). See `scripts/fetchers/base.py::is_transient_apify_error()` for the predicate pattern.
- **`supabase-py`** for DB; check `.maybe_single().execute()` returns `None` on miss in supabase-py 2.x — historic bug at sync 13 commit `48849e7`.
- **No global state.** Workers receive Supabase clients explicitly. Same goes for the Gemini / Anthropic / Apify clients.
- **Logs:** stdlib `logging` configured in `scripts/common.py`. Don't use `print()` outside of one-off diagnostic scripts in `.tmp/`.

### Migrations
- File naming: `YYYYMMDDHHMMSS_<short_description>.sql`.
- Top of file: 2–3 line comment explaining the intent (not the mechanics — those are in the SQL).
- One migration per logical change. Don't bundle a schema change with a data migration unless they must run atomically.
- For column adds: NULL-able by default unless you backfill in the same migration.
- For enum extensions: `ALTER TYPE <enum> ADD VALUE IF NOT EXISTS '<value>'`. Each value gets its own statement.

### Tests
- Python pytest at `scripts/tests/`. Unit-style. Mock Supabase client when testing pipeline logic.
- TypeScript: Playwright for browser smoke (`tests/` and `playwright.config.ts`). Currently used sparsely; add coverage as routes go live.
- Test naming: `test_<thing_being_tested>_<scenario>`. The duplicate-prevention test ring at `scripts/tests/test_commit_v2_dedup.py` is the gold standard for shape.

---

## 15. Git Conventions

### 15.1 Commit message style

Match the existing log shape. Examples from the recent history:

```
fix(fetchers): handle clockworks/tiktok-scraper bioLink as string OR dict
chore: sync project state — sync 17 (T18 + T19 + T20)
feat(classifier): Gemini-enriched suggestions surfaced in new_platform_watchdog
test+ops(pipeline): regression tests + new-platform watchdog SQL view
fix(pipeline): centralized handle normalization + visit.link.me OF redirector
```

Format: `<type>(<scope>): <short summary in lowercase>`.

- Types: `feat`, `fix`, `chore`, `test`, `refactor`, `docs`, `ops`. Combinations OK (`test+ops`, `fix+test`).
- Scopes: `pipeline`, `classifier`, `fetchers`, `harvester`, `commit_v2`, `db`, `creator-hq`, `ui`, `platforms`, etc. Match what's already in the log; don't invent new scopes for one-off uses.
- Body: optional. Use it when the why isn't obvious from the diff. Short paragraphs. No bullet point lists unless genuinely needed.
- **No emoji prefix.** Some open-source projects use `:bug:`-style; this repo doesn't.

### 15.2 Co-authored-by line

When you (Codex) author commits, use:

```
Co-Authored-By: Codex <noreply@openai.com>
```

(Or whatever attribution your harness defaults to.) Match what Claude Code did — it added `Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>`. Same pattern, different model name.

### 15.3 Push and PR rules

- **Never push without explicit authorization.** Trigger phrases like "ship it", "push it", "merge", "send the PR" authorize. "Run the next task" does not.
- **Never force-push to main/master.** Warn Simon and stop if asked.
- **Never amend a published commit** (one that's been pushed). Always create a new commit.
- **Never skip hooks** (`--no-verify`, `--no-gpg-sign`) unless Simon explicitly asks.
- **PRs:** open via `gh pr create`. Title <70 chars. Body: 1–3 bullet summary + test plan checklist. Match the existing PR shape.

### 15.4 Branch strategy

Current working branch: `phase-2-discovery-v2`. New phase work should branch off `main` once the current branch is merged. Naming: `phase-N-<slug>` for big phases; `<area>-<slug>` for focused work (e.g. `harvester-tier3-iframe-traversal`).

---

## 16. Lossy Items

Things that don't transfer cleanly from Claude Code to Codex. For each, note the compensation strategy.

### 16.1 Stop hook gate (the single biggest loss)
**What it did:** `.claude/hooks/verify-before-stop.sh` ran automatically before allowing the turn to end. Ran `npm run typecheck` (hard block on error), conditionally ran Playwright if `playwright.config.ts` existed, nudged about UI review when UI files changed. Plus the verifier subagent at `.claude/agents/verifier.md` ran an end-to-end check.
**Compensation:** Manual discipline. Run the verification protocol in [§11](#11-verification-protocol) yourself before claiming done. Don't skip "because the change looks simple" — the Stop hook caught silent regressions specifically when changes looked simple.

### 16.2 Subagent dispatch (`Agent` tool)
**What it did:** Parallel agent fan-out for independent tasks. Sync 14 used "6 implementer dispatches + 12 reviewer dispatches" pattern. Each subagent had isolated context, returned a structured result.
**Compensation:**
- Sequence the work yourself. Slower but the outcome is the same.
- For genuinely independent work, use shell parallelism (`&` + `wait`) or split across multiple Codex sessions.
- For "dispatch a verifier" specifically, just run the verification commands inline.

### 16.3 Auto-memory across sessions
**What it did:** Claude wrote per-project memory at `~/.claude/projects/<encoded-path>/memory/`. Persisted user preferences, project facts, and feedback across sessions.
**Compensation:** Memory facts are inlined at [§6](#6-memory-facts) of this doc. Update them when something material changes. Codex's own memory system (if any in your harness) is additive — use both.

### 16.4 `Skill` tool invocation
**What it did:** Auto-loaded skill content when the situation matched.
**Compensation:** Read `.claude/skills/<name>/SKILL.md` directly when the situation calls for it. The high-leverage skill content is inlined at [§10](#10-workflows), [§12](#12-skills-inventory), [§13](#13-autonomous-execution).

### 16.5 Slash commands
**What they did:** `/verify-scrape`, `/sync-project-state`, `/loop`, `/ultrareview`, `/init`, `/review`, `/security-review`. Claude Code-specific.
**Compensation:**
- `/sync-project-state` → run the workflow at §10.3 manually.
- `/verify-scrape` → run the scraper verification protocol at §11.3.
- `/ultrareview` → multi-agent cloud review of the branch. Claude-Code-specific, billed per-run, not portable. Skip or use whatever review tooling Codex offers.
- `/init`, `/review`, `/security-review` → not project-critical; skip.

### 16.6 `TaskCreate` / `TaskList` task system
**What it did:** Inline task tracking visible to Simon during long runs.
**Compensation:** Use Codex's task system if your harness has one. If not, maintain a local `TODO.md` for multi-step work, or keep a running summary in your responses.

### 16.7 `WebFetch` / `WebSearch`
**What they did:** Browse and search the web inline.
**Compensation:** Use whatever Codex provides. Fallback: `curl -sL <url>` + parse, or ask Simon to run the search.

### 16.8 Permission prompt UX
**What it did:** Claude harness prompted Simon for approval before tool calls outside the allowlist. Simon approved or denied per-call.
**Compensation:** Codex has its own permission model — assume similar gating. Default posture: ask before destructive or external actions, see [§13.1](#131-the-decision-gating-rubric).

---

## 17. Commands Cheat Sheet

### Daily ops
```bash
# Project root (always cd here for relative paths)
cd "/Users/simon/OS/Living VAULT/Content OS/The Hub"

# Status
git status
git log --oneline -10

# TypeScript
npm run typecheck                # strict, must return 0

# Lint
npm run lint                     # eslint via flat config

# Python tests
cd scripts && python3 -m pytest tests -q && cd -

# Browser smoke (slow — only run when changing UI)
npm run test:browser

# Full test suite (slow)
npm run test                     # typecheck + lint + py + browser

# Dev server
npm run dev                      # :3000
npm run start                    # production build

# Build
npm run build
```

### Schema regen (blocked on `SUPABASE_DB_URL` until Simon fills `scripts/.env`)
```bash
npm run db:schema                # regen docs/SCHEMA.md
npm run db:types                 # regen src/types/database.types.ts
```

### Worker ops (launchd-managed)
```bash
bash scripts/worker_ctl.sh status     # is it running?
bash scripts/worker_ctl.sh restart    # SIGTERM, KeepAlive respawns with fresh code
bash scripts/worker_ctl.sh log        # ~/Library/Logs/the-hub-worker.log
bash scripts/worker_ctl.sh err        # ~/Library/Logs/the-hub-worker.err.log

# Plist: ~/Library/LaunchAgents/com.thehub.worker.plist
```

### Pipeline diagnostics
```bash
# One-off Apify actor probes (gitignored .tmp/ dir)
mkdir -p .tmp
# Write a small Python script that calls apify_client and dumps raw JSON.
# Reference scripts/fetchers/ for the call shape.

# Replay dead-letter (currently no script; this is a §20 deferred item)
# scripts/discovery_dead_letter.jsonl is write-only

# Live discovery probe via UI: /creators page → bulk import → watch worker logs
```

### Direct DB (only if you have `SUPABASE_DB_URL` set)
```bash
/opt/homebrew/opt/libpq/bin/psql "$SUPABASE_DB_URL" -c "\\dt"
/opt/homebrew/opt/libpq/bin/psql "$SUPABASE_DB_URL" -c "\\d creators"
```

### Apify-specific
```bash
# Token in scripts/.env as APIFY_TOKEN
# Web UI: https://console.apify.com (Simon's account)
# Common actors:
#   apify/instagram-scraper          (IG details + posts)
#   clockworks/tiktok-scraper        (TT)
#   apify/puppeteer-scraper          (Tier 2 headless harvester)
#   lukaskrivka/results-checker      (validator chain — Phase 2 scraping)
```

---

## 18. End-of-session

When closing out a session:

1. **Verify everything that ran.** Full §11 protocol on changed surface area.
2. **Sync project state** if architectural changes happened. See §10.3.
3. **Write a session note** at `06-Sessions/YYYY-MM-DD.md` (today's date — confirm via `date +%Y-%m-%d`). Append, don't overwrite, if a note exists for today. Format roughly:
   ```markdown
   ## Codex session — <topic>

   **Branch:** <branch> · **Commits:** <range>
   **Outcome:** <one sentence>

   ### What shipped
   - <bullet>

   ### Decisions taken inline
   - <bullet>

   ### Deferred / escalated
   - <bullet>

   ### Verification
   - typecheck: 0 errors
   - pytest: <count> passing
   - browser smoke: <result>
   ```
4. **Update this AGENTS.md** if something material about the handoff changed:
   - New MCP server wired → §9
   - New skill landed → §12
   - Memory fact changed → §6
   - New invariant in the pipeline → reference to PROJECT_STATE §21
5. **Commit and push** if Simon authorized.

---

## Appendix A — File map (quick reference)

```
/Users/simon/OS/Living VAULT/Content OS/The Hub/
├── AGENTS.md                  ← you are here
├── CLAUDE.md                  ← Claude-specific (terse); superseded by this for Codex
├── PROJECT_STATE.md           ← master technical reference
├── README.md                  ← setup
├── Home.md                    ← Obsidian vault home
├── package.json               ← scripts: dev, typecheck, lint, test, db:schema, db:types
├── tsconfig.json
├── playwright.config.ts
├── .claude/
│   ├── settings.json          ← Stop hook config (Claude only)
│   ├── settings.local.json    ← per-machine overrides
│   ├── hooks/
│   │   └── verify-before-stop.sh    ← Stop-hook script (Claude only)
│   ├── agents/
│   │   └── verifier.md        ← Verifier subagent definition (Claude only)
│   └── skills/
│       ├── verify-and-fix/
│       ├── sync-project-state/
│       ├── autonomous-fix-list/
│       ├── autonomous-execution/
│       ├── a11y-audit/
│       ├── shadcn/
│       └── web-design-guidelines/
├── docs/
│   ├── SCHEMA.md              ← live DB ground truth (regen via npm run db:schema)
│   ├── AGENT_USAGE.md         ← agent-stack day-to-day usage
│   └── superpowers/
│       ├── specs/             ← design docs (4 currently)
│       └── plans/             ← execution plans (6 currently)
├── src/
│   ├── app/                   ← Next.js App Router routes
│   │   ├── (dashboard)/
│   │   │   ├── page.tsx               (/)
│   │   │   ├── creators/page.tsx
│   │   │   ├── creators/[slug]/page.tsx
│   │   │   ├── content/page.tsx
│   │   │   ├── trends/page.tsx
│   │   │   └── admin/page.tsx
│   │   └── platforms/
│   │       ├── instagram/accounts/
│   │       └── tiktok/accounts/
│   ├── components/            ← React components
│   ├── lib/
│   │   ├── db/queries.ts      ← typed Supabase query helpers
│   │   ├── platforms.ts       ← PLATFORMS dict + resolvePlatform + HOST_PLATFORM_MAP
│   │   ├── supabase/          ← server + client factories
│   │   └── utils.ts           ← cn() etc
│   └── types/
│       └── database.types.ts  ← generated Supabase types
├── scripts/                   ← Python pipeline
│   ├── .env                   ← SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY, GEMINI_API_KEY, ANTHROPIC_API_KEY, APIFY_TOKEN, ...
│   ├── discover_creator.py    ← top-level discovery entry; _commit_v2; _normalize_handle; _CASE_INSENSITIVE_PLATFORMS
│   ├── worker.py              ← launchd-managed always-on worker
│   ├── worker_ctl.sh          ← install/start/stop/restart/log/err
│   ├── scrape_content.py      ← manual IG/TT content scraper CLI
│   ├── content_scraper/       ← scraper fetchers, normalizers, orchestrator
│   ├── replay_dead_letter.py  ← (currently a stub per §20 deferred item)
│   ├── schemas.py             ← Pydantic models, Platform/EdgeType Literals
│   ├── common.py              ← logging, supabase factory, env loading
│   ├── compile_schema_ref.sh  ← regen docs/SCHEMA.md
│   ├── pipeline/
│   │   ├── canonicalize.py    ← _TRACKING_PARAMS, canonicalize_url
│   │   ├── classifier.py      ← classify(), _classify_linkme_redirector, _classify_via_llm
│   │   ├── identity.py        ← rule-cascade scorer
│   │   ├── resolver.py        ← Stage A + Stage B + _expand recursive funnel
│   │   ├── budget.py          ← BudgetTracker
│   │   └── ...
│   ├── fetchers/
│   │   ├── base.py            ← is_transient_apify_error, tenacity wrappers
│   │   ├── instagram.py       ← apify/instagram-scraper details mode
│   │   ├── tiktok.py          ← clockworks/tiktok-scraper
│   │   ├── youtube.py         ← yt-dlp
│   │   ├── onlyfans.py        ← curl_cffi w/ chrome120 JA3
│   │   ├── instagram_highlights.py    ← shelved (DISCOVERY_HIGHLIGHTS_ENABLED=0)
│   │   └── ...
│   ├── harvester/
│   │   ├── orchestrator.py    ← harvest_urls cascade
│   │   ├── tier1_static.py    ← httpx + BS4
│   │   ├── tier2_headless.py  ← apify/puppeteer-scraper
│   │   └── ...
│   ├── data/
│   │   └── monetization_overlay.yaml   ← gazetteer rules
│   └── tests/
│       ├── test_commit_v2_dedup.py     ← 13 dedup invariants
│       ├── test_platform_enum_drift.py ← static enum lock
│       ├── test_classifier_*.py
│       └── ...
├── supabase/
│   └── migrations/            ← chronological *.sql + MIGRATION_LOG.md
├── 00-Meta/                   ← Obsidian vault sections
├── 01-Product/
├── 02-Architecture/
├── 03-Database/
├── 04-Pipeline/
│   └── Agent Catalog.md       ← per-agent operational details
├── 05-Prompts/
└── 06-Sessions/
    └── YYYY-MM-DD.md          ← session notes
```

---

## Appendix B — Environment variables

`.env.local` (Next.js):
```
NEXT_PUBLIC_SUPABASE_URL=
NEXT_PUBLIC_SUPABASE_ANON_KEY=
```

`scripts/.env` (Python pipeline):
```
SUPABASE_URL=
SUPABASE_SERVICE_ROLE_KEY=
SUPABASE_DB_URL=                # MISSING — blocks db:schema and db:types
GEMINI_API_KEY=
ANTHROPIC_API_KEY=
APIFY_TOKEN=
POLL_INTERVAL_SECONDS=30
MAX_CONCURRENT_RUNS=5

# Discovery flags
DISCOVERY_HIGHLIGHTS_ENABLED=0  # shelved
DISCOVERY_MAX_DEPTH=6
RECURSIVE_GEMINI=1

# Phase 2 scraping watchdogs (automatic cron/webhooks deferred)
APIFY_WEBHOOK_URL_SUCCEEDED=
APIFY_WEBHOOK_URL_FAILED=
APIFY_WEBHOOK_URL_EMPTY_DATASET=
SLACK_WEBHOOK_URL_ALERTS=

# Optional (Sentry, etc)
SENTRY_AUTH_TOKEN=
SENTRY_ORG_SLUG=
```

---

## Appendix C — Phase 2 scraping status

Phase 2 scraping has a manual-trigger foundation. Specs/plans:
- `docs/superpowers/specs/2026-04-27-content-scraper-v1-design.md`
- `docs/superpowers/plans/2026-04-27-content-scraper-v1.md`
- `docs/superpowers/plans/2026-04-27-scraping-followup-without-cron.md`

**Subsystem status** (per PROJECT_STATE §14 + §15.2):

1. **Apify ingestion actors** — `apify/instagram-scraper` (post-mode, not details-mode) for IG; `clockworks/tiktok-scraper` for TT. Both already used in discovery; reuse the connection patterns from `scripts/fetchers/`.
2. **GitHub Actions cron** — explicitly deferred by Simon on 2026-04-27.
3. **Normalizers** — live under `scripts/content_scraper/normalizer.py`.
4. **`quality_flag` + `quality_reason` columns** — live via migration `20260427000000_scraped_content_v1_columns`.
5. **Apify webhooks (4 events)** — not wired while cron is deferred; future path should write `scrape_runs` after pending migration is applied.
6. **`results-checker` validator chain** — schema artifact exists at `schemas/social_post.schema.json`; Apify-console chain still deferred.
7. **Inside each actor run** — Pydantic validation live; deterministic row validator available at `scripts/validate_scraped_content.py`.
8. **`flag_outliers`** — called per-profile after each manual scrape commit.
9. **LLM-as-judge** — still deferred; deterministic `suspicious` rows are ready for it.
10. **Outliers page** — live for Instagram and TikTok with filters.
11. **Audio Trends** — live at `/trends`; broader Trend Signals feed still pending.

**Dependencies between subsystems:**
- (4) `quality_flag` migration before (1) ingestion writes any rows
- (1) ingestion before (8) `flag_outliers` cron
- (8) before (10) Outliers page can show real data
- (5) webhooks should land alongside (1) ingestion, not after
- (6) results-checker is configurable in Apify console; can land last

**Spec/plan template:** mirror the universal-url-harvester plan at `docs/superpowers/plans/2026-04-25-universal-url-harvester.md` for shape.

---

**End of handoff. After reading this, read `PROJECT_STATE.md` and you're oriented.**
