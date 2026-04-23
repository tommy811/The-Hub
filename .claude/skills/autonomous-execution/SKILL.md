---
name: autonomous-execution
description: Use at the start of any subagent-driven or multi-task execution where the user has explicitly granted autonomy ("just do it", "keep working", "proceed"). Codifies which decisions warrant interrupting the user vs. proceeding with best judgment, and surfaces routine decisions in post-task reports instead of during work.
---

# Autonomous Execution — Decision Gating Policy

## When to invoke

At the start of any execution loop where the user has granted autonomy. This includes:

- Subagent-driven plan execution (always)
- Multi-task runs started with "go ahead", "just do it", "keep working", "proceed"
- Continuing a plan after the user has approved scope and the major decisions

**Do NOT invoke** for: exploratory brainstorming, initial scoping, research the user is actively supervising, or one-shot questions.

## The rule

Prompt the user ONLY for **MAJOR decisions**. For everything else, proceed with best judgment using project context and report what you decided in the post-task summary.

### MAJOR — must escalate

1. **Destructive or irreversible actions** — deleting data, dropping tables, force-pushing, `rm -rf`, overwriting uncommitted work, amending published commits.
2. **External / shared-state mutations** — pushing to remote, creating/merging PRs, sending messages, posting to third-party services, modifying shared infrastructure or permissions.
3. **Cost-incurring actions beyond pre-approved ceiling** — LLM calls, API runs, Apify scrapes that exceed the budget the user signed off on.
4. **Scope or architecture deviations** — when the plan doesn't cover the situation and the resolution changes what gets built.
5. **Security-sensitive choices** — auth, secrets, permissions, RLS changes.
6. **New dependencies** — adding a package/library not in the approved plan.
7. **Genuine forks with real downstream consequences** — when picking either path commits the project to materially different follow-up work.
8. **Verification failure with ambiguous root cause** — tests or smoke-tests fail and you can't confidently identify the fix after one focused debugging pass.

### ROUTINE — proceed, report in summary

- Naming variables, functions, helpers, files
- Error-message wording, log phrasing
- Test-assertion phrasing and ordering
- Picking between two equivalent idioms already used in the codebase
- Where to place a helper / how to organize imports
- Small cosmetic deviations from the plan (if plan is unclear, pick best)
- Recoverable code choices (easy to change later)
- Whether to write a comment
- Whitespace, formatting, stylistic choices
- Pinning minor versions of already-approved libraries

## Borderline-case heuristic

Ask yourself, in order:

1. **Reversible in ≤10 min?** Yes → decide, report.
2. **Within the user's approved plan and decisions?** Yes → decide, report.
3. **Does either path commit the project to materially different follow-up work?** Yes → escalate. No → decide, report.
4. **Does it cost money, touch shared systems, or risk data loss?** Yes → escalate.

If still unsure → escalate. Cost of a confirmation is low; cost of getting a bet wrong is high.

## How to surface routine decisions

In end-of-task / end-of-phase reports, include a **Decisions taken** section listing non-obvious autonomous choices:

```
Decisions taken:
- Placed the dead-letter file at `scripts/discovery_dead_letter.jsonl` (plan
  said "writes to a dead-letter file" without specifying path). Env-overridable
  via DISCOVERY_DEAD_LETTER_PATH.
- Named the Apify helper module `apify_details.py`. Matches the naming pattern
  of apify_scraper.py.
- Pinned pytest 8.2.0 + pytest-mock 3.14.0 as latest minor-stable.
```

This gives the user a quick scan of what's reversible without interrupting flow.

## How to escalate

When you hit a MAJOR decision, STOP and report concisely:

1. **What you're about to do** — one sentence
2. **Why it qualifies as major** — which of the 8 criteria above it matches
3. **2–3 concrete options** with tradeoffs
4. **Your recommendation**

Wait for explicit approval. A prior blanket "keep going" covers routine decisions only — MAJOR still requires explicit approval.

## Subagent inheritance

When dispatching subagents under this policy, include this clause in their prompt:

> Operate autonomously within the approved plan. Only escalate (return with a blocker report) if you hit a MAJOR decision per `autonomous-execution` criteria: destructive/irreversible action, external-state mutation, scope/architecture deviation, new dependency, security-sensitive choice, cost overrun, or verification failure you can't resolve after one focused debugging pass. For routine choices (naming, placement, wording), decide and report in the summary.

## Stop conditions

Pause and report to the user when:

1. A verification step fails 2x with the same root cause after fix attempts
2. A migration fails or cannot be rolled back safely
3. A plan assumption turns out to be false (library doesn't exist, API signature changed, column missing)
4. You discover unfamiliar uncommitted work, unexpected branches, or in-progress user state
5. Cost tracking exceeds the pre-approved ceiling
6. Any MAJOR decision per the rule above

## Interaction with other skills

This is a policy layer. It does not replace:

- `superpowers:executing-plans` / `superpowers:subagent-driven-development` — govern execution mechanics
- `superpowers:verification-before-completion` — always run verification regardless of autonomy
- `superpowers:systematic-debugging` — still applies when things break
- `verify-and-fix` — still the gate before declaring tasks done

This skill governs WHEN to interrupt the user, on top of those skills.
