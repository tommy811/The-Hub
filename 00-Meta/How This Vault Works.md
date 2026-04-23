# How This Vault Works

## The One Rule
Repo and docs share one folder: `/Users/simon/OS/Living VAULT/Content OS/The Hub`.
`PROJECT_STATE.md` at the repo root is the single source of truth.
Obsidian indexes everything in this folder (code + docs). There is no separate vault and no mirroring — edit `PROJECT_STATE.md` directly and it's already in the vault.

## Folder Guide
| Folder | Purpose |
|---|---|
| 01-Product | Vision, roadmap, backlog, UI decisions |
| 02-Architecture | Schema docs, entity relationships, identity resolution rules |
| 03-Database | Migration log, RPCs, enums, field mappings |
| 04-Pipeline | Discovery, ingestion, Gemini pipelines |
| 05-Prompts | AI Studio + Claude prompts, log of what worked |
| 06-Sessions | Daily work logs — what changed, what's next |

## Workflow

### Every Claude Code session:
1. Claude Code reads `PROJECT_STATE.md` from the repo root first
2. Works on the task
3. Updates `PROJECT_STATE.md` in the same commit if architecture changed
4. No mirroring needed — the file is already visible in Obsidian

### Every AI Studio session:
1. Paste `PROJECT_STATE.md` at the top of your prompt
2. This gives Gemini full context without re-explaining

### Every work session end:
1. Write a new `06-Sessions/YYYY-MM-DD.md`
2. Git commit with a clear message
3. Update `01-Product/Feature Backlog.md` if anything moved

## What the .gitignore and Obsidian Exclusions Do
The repo and vault share one folder, but noise is kept out of both views:
- `.gitignore` excludes Obsidian workspace files, `.DS_Store`, `node_modules`, `.next`, etc. — so git history stays clean
- Obsidian's "Excluded files" setting (in Settings → Files & Links) can exclude `node_modules/`, `.next/`, `src/` if you don't want code files in Obsidian search

## What Kills Project Organization
Keeping decisions in chat history instead of writing them down.
Every architectural decision made in any AI session → write it here.
