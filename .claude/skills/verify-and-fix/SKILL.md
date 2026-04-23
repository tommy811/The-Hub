---
name: verify-and-fix
description: Use after any edit to src/app/, src/components/, or scripts/ before declaring work complete. Run when a route, component, server action, or pipeline script is claimed to be working.
---

# Verify and Fix

Run the verification loop after every code change. Never declare work done without a verifier pass.

## When to Trigger

Any of these = run verify-and-fix before saying "done":
- Edited any `.ts` / `.tsx` under `src/`
- Edited any `.py` under `scripts/`
- Applied or rolled back a Supabase migration
- Wired a new route, component, or server action

## The Loop

**Step 1 — Invoke the verifier subagent:**

```
Agent({
  subagent_type: "verifier",
  prompt: "Verify changes to [list changed files]. Expected behaviour: [what should now work]."
})
```

**Step 2 — Read the verdict:**

| Verdict | Action |
|---|---|
| `"pass"` | Work is done. You may declare complete. |
| `"fail"` | Fix every failure in `escalation_notes`. Loop back to Step 1. |
| `"inconclusive"` | Resolve the blocking condition (start dev server, check MCP). Loop back to Step 1. |

**Step 3 — Loop limit:** Maximum **3 iterations**. Still failing after iteration 3 → escalate (see below). Do not attempt a 4th fix.

## Escalation

After 3 failed iterations, write to `06-Sessions/YYYY-MM-DD.md`:

```markdown
## Agent Escalations

### verify-and-fix — [timestamp]
**Trigger:** [files changed]
**Outcome:** fail (3 iterations exhausted)
**Evidence:**
- [verbatim check failures from verifier report]
**Proposed next action:** [what needs human input]
```

Then stop. Do not declare done.

## Rules

- The verifier runs **after** your fix, not before. Do not pre-declare a pass.
- "It compiled" is not a pass. The verifier checks HTTP 200, Chrome console errors, and DB query shape.
- A `typecheck` pass from the Stop hook is **not sufficient** — the Stop hook only runs typecheck. This loop runs typecheck + HTTP + DB + Chrome.
- Do not skip invocation because the change "looks simple."

## Red Flags — You Are About to Skip This

| Thought | Reality |
|---|---|
| "The change is too small to verify" | Small changes cause silent regressions. Run it. |
| "I already checked it manually" | Manual checks miss console errors and DB shape mismatches. Run the verifier. |
| "The Stop hook passed, so it's fine" | Stop hook = typecheck only. This loop = full end-to-end. |
| "I'll verify after I declare done" | Verification gates completion. Declare done only after a verifier pass. |
| "The route rendered something" | Rendered ≠ correct. Verifier checks 200, zero console errors, and DB row count. |
