# Stack & Tools

> The complete toolkit for The Hub. Every AI, every service, every skill, every MCP, every rejected option and why. Read this before onboarding, before deciding whether to adopt a new tool, or when you forget what's connected.

**Last synced:** 2026-04-26 (sync 16 — profile noise filter retroactive, specific platform identification, AccountRow + banner foundation)

---

## AI Tools

| Tool | Role | Used For |
|---|---|---|
| **Claude (web/desktop)** | Architecture partner | Schema design, prompt writing, decision-making, doc authoring, audit strategy, clarifying questions |
| **Google AI Studio (Gemini)** | Bulk code generator | Large code generation passes — initial Next.js codebase, creators hub, discovery pipeline boilerplate |
| **Claude Code** | Hands-on executor | Running migrations via MCP, editing files, applying audits, committing to git, updating docs |

**Division of labor:** Claude for thinking, AI Studio for large generative passes, Claude Code for actual file/DB work.

---

## AI Models (Committed Routing)

| Model | Used For |
|---|---|
| **Gemini 2.5 Flash** | Creator discovery (fishnet + funnel), content visual/multimodal analysis |
| **Gemini Flash** | Quick classification with enum-constrained outputs |
| **Claude Sonnet** | Brand analysis, hook pattern analysis, narrative reasoning |
| **Claude Opus / Sonnet** | Multi-step agent workflows (Phase 3+) |

**Principle:** Gemini for vision and multimodal. Claude for writing and reasoning.
**Full detail:** [[PROJECT_STATE#8. LLM Routing]]

---

## Infrastructure & Services

| Service | Role | Location / ID |
|---|---|---|
| **Supabase** | Postgres + Auth + RLS + Realtime + Storage + Edge Functions | Project: Content OS (`dbkddgwitqwzltuoxmfi`, us-east-1) |
| **GitHub** | Source control, handoff point between tools | `tommy811/The-Hub` |
| **Obsidian** | Project knowledge base | Vault path: `/Users/simon/OS/Living VAULT/Content OS/The Hub` (same folder as repo) |
| **Apify** | Social media scraping platform + page-level harvest | Actors: `apify/instagram-scraper`, `clockworks/tiktok-scraper`, **`apify/puppeteer-scraper`** (added 2026-04-26 — backs Tier 2 of the Universal URL Harvester; runs a custom `page_function.js` that hooks `window.open`/`location.href` setters before page scripts execute and auto-clicks 7 interstitial keyword variants for sensitive-content / "open link" gates) |
| **macOS launchd** | Always-on discovery worker (local dev) | User agent `com.thehub.worker` at `~/Library/LaunchAgents/com.thehub.worker.plist`. Runs `scripts/worker.py` with RunAtLoad + KeepAlive + ThrottleInterval=10s. Logs at `~/Library/Logs/the-hub-worker.{log,err.log}`. Managed via `scripts/worker_ctl.sh {install|start|stop|restart|unload|status|log|err|uninstall}`. After any pipeline code change, run `scripts/worker_ctl.sh restart` so the process respawns with fresh bytecode. |

---

## MCP Servers Connected

| Server | Status | Role |
|---|---|---|
| **Supabase MCP** | Active, used | Direct database migrations, table inspection, RPC deployment, schema verification |
| **n8n MCP** | Connected, idle | Workflow automation — not yet used for this project |
| **Airtable MCP** | Connected, idle | Airtable read/write — not yet used for this project |
| **Google Drive MCP** | Connected, idle | Drive file access — not yet used for this project |

**How to add more:** configure connectors in Claude's connector settings. New MCPs auto-appear in Claude Code's tool list.

---

## Claude Code Skills Installed

| Skill | Location | Purpose |
|---|---|---|
| **kepano/obsidian-skills** | `.claude/skills/` in vault root | Obsidian Flavored Markdown (wiki-links, callouts, properties), Bases YAML, Canvas JSON, Obsidian CLI |
| **sync-project-state** | `.claude/skills/sync-project-state/` | Automated project state sync (triggered by "update project state" or "sync project") |
| **verify-and-fix** | `.claude/skills/verify-and-fix/` | Post-change verification loop — invokes verifier subagent, iterates up to 3×, escalates to session note on exhaustion |
| **autonomous-execution** | `.claude/skills/autonomous-execution/` | Decision-gating policy for subagent-driven / multi-task work where the user has explicitly granted autonomy. Codifies which decisions warrant interrupting vs proceeding with best judgment. |
| **autonomous-fix-list** | `.claude/skills/autonomous-fix-list/` | Workflow companion to autonomous-execution. Triggered when Simon hands a fix list with phrases like "full autonomy", "every permission granted", "use subagents to run everything", "minimal input from my end". Runs plan → dispatch (parallel where independent, sequenced where dependent) → catch unrelated regressions inline → final verify (tsc + pytest + visual via Chrome DevTools MCP) → push → report end-to-end with zero check-ins. |
| **superpowers** | installed | Verification gate, TDD enforcement, verifier subagent patterns |
| **webapp-testing** (via anthropics/skills) | installed | Next.js + Python test patterns, multi-server lifecycle |
| **shadcn** | `.claude/skills/shadcn/` | Deep shadcn/ui component knowledge — component selection, CLI usage, theming, registry authoring. Activates when `components.json` exists. |
| **web-design-guidelines** | `.claude/skills/web-design-guidelines/` | UI consistency auditor — audits code against 100+ Vercel Web Interface Guidelines rules (a11y, focus states, forms, animation, typography, images, performance, dark mode). |
| **a11y-audit** | `.claude/skills/a11y-audit/` | WCAG 2.1 AA accessibility auditor — template-aware page sampling, axe-core + Puppeteer scanning, prioritized findings with remediation hints and progress tracking across audits. |

> **Planned agents:** see [[PROJECT_STATE#16. Per-Phase Agent Requirements]] for the full per-phase agent requirements. All agent operational details are in [[04-Pipeline/Agent Catalog]].

### Installation commands

**kepano/obsidian-skills:**
```bash
cd "/Users/simon/OS/Living VAULT/Content OS/The Hub"
npx skills add git@github.com:kepano/obsidian-skills.git
```

**sync-project-state:** see the skill file at `.claude/skills/sync-project-state/SKILL.md` — written manually and committed to the vault.

---

## Tech Stack

### Frontend
- Next.js 16.2.4 (App Router, Server Components where possible)
- TypeScript strict mode
- Tailwind CSS
- shadcn/ui
- Playwright browser smoke tests
- Recharts (viz)
- lucide-react (generic icons + brand-icon fallbacks; also covers Cash App / Venmo / Fanfix as `DollarSign`/`Heart` fallbacks where react-icons has no Simple Icon match, plus the unified aggregator clip icon `Link` used for linktree/beacons/custom_domain)
- react-icons 5.6.0 (Simple Icons + FontAwesome — real platform brand glyphs: `SiInstagram`, `SiTiktok`, `SiYoutube`, `SiX`, `SiFacebook`, `SiPatreon`, `SiOnlyfans`, `SiTelegram`, `SiLinktree`, `FaLinkedin`, `FaAmazon`. Sync 16 (2026-04-26) added: `SiReddit`, `SiSnapchat`, `SiThreads`, `SiBluesky`, `SiSpotify`, `SiSubstack`, `SiDiscord`, `SiWhatsapp`, `SiKofi`, `SiBuymeacoffee` to the PLATFORMS dict in `src/lib/platforms.ts`. No new dependencies — all glyphs verified present in react-icons 5.6.0.)
- framer-motion (animations)
- @xyflow/react (React Flow — funnel editor, stubbed for Phase 1)

### Backend / Pipeline
- Python 3.11+
- `supabase-py` (DB client)
- `apify-client` (scraping + page-level harvest via `apify/puppeteer-scraper`)
- `google-generativeai` (Gemini)
- `anthropic` (Claude, Phase 3)
- `pydantic` v2 (validation)
- `tenacity` (retry logic)
- `rapidfuzz` (handle similarity)
- `httpx` (HTTP client + Tier 1 of Universal URL Harvester)
- `beautifulsoup4` (HTML parsing + Tier 1 anchor extraction)
- `curl_cffi` (chrome120 JA3 impersonation — OnlyFans fetcher)
- `yt-dlp` (YouTube channel info)
- `rich` (structured logging)

### Pipeline package layout (`scripts/`)
- `pipeline/` — resolver, classifier, identity, canonicalize, budget
- `fetchers/` — 9 platform fetchers (IG, TT, YT, OF, Patreon, Fanvue, generic, FB stub, X stub) + `instagram_highlights.py` (shelved, runtime-gated)
- **`harvester/`** — Universal URL Harvester (added 2026-04-26): `orchestrator.py` (cache → Tier 1 → Tier 2 → classify cascade), `tier1_static.py` (httpx + 4-signal escalation detector), `tier2_headless.py` (Apify Puppeteer Scraper integration), `page_function.js` (in-browser hooks + auto-click), `cache.py` (24h TTL on `url_harvest_cache`), `types.py` (`HarvestedUrl`, `Tier1Result`, 10-value `DestinationClass` Literal). Replaces the deleted `aggregators/` package.
- `worker.py` — launchd-managed long-running poller (`scripts/worker_ctl.sh` for lifecycle)
- `discover_creator.py` — per-run orchestration around the resolver

### Testing
- ESLint flat config for repo-wide linting
- `tsc --noEmit` typecheck gate
- `pytest` for the Python pipeline
- Playwright browser smoke suite for route and console coverage

---

## Evaluated and Rejected Tools

Decisions saved here so future-you doesn't re-evaluate.

| Tool | Rejected On | Reason |
|---|---|---|
| **Sleestk/Skills-Pipeline** (Obsidian Power User skill) | 2026-04-23 | Over-engineered — teaches Claude every Obsidian feature (Dataview, Templater, Publish, Web Clipper, CLI, every core plugin). We use ~15% of that. kepano's skill covers what we need. |
| **graphify** (`pip install graphifyy`) | 2026-04-23 | Semantic codebase indexing. Pays off at 50+ source files with deep cross-refs. Current codebase is ~25 files. Revisit in Phase 2 when codebase grows. |

---

## Workflow Patterns (Reusable)

### 1. Audit-before-apply
**When:** Making sweeping changes to docs or code (especially sync tasks).
**How:** Two Claude Code sessions — one read-only audit producing a diff report, user approves items, second session applies only approved changes.
**Why it works:** Prevents Claude Code from making plausible-but-wrong changes at scale. First pass is cheap; second pass is surgical.
**Used in:** Post-rewrite audit of vault vs. code vs. PROJECT_STATE on 2026-04-23.

### 2. Insert-first, enrich-later
**When:** UI flows where user input should feel instantaneous but requires async processing.
**How:** Insert placeholder row with `onboarding_status = 'processing'` synchronously. Trigger async pipeline. Use Realtime to flip UI state when done.
**Used in:** Creator bulk import — cards appear in grid immediately, discovery pipeline enriches async.

### 3. Upsert-never-duplicate
**When:** Ingesting external data.
**How:** Every external-facing row has a natural unique key. All writes use `ON CONFLICT (unique_key) DO UPDATE`.
**Used in:** All scraping pipelines, discovery commits, profile imports.

### 4. Schema-first phased delivery
**When:** Multi-phase product where later phases build on earlier.
**How:** Build the full schema upfront (even for future phases). Each phase is purely additive — no migrations needed to support later phases.
**Used in:** All 20 tables built in Phase 1 even though only 8 are actively used. Phases 2–4 are additive only.

### 5. Paste PROJECT_STATE.md at every AI session start
**When:** Any new AI Studio / Claude session on this project.
**How:** Copy `PROJECT_STATE.md` from repo root → paste at top of prompt.
**Why:** Gives the AI full schema + conventions + decisions context in one shot. No re-explaining.

### 6. One-command project sync
**When:** End of every work session or after any architectural change.
**How:** Say "update project state" → triggers the sync-project-state skill.
**Why:** Prevents doc drift. Every file that needs updating gets updated deterministically.

### 7. Schema-first, agent-last
**When:** Deciding where a new capability belongs (code vs agent).
**How:** Default to straight code. Introduce agents only when a workflow requires iterative reasoning — reading output, deciding next action, looping. Phase 3+ is the first real candidate.
**Why:** Agents are expensive and hard to debug. Code is deterministic and fast.

### 8. Agents are phase deliverables, not afterthoughts
**When:** Scoping any new phase.
**How:** Before starting feature work, define required agents in Phase Roadmap. Build agents alongside features. Don't defer.
**Why:** "We'll add the agent later" always becomes never. Agents that aren't phase-blocking never get built.

### 9. Verify before declaring done
**When:** Any code change claims to wire up new functionality — routes, components, server actions.
**How:** The verify-and-fix agent runs after every such change. Starts dev server, checks TypeScript compile, curls affected pages for 200 response, verifies Supabase query shapes via MCP, smoke-tests server actions with test payloads. Auto-fixes up to 3 loops. Escalates on 3rd failure with full error context written to today's session note.
**Why it works:** Solves the "AI says it works, doesn't actually work" pattern by forcing verification before the "done" declaration. Not optional.
**Introduced in:** Phase 1 (retroactive).

---

## Quick Reference: Environment Variables

### Next.js (`.env.local`)
```
NEXT_PUBLIC_SUPABASE_URL=
NEXT_PUBLIC_SUPABASE_ANON_KEY=
```

### Python (`scripts/.env`)
```
SUPABASE_URL=
SUPABASE_SERVICE_ROLE_KEY=
GEMINI_API_KEY=
ANTHROPIC_API_KEY=
APIFY_TOKEN=
POLL_INTERVAL_SECONDS=30
MAX_CONCURRENT_RUNS=5
```

---

## Project Principles (committed)

1. Supabase is the source of truth — UI never stores data
2. `PROJECT_STATE.md` is the master technical doc — everything else mirrors it
3. Build as code first — introduce agents only for iterative reasoning (Phase 3+)
4. Insert-first, enrich-later — UX responsiveness over consistency
5. RLS on every table — workspace isolation enforced at the DB
6. Typed end-to-end — Pydantic v2 on Python, generated types on Next.js
7. Schema-first development — DB contract before UI
8. Audit before apply — for any sweeping change
9. One command sync — "update project state" closes the loop
10. Agents are phase deliverables — a phase closes only when its agents are built and validated

---

## When to Update This File

- New AI tool, service, or MCP connected
- Claude Code skill installed or removed
- Tech stack dependency added or removed
- Tool evaluated and rejected (add to rejection table with reason)
- New workflow pattern emerges worth documenting
- Infrastructure migration (new project, region change, etc.)

This file is owned by the sync skill — it updates automatically when any of the above are detected in a commit. Manual edits welcome; the skill preserves them.
