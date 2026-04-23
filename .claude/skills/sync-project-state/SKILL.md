---
name: sync-project-state
description: Complete project state synchronization across the repo and Obsidian vault. Triggered when the user says "update project state," "sync project," "sync project state," or "update the project." Reads current code and schema state, updates every affected markdown file in both the repo and vault, commits changes, and pushes to GitHub. Ensures PROJECT_STATE.md and all reference docs stay in perfect sync with reality. Use this skill at the end of every work session or after any architectural change.
---

# Sync Project State

This skill keeps The Hub's documentation perfectly in sync with reality by scanning code, schema, and vault state, then updating every affected file deterministically.

## When This Skill Fires

Any of these phrases from the user:
- "update project state"
- "sync project"
- "sync project state"
- "update the project"
- "sync everything"
- "close out the session"

Also fire automatically (without being asked) at the **end** of any session where:
- A new migration was applied to Supabase
- A new route, component, RPC, or enum was added
- A new skill was installed
- A new MCP was connected
- Package.json dependencies changed

## What This Skill Does

Execute in this exact order. Do not skip steps.

### Step 1: Read the master

Read `PROJECT_STATE.md` from the repo root. This is the source of truth. Every other file in this sync mirrors or references it.

### Step 2: Detect what changed since last sync

Run these checks and collect a change report:

**Repo changes:**
- `git log --oneline -20` — recent commits since the last "sync project state" commit
- `git diff HEAD~5 --name-only` — files changed recently
- List of `.sql` files in `supabase/migrations/` — compare against what `PROJECT_STATE.md §4` documents
- List of routes under `src/app/` — compare against `PROJECT_STATE.md §7`
- List of components under `src/components/` — note any new component directories
- List of skills under `.claude/skills/` — compare against `00-Meta/Stack & Tools.md`

**Schema changes** (use the Supabase MCP):
- Call `list_tables` with `schemas: ["public"]` — compare to `PROJECT_STATE.md §4.1`
- Note any new tables, missing tables, or pending tables now applied

**Vault changes:**
- `ls` the Obsidian vault — compare to the expected folder structure in this skill's "Vault Structure Reference" below
- Note new `.md` files that need linking from `Home.md`

Build a changelog: a list of changes to apply across the file network.

### Step 3: Update files

Update these files in order:

**1. `PROJECT_STATE.md` (repo root — same folder as Obsidian vault, no mirroring needed)**
Update all relevant sections based on detected changes:
- §4.1 Live schema — add/remove tables, columns, enums per current Supabase state
- §4.2 Pending migration — mark items as applied (move to §4.1) when Supabase reflects them
- §5 Enums — add new values
- §6 RPCs — add new functions with signatures
- §7 Routes — update wiring status (⬜ Placeholder → 🟡 Partial → ✅ Live)
- §13 Workflow — update if the sync mechanism itself changed
- §14 Build Order — mark phases complete, update "next" status
- Update the "Last synced" date at the top.

**2. `supabase/migrations/MIGRATION_LOG.md`**
Add entry for any new migration file. Format matches existing entries.

**3. `README.md`**
Only update if setup commands or env vars changed.

### Step 4: Update vault docs

The repo and Obsidian vault share one folder (`/Users/simon/OS/Living VAULT/Content OS/The Hub`). No mirroring is needed — `PROJECT_STATE.md` at the repo root is already visible in Obsidian. Use the `kepano/obsidian-skills` skill for proper Obsidian Flavored Markdown (wiki-links, callouts, frontmatter).

**1. `02-Architecture/Entity Relationships.md`**
- New tables → add cardinality entries
- New FKs → add to the FK table
- Removed tables → remove entries

**3. `03-Database/Migration Log.md`**
- New migrations → add dated entry with what changed (tables, enums, RPCs, columns)
- Move previously-pending items to "Applied" section when applicable
- Keep a "Pending — [Phase]" section with upcoming migrations

**4. `03-Database/RPC Reference.md`**
- New functions → add with full signature and purpose
- Changed functions → update signature and behavior description

**5. `03-Database/Enum Reference.md`**
- New enums → add with full value list
- New values on existing enums → add
- Mark pending items clearly with "(pending)" annotation

**6. `03-Database/Apify Field Mappings.md`**
- New platform scraper added → add a mapping table for that platform

**7. `04-Pipeline/*.md`**
- Update pipeline docs if pipeline behavior changed
- If a new pipeline script was added, create a new file or section

**8. `00-Meta/Stack & Tools.md`**
- New AI tool / MCP / skill → add to the relevant section
- Tool evaluated and rejected → add to rejection table with date and reason
- Dependency changes → update tech stack section
- Update "Last synced" date

**9. `00-Meta/Changelog.md`**
Add a new dated entry listing every meaningful change. Format:
```
## YYYY-MM-DD
- Changed: [summary]
- Added: [summary]
- Removed: [summary]
```

**10. `01-Product/Feature Backlog.md`**
- Completed items → change `- [ ]` to `- [x]`
- New items discovered → add to appropriate section (Now / Next / Later / Ideas)

**11. `01-Product/Phase Roadmap.md`**
- Phase completion → update status emoji (🔄 → ✅)
- New phase started → mark WE ARE HERE

**12. `Home.md`**
- Update "Last session" link to today's session file
- Update "Active Work" checklist with current status
- Add quick link for any new major doc

**13. `06-Sessions/YYYY-MM-DD.md`**
- If today's session file doesn't exist, create it with sections: What We Did / Key Decisions / Current Status / Next Session / Files Changed
- If it exists, append a new "## Additional session [timestamp]" section with what happened in this sync

### Step 5: Commit and push

```bash
cd "/Users/simon/OS/Living VAULT/Content OS/The Hub"
git add .
git commit -m "chore: sync project state — [brief summary of biggest change]"
git push
```

### Step 6: Report to user

Output a concise report:
```
✅ Project state synced.

Files updated:
- [list every file touched]

Biggest changes:
- [summary]

Git commit: [hash] — [message]
Pushed to main.
```

If anything could not be updated (missing file, ambiguous change, conflict), list it separately under `⚠️ Needs manual attention:`.

## Idempotency Rules

- **Running this skill twice in a row should produce no changes on the second run.** If it does, the skill has a bug.
- **Do not duplicate entries.** Before adding a table to RPC Reference, check if it already exists there.
- **Preserve manual edits.** If a file has notes or sections not managed by this skill, do not touch them.
- **Deterministic ordering.** Within any list (tables, enums, etc.), alphabetize or follow PROJECT_STATE.md's ordering.

## Vault Structure Reference

Expected folder structure (anything missing should be flagged):

```
The Hub/
├── Home.md
├── 00-Meta/
│   ├── Changelog.md
│   ├── How This Vault Works.md
│   └── Stack & Tools.md
├── 01-Product/
│   ├── Feature Backlog.md
│   ├── Full Product Vision.md
│   ├── Phase Roadmap.md
│   ├── UI Reference.md
│   └── Vision.md
├── PROJECT_STATE.md   ← repo root, also visible in Obsidian (no copy in 02-Architecture)
├── 02-Architecture/
│   ├── Entity Relationships.md
│   └── Identity Resolution Rules.md
├── 03-Database/
│   ├── Apify Field Mappings.md
│   ├── Enum Reference.md
│   ├── Migration Log.md
│   └── RPC Reference.md
├── 04-Pipeline/
│   ├── Apify Actor Registry.md
│   ├── Discovery Pipeline.md
│   ├── Gemini Schema.md
│   └── Ingestion Pipeline.md
├── 05-Prompts/
│   ├── Phase1-Foundation.md
│   ├── Phase2-Platform-Intelligence.md
│   ├── Phase3-Analysis-Engines.md
│   ├── Phase4-Funnel-Viz.md
│   └── Prompt Log.md
└── 06-Sessions/
    └── YYYY-MM-DD.md (one per calendar day)
```

## Failure Modes and Recovery

**If `PROJECT_STATE.md` is malformed or missing:**
Stop. Do not proceed. Report to user that the master document is broken and needs to be rebuilt manually.

**If Supabase MCP is unavailable:**
Skip schema-state checks. Only update doc files based on git log and filesystem state. Note in the final report that schema verification was skipped.

**If git push fails:**
Report the error verbatim to the user. Do not attempt force-push or rebase.

**If a file has a merge conflict marker:**
Stop editing that file. Report the conflict in the final report.

## What This Skill Does NOT Do

- Does not apply new Supabase migrations (user or Claude Code does that manually before running sync)
- Does not generate new code (only documentation)
- Does not rename files (only edits contents)
- Does not reorganize the vault structure (only updates contents)
- Does not install new tools or skills (only documents them after installation)
