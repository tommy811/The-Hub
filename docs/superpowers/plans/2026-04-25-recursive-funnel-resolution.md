# Recursive Funnel Resolution — Plan (Draft)

> **Status:** DRAFT — not yet executed. Brainstormed 2026-04-25 (sync 13 → next). Open thread, ready to refine.
> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:writing-plans` to harden this draft, then `superpowers:subagent-driven-development` (or `superpowers:executing-plans`) to implement.

**Goal:** Close the discovery gap where secondary accounts discovered via the seed (e.g. Kira's Instagram surfaced from her TikTok bio) are recorded as profiles but their *own* `external_urls` and `bio` text-mentions are never expanded — so any link-in-bio aggregator (and everything downstream of it) hanging off a secondary account is invisible to us.

**Concrete failing case (2026-04-25):**
- Seed: `@kira` on TikTok → empty bio, no external links
- Resolver follows TT bio mention to `@kirapregiato` on Instagram → IG profile fetched
- IG profile has a `tapforallmylinks.com/kira` aggregator with OnlyFans + Telegram + more
- We persist the IG profile but **never look at its bio links** → the aggregator is invisible, OF/Telegram/etc. never surface
- User confirmed via manual browser check that those links exist on the IG bio

**Non-goal:** Post-scraping. That stays in Phase 2 (§14 item 9) — separate scheduled worker, separate cost profile.

---

## Architecture

### Current resolver (`scripts/pipeline/resolver.py:135-253`)

```
Stage A: fetch_seed(handle, platform_hint) → seed_ctx
Stage B (seed only):
  for url in seed_ctx.external_urls:
    _classify_and_enrich(url)   ← aggregators expanded once, social/monetization fetched
  gemini_result = run_gemini_discovery_v2(seed_ctx)
  for mention in gemini_result.text_mentions:
    _classify_and_enrich(synth_url(mention))
return { seed_context, gemini_result, enriched_contexts, discovered_urls }
```

The `enriched_contexts` map *contains* fetched secondary `InputContext`s with their own `external_urls` and `bio`, but nothing iterates them.

### Proposed resolver

Bounded recursion. Each newly-enriched social/monetization profile gets one more Stage B pass on its `external_urls` plus a Gemini-bio text-mention extraction.

```
Stage A: fetch_seed → seed_ctx, depth=0
Stage B (recursive, depth-bounded):
  visited_canonical, aggregator_expanded, enriched_depth = {}, {}, {}

  def expand(ctx, depth):
    if depth >= MAX_DEPTH: return
    for url in ctx.external_urls:
      _classify_and_enrich(url, parent_depth=depth)
    if depth == 0 OR enable_secondary_gemini:
      gemini_for_ctx = run_gemini_text_mentions(ctx)   # bio-only Gemini call (cheap)
      for mention in gemini_for_ctx.text_mentions:
        _classify_and_enrich(synth_url(mention), parent_depth=depth)

  _classify_and_enrich(url, parent_depth):
    ... classify, dedup ...
    if account_type == link_in_bio: expand aggregator children once (no chaining)
    elif account_type in {social, monetization}: enrich (fetch profile)
       if enriched: expand(ctx, parent_depth + 1)   ← NEW
```

**Constants:**
- `MAX_DEPTH = 2` (seed=0, secondary=1, would-be-tertiary blocked). Tunable via env var `DISCOVERY_MAX_DEPTH`.
- Existing `BudgetTracker` still gates every fetch — runaway is impossible.
- Existing `visited_canonical` set still dedupes — we never re-fetch the same canonical URL.
- Existing aggregator chain rule (`is_aggregator_child=True`) still applies — Linktree-from-Beacons stays blocked.

**Gemini call for secondaries — design choice:**

Option A: Reuse the full `run_gemini_discovery_v2` per secondary. Expensive — that prompt is canonicalization + niche + mentions. Overkill for "just give me handles in this bio."

Option B (preferred): Add a tiny `run_gemini_bio_mentions(ctx) → list[TextMention]` that takes only the bio and asks for `@platform/handle` mentions. Single small Gemini Flash call (~$0.001). Keep canonicalization/niche only on the seed where it's needed.

Option C: Skip Gemini on secondaries entirely; rely only on `external_urls`. Cheaper but misses bios that say "follow me on TikTok @foo" without a clickable link. Most platforms don't allow clickable mentions in bio anyway, so this is a real loss.

→ Default to **Option B** behind a feature flag `DISCOVERY_RECURSIVE_GEMINI=1`. Falls back to C if flag is off.

---

## Tasks

### Task 0 — Pre-flight

**Files:** none

- [ ] Confirm branch is `phase-2-discovery-v2` (or new branch off it: `phase-2-recursive-funnel`)
- [ ] Confirm tree clean
- [ ] Confirm pytest 107 green: `cd scripts && python -m pytest`
- [ ] Confirm `tsc --noEmit` 0

### Task 1 — Schema check (likely no migration needed)

**Files:** none

- [ ] Verify `discovery_runs.assets_discovered_count` already counts everything we'd write. It does.
- [ ] Verify `profiles.discovery_reason` can absorb new reason strings (it's `text`, not enum). It can. New reasons: `recursive:level_2`, `recursive_aggregator:level_2`.
- [ ] No schema change required. Skip migration.

### Task 2 — Add `MAX_DEPTH` plumbing

**Files:**
- Modify: `scripts/pipeline/resolver.py`

- [ ] Add module constant `MAX_DEPTH = int(os.getenv("DISCOVERY_MAX_DEPTH", "2"))`
- [ ] Add `recursive_gemini_enabled = os.getenv("DISCOVERY_RECURSIVE_GEMINI", "1") == "1"` constant
- [ ] Refactor `resolve_seed` body into a private `_expand(ctx, depth)` with the recursion structure above
- [ ] Pass `parent_depth` through `_classify_and_enrich`
- [ ] On successful enrich, call `_expand(ctx, parent_depth + 1)` if `parent_depth + 1 < MAX_DEPTH`
- [ ] Keep all existing dedup / aggregator / budget guards in place — they should already be safe under recursion since `visited_canonical` is a closure-shared set

### Task 3 — Light-weight Gemini bio-mentions extractor

**Files:**
- Modify: `scripts/discover_creator.py` (or split into `scripts/llm/gemini_bio.py`)

- [ ] Add `run_gemini_bio_mentions(ctx: InputContext) -> list[TextMention]`
- [ ] Prompt: "Extract @platform/handle mentions from this bio. Return JSON list of {platform, handle, source_text}. Bio: {ctx.bio}"
- [ ] Use Gemini Flash (cheapest tier). Hard cap output tokens at 256.
- [ ] Pydantic-validate response against `list[TextMention]`. Catch `ValidationError` → return `[]` (don't crash discovery)
- [ ] Re-export from `scripts/pipeline/resolver.py` import site so tests can monkey-patch

### Task 4 — Wire recursive Gemini into the new `_expand`

**Files:**
- Modify: `scripts/pipeline/resolver.py`

- [ ] At depth 0: keep using `run_gemini_discovery_v2` (canonicalization + niche + mentions — needed for the creator-level row)
- [ ] At depth >= 1 and `recursive_gemini_enabled`: call `run_gemini_bio_mentions(ctx)` only
- [ ] Feed mentions into the same `_classify_and_enrich` loop with `parent_depth=current_depth`

### Task 5 — Progress UI updates

**Files:**
- Modify: `scripts/discover_creator.py` — `_make_progress_writer` stage table

- [ ] Add new stage label `"Mapping secondary funnels"` at ~50% pct, between "Resolving links" (35%) and "Analyzing" (70%)
- [ ] Resolver emits this label when entering depth >= 1 expansion
- [ ] No DB schema change — just new label values

### Task 6 — Tests (pytest)

**Files:**
- Modify: `scripts/tests/pipeline/test_resolver.py`
- Create: `scripts/tests/pipeline/test_resolver_recursive.py`

Test cases:
- [ ] Depth-2 recursion: seed has TT bio mention of IG, IG has linktree, linktree has OF → all 3 land in `discovered_urls`
- [ ] Depth-3 blocked: tertiary IG would mention another TT — confirm we DO NOT fetch the tertiary
- [ ] Aggregator chain still blocked: depth-1 secondary has linktree, linktree has another linktree → second linktree NOT expanded (existing rule preserved)
- [ ] Budget exhaustion mid-recursion: `BudgetTracker.debit` raises on 4th fetch → resolver stops cleanly, partial result returned
- [ ] Visited dedup across depths: secondary IG mentions seed back → seed's canonical URL is already in `visited_canonical` → no infinite loop
- [ ] `recursive_gemini_enabled=False` skips secondary Gemini calls but still expands `external_urls`
- [ ] Empty bio on secondary: `run_gemini_bio_mentions` returns `[]`, recursion completes without error

Target: pytest 107 → ~115 (8 new tests, no existing breaks).

### Task 7 — Smoke test on Kira

**Files:** none (operational)

- [ ] On dev: re-run discovery for Kira via `/creators/[slug]` → "Re-run Discovery" button
- [ ] Watch worker log: should see "Mapping secondary funnels" stage emitted
- [ ] Confirm new profiles land: OnlyFans, Telegram, anything else hanging off her IG aggregator
- [ ] Confirm `profile_destination_links` has the new aggregator children with `source_platform=instagram` (not tiktok — the aggregator is on her IG, not her TT)
- [ ] Spot-check via Chrome DevTools MCP: `/creators/kira-p` HQ page renders the new accounts under correct platform sections

### Task 8 — Sync project state

**Files:**
- Modify: `PROJECT_STATE.md` (Decisions Log, §14 build order, §6 RPC table if needed)
- Modify: `06-Sessions/YYYY-MM-DD.md` (the session this lands in)

- [ ] Run `/sync-project-state`
- [ ] Commit + push

---

## Cost / risk analysis

**Apify cost per discovery (estimated):**
| | Current (v2 SP1) | Proposed (recursive) |
|---|---|---|
| Best case (no secondaries) | ~$0.10 | ~$0.10 |
| Typical (2-3 secondaries) | ~$0.30 | ~$0.30 (already fetched, no extra calls) |
| Heavy (5+ secondaries with their own aggregators) | ~$0.50 | ~$0.50 |

**Net cost delta: ~$0.001 per secondary for the bio-mentions Gemini Flash call.** No additional Apify calls because the secondary profile fetch already happened in v2 SP1 — we're just *also using* the bio + external_urls we already pulled.

**Risk: runaway expansion.** Triple-bounded:
1. `MAX_DEPTH=2` hard cap
2. `BudgetTracker` (existing — caps total Apify spend per discovery run)
3. `visited_canonical` set (existing — dedup across all depths)

No new failure modes vs current pipeline.

---

## What this does NOT do

- Post scraping (50-100 recent posts per profile for outliers/trends) → Phase 2 §14 #9, separate scheduled worker
- Tertiary recursion (depth >= 3) → diminishing returns, would 2x the surface area
- Cross-creator funnel inference → `funnel-inference` runtime agent, Phase 4 (§16)
- Re-scraping existing profiles' bios → only runs at discovery time / Re-run Discovery; bio-refresh cadence is a separate question

---

## Open questions

1. Should `recursive_gemini_enabled` default to ON or OFF for the first cut? Cheap call but adds a Gemini dep on every secondary. **Tentative: ON** — we already have the Gemini key wired and the cost is negligible.
2. Should depth-1 results carry a `discovery_confidence` lower than depth-0 (e.g. 0.85 vs 0.9)? **Tentative: yes**, drop confidence linearly with depth.
3. Should the smoke test be automated or manual the first time? **Tentative: manual** — Kira is the canonical case and we want eyes on the result before we trust the recursion.
