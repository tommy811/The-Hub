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
