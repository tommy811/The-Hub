# Agent Catalog

> Operational registry of every agent and verifier in The Hub. Each entry documents what triggers the agent, what it does, what tools it has, and when it escalates.
>
> Architecture and per-phase requirements are in [[PROJECT_STATE#15. Agent Architecture|PROJECT_STATE §15–§19]].

---

## Active Agents

_(empty — will populate as agents are built, starting with `verify-and-fix` in Phase 1 retroactive)_

---

## Dev-Time Agents

### verify-and-fix (Phase 1, blocking)

**Trigger:** After any file edit under `src/app/`, `src/components/`, or `scripts/`. Also on explicit phrase "verify the build."

**Layer:** Dev-time (inside Claude Code session)

**Tools (read-only):**
- `Read`, `Grep`, `Glob`, `Bash`
- `mcp__chrome-devtools__*`
- `mcp__playwright__*`
- `mcp__supabase__*` (read-only connection)

**Workflow:**
1. Run `npm run dev` headless in background (Bash tool with `run_in_background: true`)
2. Check TypeScript compile via `npm run typecheck`; if errors, report to implementer and stop
3. For each changed route: curl `http://localhost:3000/<route>` — assert 200, no stack trace in response
4. For pages that render DB data:
   - Use `mcp__supabase__execute_sql` to run the expected query
   - Assert row count matches expectation given the test workspace
   - Assert required columns are non-null per documented schema
5. Use `mcp__chrome-devtools__navigate_page` to open the route in real Chrome
6. `get_console_messages` — assert zero errors
7. `take_screenshot` — capture evidence (agent cannot interpret visually but screenshot is archived for human)
8. For pages with server actions: smoke-test via fake payload
9. Return structured pass/fail JSON. If fail: list specific assertion failures with evidence.

**Escalation:** On failure, writes to `06-Sessions/YYYY-MM-DD.md` under "Agent Escalations" with full context. Does not auto-fix. The implementer (Claude Code) sees the report and iterates.

**Cost estimate:** ~$0.01 per invocation (all read operations, minimal tokens).

---

### verify-scrape (Phase 2, slash command not agent)

**Trigger:** Explicit slash command `/verify-scrape` before declaring any scraper work complete.

**Layer:** Dev-time

**Workflow:**
1. `mcp__apify__get-actor-run-list` limit 1 — assert `status=SUCCEEDED`, `itemCount >= 50`
2. `mcp__apify__get-actor-log` — grep for `sign in|captcha|cf-chl|access denied|log in|blocked` — fail if found
3. `mcp__supabase__execute_sql`:
   ```sql
   SELECT count(*) AS total,
          count(*) FILTER (WHERE author IS NULL) AS nulls,
          count(DISTINCT platform_post_id) AS uniq
   FROM scraped_content
   WHERE inserted_at > now() - interval '1 hour';
   ```
   Assert: `total >= 50`, `nulls/total < 0.05`, `uniq/total > 0.98`
4. `mcp__chrome-devtools__navigate_page` to the platform accounts UI route
5. Wait for network idle; `evaluate_script` to count DOM elements matching selector
6. **Critical assertion:** DB row count ≈ DOM-visible count (within pagination). This is what catches the "data in Supabase but UI empty" case.
7. Report structured JSON. If any step fails, stop and flag.

**Escalation:** Stops the "declare done" workflow. Claude Code must re-run after fix.

---

### schema-drift-watchdog (Phase 2+, ongoing)

**Trigger:** Weekly cron (GitHub Action). Also on phrase "check schema drift."

**Layer:** Dev-time

**Tools:** `Read`, `Grep`, `Glob`, `Bash`, `mcp__supabase__*` (read-only)

**Workflow:**
1. Query live Supabase schema via `mcp__supabase__list_tables` + `list_columns` + `list_functions`
2. Parse `PROJECT_STATE.md` §4 — extract documented tables, columns, enums, RPCs
3. Grep all `src/**/*.ts` and `scripts/**/*.py` for: table names (from documented list), column names, enum values, `.rpc(` calls
4. Produce three-section drift report:
   - **live-vs-docs:** things in Supabase not in PROJECT_STATE (pending migration applied? undocumented change?)
   - **live-vs-code:** things in live schema not referenced in any code (dead columns?)
   - **docs-vs-code:** things documented but not used (speculative schema?)
5. Write report to `06-Sessions/YYYY-MM-DD.md` under "Schema Drift Report"

**Escalation:** Report only. Human decides what to act on.

---

### documentation-drift (ongoing)

**Trigger:** Weekly cron. Companion to `sync-project-state` skill.

**Layer:** Dev-time

**Tools:** `Read`, `Grep`, `Glob`

**Workflow:**
1. Scan every `.md` in vault and repo for:
   - Wiki-links `[[...]]` pointing to files that don't exist
   - References to deprecated patterns (e.g., "archetype on content_analysis" after Phase 2 migration moves it to creators)
   - `.md` files not linked from `Home.md` or any other file (orphans)
   - Session notes older than 30 days still in `06-Sessions/` (archival candidates)
   - Stale "we are here" phase markers
2. Produce drift report under "Documentation Drift" heading in today's session note
3. Propose fixes as approval checklist — does not apply unilaterally

**Escalation:** Report only. Human approves fixes; they run via `sync-project-state`.

---

## Runtime Agents

### scrape-verify (Phase 2, runtime)

**Trigger:** Apify webhook on every actor run completion, failure, timeout, or empty-dataset event.

**Layer:** Runtime (deterministic, not LLM — this is a webhook handler)

**Workflow (Python endpoint at `/api/webhooks/apify`):**
1. Return 200 < 30s; queue heavy work
2. Validate against `lukaskrivka/results-checker` rules (min_items, field success rates, JSON schema)
3. Regex raw HTML sample for auth-wall patterns
4. Pydantic-validate every row before insert to `scraped_content`
5. Set `quality_flag` based on validation:
   - All pass → `clean`
   - Any fail → `suspicious`
   - HTML auth wall detected → `rejected`
6. On `SUCCEEDED_WITH_EMPTY_DATASET` event: alert Slack immediately, do not retry silently
7. On `FAILED` or `TIMED_OUT`: log to Sentry, alert Slack

**Escalation:** Slack webhook. Also writes to `discovery_runs.error_message`.

---

### brand-analysis (Phase 3)

**Trigger:** Manual (per-creator, from creator deep-dive page). Also on new platform scrape completion for a creator (all their scraped platforms considered together).

**Layer:** Dev + Runtime (agent workflow, run as Python subprocess or Supabase Edge Function)

**Tools:** Read-only Supabase, Gemini 1.5 Pro (visual), Claude Sonnet (synthesis)

**Workflow:**
1. Fetch creator + all linked `profiles` + top 20 scraped posts per platform + all content_analysis
2. Fetch link-in-bio destinations from `creator_accounts` where `account_type = 'link_in_bio'`
3. Claude Sonnet synthesis pass:
   - Niche summary
   - USP
   - 5 brand_keywords
   - 5 seo_keywords
   - Proposed creator-level archetype (Jungian 12)
   - Proposed creator-level vibe
4. Write to `creator_brand_analyses` with `version = previous + 1`
5. If proposed archetype/vibe differs from current by > threshold, flag for human review

**Escalation:** Any step erroring → `discovery_runs` row with error. Ambiguous archetype → flag in UI, don't auto-update creator.

**Cost estimate:** ~$0.15 per creator analysis. Run on-demand, not blanket.

---

### label-deduplication (Phase 3, nightly)

**Trigger:** Cron, 2am daily.

**Layer:** Runtime

**Tools:** Supabase (read + write to `content_labels.merged_into_id`), embedding model (Gemini embedding or OpenAI `text-embedding-3-small`), Claude Sonnet for ambiguous cases only

**Workflow:**
1. Fetch all `content_labels` WHERE `usage_count > 0 AND merged_into_id IS NULL`
2. Generate embeddings for each label name + description
3. Pairwise cosine similarity; candidates with similarity > 0.92
4. For pairs ≥ 0.98: auto-merge (set loser's `merged_into_id` → winner)
5. For pairs 0.92–0.98: Claude Sonnet one-shot: "are these the same concept?" — auto-merge on "yes" with confidence
6. For pairs < 0.92: no action
7. Log all actions to a daily audit table

**Escalation:** Human reviews the audit table weekly. Can un-merge if AI got it wrong.

**Cost estimate:** ~$2/month at steady state.

---

### merge-candidate-resolver (Phase 3, nightly)

**Trigger:** Cron, 3am daily.

**Layer:** Runtime

**Workflow:**
1. `SELECT * FROM creator_merge_candidates WHERE status = 'pending'`
2. For confidence ≥ 0.9: call `merge_creators(keep, merge, system_user_id, candidate_id)` RPC
3. For 0.7–0.89: leave for human review
4. Below 0.7: already filtered at creation time, should not appear

**Escalation:** None — high-confidence auto-merges are already the designed behavior.

---

### funnel-inference (Phase 4, weekly)

**Trigger:** Cron, weekly.

**Layer:** Runtime

**Workflow:**
1. For each creator, scan recent content captions for: "link in bio," "@handle," URL patterns
2. Scan link-in-bio provider pages for destinations not yet in `funnel_edges`
3. Propose new `funnel_edges` rows with `confidence` based on evidence strength
4. Do NOT insert as `confidence = 1.0`. All inferred edges start at ≤ 0.7 and require human approval via the funnel editor UI.

---

## Triggers Summary

| Trigger | Agent |
|---|---|
| File edit in `src/app/**` or `src/components/**` | `verify-and-fix` |
| `/verify-scrape` slash command | scrape verification chain |
| Weekly cron Monday | `schema-drift-watchdog` + `documentation-drift` |
| Apify webhook (4 events) | `scrape-verify` |
| Creator page "Run Brand Analysis" button | `brand-analysis` |
| Nightly 2am | `label-deduplication` |
| Nightly 3am | `merge-candidate-resolver` |
| Weekly cron Sunday | `funnel-inference` |

---

## Agent Escalation Protocol

All agents write to `06-Sessions/YYYY-MM-DD.md` under this heading template:

```markdown
## Agent Escalations

### [Agent Name] — [Timestamp]
**Trigger:** [what caused this invocation]
**Outcome:** [pass / fail / ambiguous]
**Evidence:**
- [specific assertion that failed or was uncertain]
- [supporting data]
**Proposed next action:** [what human should do]
```

No agent ever modifies data silently on failure. Escalation is the only failure mode.

---

## Build Order

1. Phase 1 close: `verify-and-fix` (blocking)
2. Phase 2 concurrent with scraping build: `scrape-verify`, `verify-scrape` slash command, `schema-drift-watchdog`
3. Ongoing: `documentation-drift` (set up once, runs forever)
4. Phase 3: `brand-analysis`, `label-deduplication`, `merge-candidate-resolver`
5. Phase 4: `funnel-inference`

Each phase's agents ship with the phase. A phase is not considered closed otherwise.
