# Recursive Funnel Resolution Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Follow each creator's funnel trail to its natural terminus — not just the seed's bio, but every secondary profile's bio + external links — so that anything hanging off (e.g.) a creator's IG aggregator surfaces in discovery instead of being invisible.

**Architecture:** Replace the seed-only Stage B in `scripts/pipeline/resolver.py` with bounded recursion through `_expand(ctx, depth)`. Termination is **natural** — a profile is "terminal" iff its enrichment surfaces no new external_urls and (with flag on) no new bio mentions. Existing guards (`visited_canonical` cycle dedup, `BudgetTracker` cost cap, aggregator-no-chain rule) carry over. A defensive `MAX_DEPTH=6` only exists to guarantee no pathological loop. Discovery confidence drops linearly with depth (depth 1 = 0.9 → depth 9+ floors at 0.5).

**Tech Stack:** Python 3.11+, Pydantic v2, pytest (existing 107 tests must stay green), Gemini 2.5 Flash for the new lightweight bio-mentions extractor, existing Apify/yt-dlp/curl_cffi/httpx fetchers. No schema migration required.

---

## File Structure

| File | Responsibility | Action |
|---|---|---|
| `scripts/schemas.py` | Pydantic models. Add `depth` field to `DiscoveredUrl` so commit can apply depth-aware confidence | Modify |
| `scripts/pipeline/resolver.py` | The recursion. New `_expand(ctx, depth)` + `MAX_DEPTH` + `RECURSIVE_GEMINI` env flag + per-depth confidence + new "Mapping secondary funnels" progress label | Modify |
| `scripts/discover_creator.py` | Owns Gemini integrations. Add `run_gemini_bio_mentions(ctx) → list[TextMention]` (cheap Flash call). `_commit_v2` reads `DiscoveredUrl.depth` to set `discovery_confidence` for non-seed profiles | Modify |
| `scripts/tests/pipeline/test_resolver_recursive.py` | All new recursion tests in their own file. Existing `test_resolver.py` stays untouched (its 4 tests must keep passing as a regression check) | Create |

---

## Pre-Execution Notes for the Worker

1. The resolver's existing tests (`scripts/tests/pipeline/test_resolver.py`) must stay green throughout. Run `cd scripts && python -m pytest` before each commit.
2. The pattern for mocking Gemini is `@patch("pipeline.resolver.run_gemini_discovery_v2")` because `pipeline.resolver` re-imports it from `discover_creator` via a wrapper. Apply the same pattern for the new `run_gemini_bio_mentions` — add a wrapper in `pipeline/resolver.py` and tests patch `pipeline.resolver.run_gemini_bio_mentions`.
3. Patching fetchers: `@patch("pipeline.resolver.fetch_ig.fetch")` etc. — they're already imported as module aliases in resolver.py.
4. Don't break the `MagicMock()` supabase pattern in tests — the classifier's `_cache_lookup` accepts None gracefully (commit `48849e7` already proved this on the live smoke).
5. The `_classify_and_enrich` helper is a closure inside `resolve_seed`. Recursion through it is straightforward — don't extract it to module scope unless absolutely necessary; the closure lets it share `visited_canonical`, `aggregator_expanded`, `enriched`, etc.

---

## Task 0 — Pre-flight

**Files:** none

- [ ] **Step 1: Confirm git state**

```bash
git status
git branch --show-current
```

Expected: tree clean (or only `.tmp/` untracked), branch is `phase-2-discovery-v2`. If you want isolation from the main work branch, branch off now: `git checkout -b phase-2-recursive-funnel`. Otherwise stay on `phase-2-discovery-v2` and the commits will land directly there.

- [ ] **Step 2: Confirm pytest baseline**

```bash
cd scripts && python -m pytest -q
```

Expected: `107 passed` (or more — if PROJECT_STATE has been updated since the plan was written, use whatever the current count is, but record it as the baseline).

- [ ] **Step 3: Confirm tsc baseline**

```bash
cd "/Users/simon/OS/Living VAULT/Content OS/The Hub" && npx tsc --noEmit
```

Expected: 0 errors. (No TypeScript changes are planned, but track this baseline anyway in case you need to touch a `<DiscoveryProgress>` label.)

- [ ] **Step 4: Read the resolver and classifier once**

Read `scripts/pipeline/resolver.py` end-to-end and `scripts/pipeline/classifier.py` skim. Note that `_classify_and_enrich` is a closure with shared mutable state (`discovered`, `enriched`, `visited_canonical`, `aggregator_expanded`). The recursion will mutate the same closures.

---

## Task 1 — Add `depth` field to `DiscoveredUrl`

**Files:**
- Modify: `scripts/schemas.py`

- [ ] **Step 1: Write the failing test**

Append to `scripts/tests/pipeline/test_resolver.py`:

```python
def test_discovered_url_has_depth_field_default_zero():
    from schemas import DiscoveredUrl
    du = DiscoveredUrl(
        canonical_url="https://example.com",
        platform="other",
        account_type="other",
        destination_class="other",
        reason="rule:test",
    )
    assert du.depth == 0
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd scripts && python -m pytest tests/pipeline/test_resolver.py::test_discovered_url_has_depth_field_default_zero -v
```

Expected: FAIL with `AttributeError: 'DiscoveredUrl' object has no attribute 'depth'` (or similar).

- [ ] **Step 3: Add the field**

Modify `scripts/schemas.py` — locate the `DiscoveredUrl` class (around line 103) and add `depth`:

```python
class DiscoveredUrl(BaseModel):
    """A URL the resolver discovered + classified. One row per URL in the creator's network."""
    canonical_url: str
    platform: Platform
    account_type: AccountType
    destination_class: DestinationClass
    reason: str  # 'rule:X' | 'llm:high_confidence' | 'llm:cache_hit' | 'llm:low_confidence' | 'llm:timeout' | 'manual_add'
    depth: int = 0  # 0 = seed, 1 = surfaced from seed bio, 2 = surfaced from depth-1's bio, ...
```

- [ ] **Step 4: Run all tests to verify nothing else broke**

```bash
cd scripts && python -m pytest -q
```

Expected: 108 passed (was 107 + 1 new). No failures.

- [ ] **Step 5: Commit**

```bash
git add scripts/schemas.py scripts/tests/pipeline/test_resolver.py
git commit -m "feat(schemas): add depth field to DiscoveredUrl"
```

---

## Task 2 — Add `MAX_DEPTH` and `RECURSIVE_GEMINI` env-gated constants to resolver

**Files:**
- Modify: `scripts/pipeline/resolver.py`

- [ ] **Step 1: Write the failing test**

Create `scripts/tests/pipeline/test_resolver_recursive.py`:

```python
# scripts/tests/pipeline/test_resolver_recursive.py
import os
from unittest.mock import MagicMock, patch
import pytest

from schemas import InputContext, DiscoveryResultV2, TextMention, DiscoveredUrl
from pipeline.resolver import ResolverResult, resolve_seed
from pipeline.budget import BudgetTracker
from pipeline.classifier import Classification


def _mk_ctx(**overrides):
    base = dict(
        handle="alice", platform="instagram", display_name="Alice",
        bio="", follower_count=50000, avatar_url="https://cdn/a.jpg",
        external_urls=[], source_note="test",
    )
    base.update(overrides)
    return InputContext(**base)


def test_resolver_module_exposes_max_depth_constant():
    from pipeline import resolver
    assert hasattr(resolver, "MAX_DEPTH")
    assert isinstance(resolver.MAX_DEPTH, int)
    assert resolver.MAX_DEPTH >= 2  # must allow at least 2 hops by default


def test_resolver_module_exposes_recursive_gemini_constant():
    from pipeline import resolver
    assert hasattr(resolver, "RECURSIVE_GEMINI")
    assert isinstance(resolver.RECURSIVE_GEMINI, bool)
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd scripts && python -m pytest tests/pipeline/test_resolver_recursive.py -v
```

Expected: 2 failures with `AttributeError: module 'pipeline.resolver' has no attribute 'MAX_DEPTH'` (and `RECURSIVE_GEMINI`).

- [ ] **Step 3: Add the constants**

In `scripts/pipeline/resolver.py`, add `import os` at the top (with the other imports — there isn't one yet) and add the constants near the top of the module, just below the `_APIFY_COSTS` dict:

```python
import os
# ... existing imports ...

# Defensive max depth so a pathological cycle (visited_canonical bug) can't loop.
# Real-world creator networks rarely exceed depth 3.
MAX_DEPTH = int(os.getenv("DISCOVERY_MAX_DEPTH", "6"))

# When True, secondary profiles get a cheap Gemini Flash bio-mentions extraction
# in addition to their explicit external_urls. Default ON — the call is ~$0.001.
RECURSIVE_GEMINI = os.getenv("DISCOVERY_RECURSIVE_GEMINI", "1") == "1"
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd scripts && python -m pytest tests/pipeline/test_resolver_recursive.py -v
```

Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add scripts/pipeline/resolver.py scripts/tests/pipeline/test_resolver_recursive.py
git commit -m "feat(resolver): add MAX_DEPTH and RECURSIVE_GEMINI env-gated constants"
```

---

## Task 3 — Refactor `resolve_seed` to use `_expand(ctx, depth)` (no behaviour change)

**Files:**
- Modify: `scripts/pipeline/resolver.py`

This is a pure refactor — extract the existing seed-only logic into a `_expand` closure that takes `(ctx, depth)`. No recursion through enriched contexts yet (that's Task 4). Existing `test_resolver.py` tests must continue to pass.

- [ ] **Step 1: Run baseline tests**

```bash
cd scripts && python -m pytest tests/pipeline/test_resolver.py -v
```

Expected: 4 passed (the existing tests).

- [ ] **Step 2: Refactor**

In `scripts/pipeline/resolver.py`, restructure the body of `resolve_seed` (currently lines 156-247). Update `_classify_and_enrich` to take a `depth` parameter (with default 1 for backwards compat with the explicit calls below), set `DiscoveredUrl.depth=depth`, and introduce `_expand(ctx, depth)`:

```python
def resolve_seed(
    handle: str, platform_hint: str,
    supabase, apify_client: ApifyClient,
    budget: BudgetTracker,
    progress=None,
) -> ResolverResult:
    """Two-stage resolver for one seed.

    Stage A: fetch seed, debit budget.
    Stage B: classify + enrich every discovered URL via _expand recursion.
    Aggregators expanded once. Gemini canonicalization runs on seed only.
    Recursion terminates naturally when no new URLs/mentions surface; bounded
    defensively by MAX_DEPTH.

    progress: optional callable(pct, label) — invoked at stage boundaries so
    the UI can render a real progress bar. Decoupled from supabase to keep
    the resolver mockable in tests.
    """
    def _emit(pct: int, label: str) -> None:
        if progress is not None:
            progress(pct, label)

    # Stage A
    _emit(10, "Fetching profile")
    budget.debit(f"apify/{platform_hint}-scraper", _apify_cost(platform_hint))
    seed_ctx = fetch_seed(handle, platform_hint, apify_client)
    console.log(f"[cyan]Stage A: @{handle} on {platform_hint} — "
                f"bio={bool(seed_ctx.bio)} followers={seed_ctx.follower_count} "
                f"external={len(seed_ctx.external_urls)}[/cyan]")
    _emit(35, "Resolving links")

    discovered: list[DiscoveredUrl] = []
    enriched: dict[str, InputContext] = {}
    visited_canonical: set[str] = set()
    aggregator_expanded: set[str] = set()
    mapping_label_emitted = False

    def _classify_and_enrich(url: str, depth: int, is_aggregator_child: bool = False):
        """Classify URL, optionally enrich profile, record in discovered list.

        depth = the depth the URL itself sits at. Seed.external_urls items are
        depth=1. Aggregator children inherit depth from the aggregator + 1.
        """
        nonlocal mapping_label_emitted

        if depth > MAX_DEPTH:
            return  # defensive cap

        expanded = resolve_short_url(url)
        canon = canonicalize_url(expanded)
        if canon in visited_canonical:
            return
        visited_canonical.add(canon)

        cls: Classification = classify(canon, supabase=supabase)
        discovered.append(DiscoveredUrl(
            canonical_url=canon,
            platform=cls.platform,
            account_type=cls.account_type,
            destination_class=_destination_class_for(cls.account_type),
            reason=cls.reason,
            depth=depth,
        ))

        # Aggregator: expand one level (only if not already a child — no chaining)
        if cls.account_type == "link_in_bio" and not is_aggregator_child:
            if canon in aggregator_expanded:
                return
            aggregator_expanded.add(canon)
            children: list[str] = []
            if aggregators_linktree.is_linktree(canon):
                children = aggregators_linktree.resolve(canon)
            elif aggregators_beacons.is_beacons(canon):
                children = aggregators_beacons.resolve(canon)
            else:
                children = aggregators_custom.resolve(canon)
            for child in children:
                _classify_and_enrich(child, depth=depth + 1, is_aggregator_child=True)
            return

        # Profile: try to enrich (if budget allows + fetcher exists)
        if cls.account_type == "social" or cls.account_type == "monetization":
            enrich_cost = _apify_cost(cls.platform)
            if enrich_cost > 0 and not budget.can_afford(enrich_cost):
                return
            fetcher = _fetcher_for(cls.platform)
            if fetcher is None:
                return
            h = _handle_from_url(canon, cls.platform)
            if not h:
                return
            try:
                if enrich_cost > 0:
                    budget.debit(f"apify/{cls.platform}-scraper", enrich_cost)
                if cls.platform in ("instagram", "tiktok"):
                    ctx = fetcher(apify_client, h)
                else:
                    ctx = fetcher(h)
                enriched[canon] = ctx
            except (EmptyDatasetError, BudgetExhaustedError):
                return
            except Exception as e:
                console.log(f"[yellow]enrichment failed for {canon}: {e}[/yellow]")
                return

            # Recurse into the enriched ctx (Task 4 will populate this body)
            # Placeholder: pass

    def _expand(ctx: InputContext, depth: int) -> None:
        """Expand ctx's outbound links + bio mentions one hop further.

        ctx is at `depth`; its external_urls are processed at depth+1.
        """
        if depth >= MAX_DEPTH:
            return
        for url in ctx.external_urls:
            try:
                _classify_and_enrich(url, depth=depth + 1)
            except BudgetExhaustedError:
                return

    # Stage B for seed (depth 0 → expand to depth 1)
    try:
        _expand(seed_ctx, depth=0)
    except BudgetExhaustedError:
        pass

    # Gemini full pass (canonicalization + niche + text_mentions)
    _emit(70, "Analyzing")
    gemini_result = run_gemini_discovery_v2(seed_ctx)

    # Stage B for seed text_mentions (depth 1, since they're 1 hop from seed)
    for mention in gemini_result.text_mentions:
        synth = _synthesize_url(mention)
        if synth:
            try:
                _classify_and_enrich(synth, depth=1)
            except BudgetExhaustedError:
                break

    return ResolverResult(
        seed_context=seed_ctx,
        gemini_result=gemini_result,
        enriched_contexts=enriched,
        discovered_urls=discovered,
    )
```

- [ ] **Step 3: Run all existing tests to confirm no regression**

```bash
cd scripts && python -m pytest -q
```

Expected: all green (108 + 2 = 110 passed if you count Tasks 1 and 2).

- [ ] **Step 4: Commit**

```bash
git add scripts/pipeline/resolver.py
git commit -m "refactor(resolver): extract _expand(ctx, depth) closure, no behavior change"
```

---

## Task 4 — TDD: Recursive expansion of secondary external_urls

**Files:**
- Modify: `scripts/pipeline/resolver.py`
- Modify: `scripts/tests/pipeline/test_resolver_recursive.py`

This is the core feature: after enriching a profile, expand its external_urls one hop deeper.

- [ ] **Step 1: Write the failing test**

Append to `scripts/tests/pipeline/test_resolver_recursive.py`:

```python
@patch("pipeline.resolver.fetch_ig.fetch")
@patch("pipeline.resolver.run_gemini_discovery_v2")
@patch("pipeline.resolver.classify")
@patch("pipeline.resolver.fetch_seed")
def test_secondary_external_urls_are_followed(
    mock_fetch_seed, mock_classify, mock_gemini, mock_ig_fetch,
):
    """Kira-shaped case: TT seed has 1 external URL pointing to IG.
    The IG ctx has its own external URL pointing to OnlyFans.
    Both must land in discovered_urls."""

    mock_fetch_seed.return_value = _mk_ctx(
        handle="kira", platform="tiktok", bio="",
        external_urls=["https://instagram.com/kirapregiato"],
    )
    mock_ig_fetch.return_value = _mk_ctx(
        handle="kirapregiato", platform="instagram", bio="",
        external_urls=["https://onlyfans.com/kira"],
    )

    classifications = iter([
        Classification(platform="instagram", account_type="social",
                       confidence=1.0, reason="rule:instagram_social"),
        Classification(platform="onlyfans", account_type="monetization",
                       confidence=1.0, reason="rule:onlyfans_monetization"),
    ])
    mock_classify.side_effect = lambda *a, **kw: next(classifications)
    mock_gemini.return_value = DiscoveryResultV2(
        canonical_name="Kira", known_usernames=["kira"],
        display_name_variants=["Kira"], raw_reasoning="",
    )

    budget = BudgetTracker(cap_cents=1000)
    result = resolve_seed(
        handle="kira", platform_hint="tiktok",
        supabase=MagicMock(), apify_client=MagicMock(),
        budget=budget,
    )

    urls = [du.canonical_url for du in result.discovered_urls]
    assert any("instagram.com/kirapregiato" in u for u in urls), \
        f"depth-1 IG missing from {urls}"
    assert any("onlyfans.com/kira" in u for u in urls), \
        f"depth-2 OF missing from {urls} — recursion didn't fire"
    # Also: the IG ctx should be in enriched_contexts; OF should NOT be
    # (OF fetcher wasn't mocked — call would have errored if attempted, which is fine)
    assert any("instagram.com" in k for k in result.enriched_contexts.keys())
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd scripts && python -m pytest tests/pipeline/test_resolver_recursive.py::test_secondary_external_urls_are_followed -v
```

Expected: FAIL with `AssertionError: depth-2 OF missing from [...] — recursion didn't fire`. The IG URL will be present (Task 3 wired Stage B for seed externals); the OF URL won't because nothing recurses into the IG ctx yet.

- [ ] **Step 3: Wire the recursion**

In `scripts/pipeline/resolver.py`, inside `_classify_and_enrich`, after the enrichment block stores `ctx` in `enriched`, add the recursive `_expand` call:

```python
            try:
                if enrich_cost > 0:
                    budget.debit(f"apify/{cls.platform}-scraper", enrich_cost)
                if cls.platform in ("instagram", "tiktok"):
                    ctx = fetcher(apify_client, h)
                else:
                    ctx = fetcher(h)
                enriched[canon] = ctx
            except (EmptyDatasetError, BudgetExhaustedError):
                return
            except Exception as e:
                console.log(f"[yellow]enrichment failed for {canon}: {e}[/yellow]")
                return

            # NEW: recurse into the freshly-enriched ctx
            if not mapping_label_emitted:
                _emit(50, "Mapping secondary funnels")
                mapping_label_emitted = True
            try:
                _expand(ctx, depth=depth)
            except BudgetExhaustedError:
                return
```

Note: `_expand(ctx, depth=depth)` — the enriched ctx sits at the same depth as the URL we just classified (because the URL *is* the ctx's address). Inside `_expand`, the next level of links becomes `depth+1`.

- [ ] **Step 4: Run the test**

```bash
cd scripts && python -m pytest tests/pipeline/test_resolver_recursive.py::test_secondary_external_urls_are_followed -v
```

Expected: PASS.

- [ ] **Step 5: Run all tests to confirm no regression**

```bash
cd scripts && python -m pytest -q
```

Expected: all green.

- [ ] **Step 6: Commit**

```bash
git add scripts/pipeline/resolver.py scripts/tests/pipeline/test_resolver_recursive.py
git commit -m "feat(resolver): recurse into enriched secondaries' external_urls"
```

---

## Task 5 — TDD: Defensive `MAX_DEPTH` truncation

**Files:**
- Modify: `scripts/tests/pipeline/test_resolver_recursive.py`

The cap was added in Task 2 and the early-return in Task 3 — this task verifies it under a deliberately-deep mock chain.

- [ ] **Step 1: Write the failing test**

Append to `scripts/tests/pipeline/test_resolver_recursive.py`:

```python
@patch("pipeline.resolver.fetch_ig.fetch")
@patch("pipeline.resolver.run_gemini_discovery_v2")
@patch("pipeline.resolver.classify")
@patch("pipeline.resolver.fetch_seed")
def test_max_depth_defensive_cap_truncates_chain(
    mock_fetch_seed, mock_classify, mock_gemini, mock_ig_fetch,
    monkeypatch,
):
    """Force MAX_DEPTH=2; build a 5-deep IG chain. Confirm only depths 1-2 land."""
    monkeypatch.setattr("pipeline.resolver.MAX_DEPTH", 2)

    # Seed → IG-1 → IG-2 → IG-3 → IG-4 → IG-5; each IG points to the next.
    mock_fetch_seed.return_value = _mk_ctx(
        handle="seed", platform="instagram",
        external_urls=["https://instagram.com/ig1"],
    )

    # Each enriched IG returns the next link in the chain.
    chain = iter([
        _mk_ctx(handle="ig1", external_urls=["https://instagram.com/ig2"]),
        _mk_ctx(handle="ig2", external_urls=["https://instagram.com/ig3"]),
        _mk_ctx(handle="ig3", external_urls=["https://instagram.com/ig4"]),
        _mk_ctx(handle="ig4", external_urls=["https://instagram.com/ig5"]),
        _mk_ctx(handle="ig5", external_urls=[]),
    ])
    mock_ig_fetch.side_effect = lambda client, h: next(chain)

    mock_classify.return_value = Classification(
        platform="instagram", account_type="social",
        confidence=1.0, reason="rule:instagram_social",
    )
    mock_gemini.return_value = DiscoveryResultV2(
        canonical_name="Seed", known_usernames=["seed"],
        display_name_variants=["Seed"], raw_reasoning="",
    )

    budget = BudgetTracker(cap_cents=10000)
    result = resolve_seed(
        handle="seed", platform_hint="instagram",
        supabase=MagicMock(), apify_client=MagicMock(),
        budget=budget,
    )

    depths = sorted({du.depth for du in result.discovered_urls})
    # MAX_DEPTH=2 means depth 1 and 2 are recorded; depth 3+ should not appear.
    assert max(depths) <= 2, f"depths={depths} exceeded MAX_DEPTH=2"
    # And we DID reach depth 2 — otherwise the test isn't really verifying the cap.
    assert 2 in depths, f"never reached depth 2: depths={depths}"
```

- [ ] **Step 2: Run the test**

```bash
cd scripts && python -m pytest tests/pipeline/test_resolver_recursive.py::test_max_depth_defensive_cap_truncates_chain -v
```

Expected: PASS (Task 3's early-return already enforces the cap). If it fails, the cap implementation needs to be checked — recursion may be entering `_expand` with `depth==MAX_DEPTH`. Verify `_expand` returns early when `depth >= MAX_DEPTH` and `_classify_and_enrich` returns early when `depth > MAX_DEPTH`.

- [ ] **Step 3: Run all tests**

```bash
cd scripts && python -m pytest -q
```

Expected: all green.

- [ ] **Step 4: Commit**

```bash
git add scripts/tests/pipeline/test_resolver_recursive.py
git commit -m "test(resolver): defensive MAX_DEPTH cap truncates deep chains"
```

---

## Task 6 — TDD: Cycle dedup across depths

**Files:**
- Modify: `scripts/tests/pipeline/test_resolver_recursive.py`

The existing `visited_canonical` set already handles this. This test verifies that under recursion.

- [ ] **Step 1: Write the test**

Append:

```python
@patch("pipeline.resolver.fetch_ig.fetch")
@patch("pipeline.resolver.fetch_tt.fetch")
@patch("pipeline.resolver.run_gemini_discovery_v2")
@patch("pipeline.resolver.classify")
@patch("pipeline.resolver.fetch_seed")
def test_cycle_dedup_prevents_infinite_loop(
    mock_fetch_seed, mock_classify, mock_gemini, mock_tt_fetch, mock_ig_fetch,
):
    """A's bio links to B; B's bio links back to A. Verify each canonical_url
    appears exactly once and the resolver returns cleanly."""

    seed_url = "https://tiktok.com/@kira"
    ig_url = "https://instagram.com/kira"

    mock_fetch_seed.return_value = _mk_ctx(
        handle="kira", platform="tiktok",
        external_urls=[ig_url],
    )
    mock_ig_fetch.return_value = _mk_ctx(
        handle="kira", platform="instagram",
        external_urls=[seed_url],  # mentions back the TT seed
    )
    # TT fetcher is provided so attempting to re-enrich would succeed if
    # the cycle dedup failed. visited_canonical should prevent it.
    mock_tt_fetch.return_value = _mk_ctx(
        handle="kira", platform="tiktok",
        external_urls=[ig_url],
    )

    mock_classify.side_effect = lambda url, **kw: (
        Classification(platform="instagram", account_type="social",
                       confidence=1.0, reason="rule:instagram_social")
        if "instagram.com" in url else
        Classification(platform="tiktok", account_type="social",
                       confidence=1.0, reason="rule:tiktok_social")
    )
    mock_gemini.return_value = DiscoveryResultV2(
        canonical_name="Kira", known_usernames=["kira"],
        display_name_variants=["Kira"], raw_reasoning="",
    )

    budget = BudgetTracker(cap_cents=1000)
    result = resolve_seed(
        handle="kira", platform_hint="tiktok",
        supabase=MagicMock(), apify_client=MagicMock(),
        budget=budget,
    )

    canonicals = [du.canonical_url for du in result.discovered_urls]
    # Each URL appears at most once even though they cycle.
    assert len(canonicals) == len(set(canonicals)), \
        f"duplicate URLs in {canonicals} — cycle dedup failed"
    # IG was reached.
    assert any("instagram.com" in c for c in canonicals)
    # TT seed was NOT re-fetched as a discovered URL (it's the seed, not in discovered_urls)
    # but if cycle dedup failed, IG's reference to TT would have re-fetched and
    # enriched_contexts would have a TT entry. That'd indicate a leak.
    assert not any("tiktok.com" in k for k in result.enriched_contexts.keys()), \
        f"TT seed was re-fetched via cycle: {result.enriched_contexts}"
```

- [ ] **Step 2: Run the test**

```bash
cd scripts && python -m pytest tests/pipeline/test_resolver_recursive.py::test_cycle_dedup_prevents_infinite_loop -v
```

Expected: PASS (existing `visited_canonical` already protects). If FAIL — the seed URL isn't being added to `visited_canonical` before recursion sees it, which means cycles can leak. Fix by seeding `visited_canonical.add(canonicalize_url(seed_self_url))` at the top of `resolve_seed`.

Note: this MAY actually fail because the seed URL isn't currently added to `visited_canonical` — the current code only adds URLs that go through `_classify_and_enrich`. If the test fails, add seed dedup:

```python
    # Inside resolve_seed, just after seed_ctx is fetched:
    seed_canon = canonicalize_url(f"https://{_SEED_URL_HOSTS.get(platform_hint, '')}/{handle.lstrip('@')}")
    if seed_canon:
        visited_canonical.add(seed_canon)
```

But beware: `_SEED_URL_HOSTS` is in `discover_creator.py`, not the resolver. Either inline the host map (small) or import it. Inline is cleaner — copy the dict to `resolver.py` as a module-level constant `_SEED_HOST_FOR_PLATFORM`.

- [ ] **Step 3: If a fix was needed, re-run**

```bash
cd scripts && python -m pytest -q
```

Expected: all green.

- [ ] **Step 4: Commit**

```bash
git add scripts/pipeline/resolver.py scripts/tests/pipeline/test_resolver_recursive.py
git commit -m "test(resolver): cycle dedup verified across recursive depths"
```

(If you only added the test and no resolver changes, the commit message can be just `test(resolver): cycle dedup verified across recursive depths`.)

---

## Task 7 — TDD: Aggregator-no-chain rule still holds at depth ≥ 1

**Files:**
- Modify: `scripts/tests/pipeline/test_resolver_recursive.py`

The existing `is_aggregator_child` flag prevents linktree-from-beacons. Verify this under recursion.

- [ ] **Step 1: Write the test**

Append:

```python
@patch("pipeline.resolver.aggregators_linktree.resolve")
@patch("pipeline.resolver.aggregators_linktree.is_linktree")
@patch("pipeline.resolver.fetch_ig.fetch")
@patch("pipeline.resolver.run_gemini_discovery_v2")
@patch("pipeline.resolver.classify")
@patch("pipeline.resolver.fetch_seed")
def test_aggregator_chain_blocked_at_depth_one(
    mock_fetch_seed, mock_classify, mock_gemini, mock_ig_fetch,
    mock_is_linktree, mock_linktree_resolve,
):
    """Seed -> IG (depth 1) -> Linktree (depth 2) -> children include another Linktree.
    The second Linktree must NOT be re-expanded."""

    mock_fetch_seed.return_value = _mk_ctx(
        handle="seed", platform="instagram",
        external_urls=["https://instagram.com/secondary"],
    )
    mock_ig_fetch.return_value = _mk_ctx(
        handle="secondary", platform="instagram",
        external_urls=["https://linktr.ee/main"],
    )

    mock_is_linktree.side_effect = lambda u: "linktr.ee" in u
    mock_linktree_resolve.return_value = [
        "https://onlyfans.com/x",
        "https://linktr.ee/another",  # second linktree — must NOT be expanded
    ]

    classifications = iter([
        Classification(platform="instagram", account_type="social",
                       confidence=1.0, reason="rule:instagram_social"),
        Classification(platform="linktree", account_type="link_in_bio",
                       confidence=1.0, reason="rule:linktree_link_in_bio"),
        Classification(platform="onlyfans", account_type="monetization",
                       confidence=1.0, reason="rule:onlyfans_monetization"),
        Classification(platform="linktree", account_type="link_in_bio",
                       confidence=1.0, reason="rule:linktree_link_in_bio"),
    ])
    mock_classify.side_effect = lambda *a, **kw: next(classifications)
    mock_gemini.return_value = DiscoveryResultV2(
        canonical_name="Seed", known_usernames=["seed"],
        display_name_variants=["Seed"], raw_reasoning="",
    )

    budget = BudgetTracker(cap_cents=1000)
    result = resolve_seed(
        handle="seed", platform_hint="instagram",
        supabase=MagicMock(), apify_client=MagicMock(),
        budget=budget,
    )

    # linktree.resolve should be called exactly once (for the first linktree).
    assert mock_linktree_resolve.call_count == 1, \
        f"second linktree was re-expanded: {mock_linktree_resolve.call_count} calls"
    # All 4 URLs land: secondary IG, linktree-main, OF, linktree-another.
    assert len(result.discovered_urls) == 4
```

- [ ] **Step 2: Run the test**

```bash
cd scripts && python -m pytest tests/pipeline/test_resolver_recursive.py::test_aggregator_chain_blocked_at_depth_one -v
```

Expected: PASS (existing `is_aggregator_child` flag preserved through Task 3's refactor).

- [ ] **Step 3: Commit**

```bash
git add scripts/tests/pipeline/test_resolver_recursive.py
git commit -m "test(resolver): aggregator no-chain rule preserved under recursion"
```

---

## Task 8 — TDD: Budget exhaustion mid-recursion returns partial result

**Files:**
- Modify: `scripts/tests/pipeline/test_resolver_recursive.py`

- [ ] **Step 1: Write the test**

Append:

```python
@patch("pipeline.resolver.fetch_ig.fetch")
@patch("pipeline.resolver.run_gemini_discovery_v2")
@patch("pipeline.resolver.classify")
@patch("pipeline.resolver.fetch_seed")
def test_budget_exhaustion_during_recursion_returns_partial(
    mock_fetch_seed, mock_classify, mock_gemini, mock_ig_fetch,
):
    """Budget is tight: seed fetch (10c) + 1 IG enrich (10c) = 20c.
    Cap = 25c — third IG fetch must be budget-skipped, not crash."""

    mock_fetch_seed.return_value = _mk_ctx(
        handle="seed", platform="instagram",
        external_urls=["https://instagram.com/sec1"],
    )
    chain = iter([
        _mk_ctx(handle="sec1", platform="instagram",
                external_urls=["https://instagram.com/sec2"]),
        _mk_ctx(handle="sec2", platform="instagram",
                external_urls=["https://instagram.com/sec3"]),
    ])
    mock_ig_fetch.side_effect = lambda client, h: next(chain)
    mock_classify.return_value = Classification(
        platform="instagram", account_type="social",
        confidence=1.0, reason="rule:instagram_social",
    )
    mock_gemini.return_value = DiscoveryResultV2(
        canonical_name="Seed", known_usernames=["seed"],
        display_name_variants=["Seed"], raw_reasoning="",
    )

    budget = BudgetTracker(cap_cents=25)  # only seed + 1 enrich fits
    result = resolve_seed(
        handle="seed", platform_hint="instagram",
        supabase=MagicMock(), apify_client=MagicMock(),
        budget=budget,
    )

    # Resolver returned cleanly — no exception leaked.
    assert isinstance(result, ResolverResult)
    # We have at least sec1 (depth 1) recorded; possibly sec2 too if budget
    # allowed it, but never sec3.
    urls = [du.canonical_url for du in result.discovered_urls]
    assert any("sec1" in u for u in urls)
    assert not any("sec3" in u for u in urls), \
        f"sec3 should not have been fetched: {urls}"
```

- [ ] **Step 2: Run the test**

```bash
cd scripts && python -m pytest tests/pipeline/test_resolver_recursive.py::test_budget_exhaustion_during_recursion_returns_partial -v
```

Expected: PASS (Task 3's `try/except BudgetExhaustedError` already swallows mid-recursion exhaustion).

- [ ] **Step 3: Commit**

```bash
git add scripts/tests/pipeline/test_resolver_recursive.py
git commit -m "test(resolver): budget exhaustion during recursion returns partial cleanly"
```

---

## Task 9 — TDD: Empty bio + no externals on secondary = clean dead-end

**Files:**
- Modify: `scripts/tests/pipeline/test_resolver_recursive.py`

- [ ] **Step 1: Write the test**

Append:

```python
@patch("pipeline.resolver.fetch_of.fetch")
@patch("pipeline.resolver.run_gemini_discovery_v2")
@patch("pipeline.resolver.classify")
@patch("pipeline.resolver.fetch_seed")
def test_terminal_secondary_dead_ends_cleanly(
    mock_fetch_seed, mock_classify, mock_gemini, mock_of_fetch,
):
    """An OnlyFans secondary returns a ctx with no externals + no bio.
    Resolver must end the chain there with no error."""

    mock_fetch_seed.return_value = _mk_ctx(
        handle="seed", platform="instagram",
        external_urls=["https://onlyfans.com/seed"],
    )
    mock_of_fetch.return_value = _mk_ctx(
        handle="seed", platform="onlyfans",
        bio="", external_urls=[],  # truly terminal
    )
    mock_classify.return_value = Classification(
        platform="onlyfans", account_type="monetization",
        confidence=1.0, reason="rule:onlyfans_monetization",
    )
    mock_gemini.return_value = DiscoveryResultV2(
        canonical_name="Seed", known_usernames=["seed"],
        display_name_variants=["Seed"], raw_reasoning="",
    )

    budget = BudgetTracker(cap_cents=1000)
    result = resolve_seed(
        handle="seed", platform_hint="instagram",
        supabase=MagicMock(), apify_client=MagicMock(),
        budget=budget,
    )

    assert isinstance(result, ResolverResult)
    # OF was discovered (depth 1) and enriched, but nothing further.
    canonicals = [du.canonical_url for du in result.discovered_urls]
    assert len(canonicals) == 1
    assert "onlyfans.com/seed" in canonicals[0]
    assert any("onlyfans.com" in k for k in result.enriched_contexts.keys())
```

- [ ] **Step 2: Run the test**

```bash
cd scripts && python -m pytest tests/pipeline/test_resolver_recursive.py::test_terminal_secondary_dead_ends_cleanly -v
```

Expected: PASS.

- [ ] **Step 3: Commit**

```bash
git add scripts/tests/pipeline/test_resolver_recursive.py
git commit -m "test(resolver): terminal secondary (no externals, no bio) ends cleanly"
```

---

## Task 10 — Implement `run_gemini_bio_mentions(ctx)` extractor

**Files:**
- Modify: `scripts/discover_creator.py`
- Modify: `scripts/pipeline/resolver.py` (add wrapper at module level for test patching)

This is the cheap Gemini Flash call that extracts `@platform/handle` mentions from a secondary's bio.

- [ ] **Step 1: Add the function in `discover_creator.py`**

In `scripts/discover_creator.py`, near `run_gemini_discovery_v2` (around line 99), add:

```python
GEMINI_BIO_MENTIONS_SCHEMA = {
    "type": "object",
    "properties": {
        "mentions": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "platform": {"type": "string"},
                    "handle": {"type": "string"},
                },
                "required": ["platform", "handle"],
            },
        },
    },
    "required": ["mentions"],
}


def _build_bio_mentions_prompt(ctx: InputContext) -> str:
    bio = (ctx.bio or "").strip()
    return f"""
Extract every @platform/handle mention from this profile bio.
Return JSON: {{"mentions": [{{"platform": "tiktok"|"instagram"|"twitter"|"youtube"|"facebook"|"patreon"|"onlyfans"|"fanvue"|"linkedin", "handle": "..."}}]}}.
Only include mentions where both platform and handle are clearly stated or strongly implied.
Skip URLs (those are handled separately). Skip generic words like "DM me" with no handle.
If the bio is empty or contains no mentions, return {{"mentions": []}}.

Bio:
{bio}
""".strip()


@retry(
    stop=stop_after_attempt(2),  # cheap call, fewer retries than the big one
    wait=wait_exponential(multiplier=1, min=1, max=4),
    retry=retry_if_not_exception_type(ValidationError),
    reraise=True,
)
def run_gemini_bio_mentions(ctx: InputContext) -> list[TextMention]:
    """Lightweight Gemini Flash call: extract handle mentions from a secondary's bio.

    Returns [] on empty bio, validation error, or any failure. Never raises —
    a failed bio-mentions extraction must not crash discovery.
    """
    if not (ctx.bio or "").strip():
        return []

    try:
        genai.configure(api_key=get_gemini_key())
        model = genai.GenerativeModel("gemini-2.5-flash")
        resp = model.generate_content(
            _build_bio_mentions_prompt(ctx),
            generation_config=genai.GenerationConfig(
                response_mime_type="application/json",
                response_schema=GEMINI_BIO_MENTIONS_SCHEMA,
                max_output_tokens=256,
            ),
        )
        data = json.loads(resp.text)
        out: list[TextMention] = []
        for m in data.get("mentions", []):
            try:
                out.append(TextMention(
                    platform=m["platform"],
                    handle=m["handle"],
                    source="enriched_bio",
                ))
            except (ValidationError, KeyError):
                continue  # skip individual bad rows
        return out
    except Exception as e:
        console.log(f"[yellow]bio mentions extraction failed: {e}[/yellow]")
        return []
```

Make sure `TextMention` is imported in `discover_creator.py`. Check the imports at the top of the file — if it isn't already imported via `from schemas import ...`, add it.

- [ ] **Step 2: Add the wrapper in `pipeline/resolver.py`**

In `scripts/pipeline/resolver.py`, alongside the existing `run_gemini_discovery_v2` wrapper (around line 105), add:

```python
def run_gemini_bio_mentions(ctx: InputContext) -> list[TextMention]:
    """Cheap Gemini Flash bio-mentions extraction.

    Re-exported here so tests can patch at this import site, matching the
    pattern used for run_gemini_discovery_v2.
    """
    from discover_creator import run_gemini_bio_mentions as _impl
    return _impl(ctx)
```

- [ ] **Step 3: Write a unit test**

Append to `scripts/tests/pipeline/test_resolver_recursive.py`:

```python
def test_run_gemini_bio_mentions_returns_empty_for_empty_bio():
    """The function under unit test, not via resolver."""
    from discover_creator import run_gemini_bio_mentions
    ctx = _mk_ctx(bio="")
    # Should short-circuit without calling Gemini at all.
    assert run_gemini_bio_mentions(ctx) == []
```

- [ ] **Step 4: Run tests**

```bash
cd scripts && python -m pytest tests/pipeline/test_resolver_recursive.py::test_run_gemini_bio_mentions_returns_empty_for_empty_bio -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add scripts/discover_creator.py scripts/pipeline/resolver.py scripts/tests/pipeline/test_resolver_recursive.py
git commit -m "feat(discovery): add run_gemini_bio_mentions for cheap secondary bio extraction"
```

---

## Task 11 — TDD: Wire bio-mentions into recursion (flag ON)

**Files:**
- Modify: `scripts/pipeline/resolver.py`
- Modify: `scripts/tests/pipeline/test_resolver_recursive.py`

- [ ] **Step 1: Write the failing test**

Append:

```python
@patch("pipeline.resolver.run_gemini_bio_mentions")
@patch("pipeline.resolver.fetch_ig.fetch")
@patch("pipeline.resolver.run_gemini_discovery_v2")
@patch("pipeline.resolver.classify")
@patch("pipeline.resolver.fetch_seed")
def test_secondary_bio_mentions_followed_when_flag_on(
    mock_fetch_seed, mock_classify, mock_gemini_seed, mock_ig_fetch,
    mock_gemini_bio,
):
    """Secondary IG ctx has bio prose with a @tiktok mention but NO clickable
    external_url. With RECURSIVE_GEMINI=True (default), the mention is followed."""

    mock_fetch_seed.return_value = _mk_ctx(
        handle="seed", platform="instagram",
        external_urls=["https://instagram.com/sec"],
    )
    mock_ig_fetch.return_value = _mk_ctx(
        handle="sec", platform="instagram",
        bio="also follow my tiktok @sec_tt",
        external_urls=[],  # NO clickable link — only bio prose
    )
    # Bio mentions extractor returns the implied TT handle.
    mock_gemini_bio.return_value = [
        TextMention(platform="tiktok", handle="sec_tt", source="enriched_bio"),
    ]
    classifications = iter([
        Classification(platform="instagram", account_type="social",
                       confidence=1.0, reason="rule:instagram_social"),
        Classification(platform="tiktok", account_type="social",
                       confidence=1.0, reason="rule:tiktok_social"),
    ])
    mock_classify.side_effect = lambda *a, **kw: next(classifications)
    mock_gemini_seed.return_value = DiscoveryResultV2(
        canonical_name="Seed", known_usernames=["seed"],
        display_name_variants=["Seed"], raw_reasoning="",
    )

    budget = BudgetTracker(cap_cents=1000)
    result = resolve_seed(
        handle="seed", platform_hint="instagram",
        supabase=MagicMock(), apify_client=MagicMock(),
        budget=budget,
    )

    urls = [du.canonical_url for du in result.discovered_urls]
    assert any("tiktok.com/@sec_tt" in u for u in urls), \
        f"bio-mention TT not followed: {urls}"
    # Bio extractor was called for the secondary (depth 1).
    assert mock_gemini_bio.called
```

- [ ] **Step 2: Run the test**

```bash
cd scripts && python -m pytest tests/pipeline/test_resolver_recursive.py::test_secondary_bio_mentions_followed_when_flag_on -v
```

Expected: FAIL — `_expand` doesn't yet call `run_gemini_bio_mentions` for depth ≥ 1.

- [ ] **Step 3: Wire the bio-mentions call into `_expand`**

In `scripts/pipeline/resolver.py`, update `_expand`:

```python
    def _expand(ctx: InputContext, depth: int) -> None:
        """Expand ctx's outbound links + bio mentions one hop further.

        ctx is at `depth`; its external_urls are processed at depth+1. Bio
        mentions (cheap Gemini extraction) are also processed at depth+1
        when RECURSIVE_GEMINI is on. The seed (depth 0) skips bio extraction
        because the full Gemini canonicalization call covers it.
        """
        if depth >= MAX_DEPTH:
            return
        for url in ctx.external_urls:
            try:
                _classify_and_enrich(url, depth=depth + 1)
            except BudgetExhaustedError:
                return
        if depth >= 1 and RECURSIVE_GEMINI:
            mentions = run_gemini_bio_mentions(ctx)
            for m in mentions:
                synth = _synthesize_url(m)
                if synth:
                    try:
                        _classify_and_enrich(synth, depth=depth + 1)
                    except BudgetExhaustedError:
                        return
```

- [ ] **Step 4: Run the test**

```bash
cd scripts && python -m pytest tests/pipeline/test_resolver_recursive.py::test_secondary_bio_mentions_followed_when_flag_on -v
```

Expected: PASS.

- [ ] **Step 5: Run all tests**

```bash
cd scripts && python -m pytest -q
```

Expected: all green.

- [ ] **Step 6: Commit**

```bash
git add scripts/pipeline/resolver.py scripts/tests/pipeline/test_resolver_recursive.py
git commit -m "feat(resolver): follow bio mentions on secondaries (RECURSIVE_GEMINI default on)"
```

---

## Task 12 — TDD: `RECURSIVE_GEMINI=0` disables bio-mentions

**Files:**
- Modify: `scripts/tests/pipeline/test_resolver_recursive.py`

- [ ] **Step 1: Write the test**

Append:

```python
@patch("pipeline.resolver.run_gemini_bio_mentions")
@patch("pipeline.resolver.fetch_ig.fetch")
@patch("pipeline.resolver.run_gemini_discovery_v2")
@patch("pipeline.resolver.classify")
@patch("pipeline.resolver.fetch_seed")
def test_recursive_gemini_disabled_skips_bio_mentions(
    mock_fetch_seed, mock_classify, mock_gemini_seed, mock_ig_fetch,
    mock_gemini_bio, monkeypatch,
):
    """With RECURSIVE_GEMINI=False, secondary external_urls still expand
    but bio-mentions extraction is skipped."""
    monkeypatch.setattr("pipeline.resolver.RECURSIVE_GEMINI", False)

    mock_fetch_seed.return_value = _mk_ctx(
        handle="seed", platform="instagram",
        external_urls=["https://instagram.com/sec"],
    )
    mock_ig_fetch.return_value = _mk_ctx(
        handle="sec", platform="instagram",
        bio="also @sec_tt on tiktok",
        external_urls=[],
    )
    mock_classify.return_value = Classification(
        platform="instagram", account_type="social",
        confidence=1.0, reason="rule:instagram_social",
    )
    mock_gemini_seed.return_value = DiscoveryResultV2(
        canonical_name="Seed", known_usernames=["seed"],
        display_name_variants=["Seed"], raw_reasoning="",
    )

    budget = BudgetTracker(cap_cents=1000)
    result = resolve_seed(
        handle="seed", platform_hint="instagram",
        supabase=MagicMock(), apify_client=MagicMock(),
        budget=budget,
    )

    # Bio extractor must NOT be called when flag is off.
    assert not mock_gemini_bio.called, "bio extractor called despite flag=off"
    # The secondary IG itself still landed.
    urls = [du.canonical_url for du in result.discovered_urls]
    assert any("instagram.com/sec" in u for u in urls)
    # The bio-implied TT handle did NOT land (only externals were followed).
    assert not any("sec_tt" in u for u in urls)
```

- [ ] **Step 2: Run the test**

```bash
cd scripts && python -m pytest tests/pipeline/test_resolver_recursive.py::test_recursive_gemini_disabled_skips_bio_mentions -v
```

Expected: PASS.

- [ ] **Step 3: Commit**

```bash
git add scripts/tests/pipeline/test_resolver_recursive.py
git commit -m "test(resolver): RECURSIVE_GEMINI=0 disables bio-mentions extraction"
```

---

## Task 13 — TDD: Depth-aware confidence drop

**Files:**
- Modify: `scripts/pipeline/resolver.py` (add `_confidence_at_depth`)
- Modify: `scripts/discover_creator.py` (`_commit_v2` reads `DiscoveredUrl.depth`)
- Modify: `scripts/tests/pipeline/test_resolver_recursive.py`

The seed is `1.0`. Depth 1 (existing behaviour) is `0.9`. Drop linearly at `0.05` per hop, floor at `0.5`.

- [ ] **Step 1: Write the failing unit test for the helper**

Append:

```python
def test_confidence_at_depth_formula():
    from pipeline.resolver import _confidence_at_depth
    assert _confidence_at_depth(0) == 1.0   # seed
    assert _confidence_at_depth(1) == 0.9   # matches existing hardcoded value
    assert abs(_confidence_at_depth(2) - 0.85) < 1e-9
    assert abs(_confidence_at_depth(5) - 0.7) < 1e-9
    assert _confidence_at_depth(20) == 0.5  # floor
```

- [ ] **Step 2: Run the test**

```bash
cd scripts && python -m pytest tests/pipeline/test_resolver_recursive.py::test_confidence_at_depth_formula -v
```

Expected: FAIL (`_confidence_at_depth` doesn't exist).

- [ ] **Step 3: Implement the helper in `resolver.py`**

In `scripts/pipeline/resolver.py`, add near the other module-level helpers (after `_apify_cost`):

```python
def _confidence_at_depth(depth: int) -> float:
    """Discovery confidence by hop distance from the seed.

    depth 0 = seed (1.0), depth 1 = direct (0.9 — preserves existing behaviour),
    drops 0.05 per hop, floors at 0.5.
    """
    if depth <= 0:
        return 1.0
    return max(0.5, 0.9 - 0.05 * (depth - 1))
```

- [ ] **Step 4: Run the helper test**

```bash
cd scripts && python -m pytest tests/pipeline/test_resolver_recursive.py::test_confidence_at_depth_formula -v
```

Expected: PASS.

- [ ] **Step 5: Wire it into `_commit_v2`**

In `scripts/discover_creator.py`, update the loop in `_commit_v2` that builds enriched-secondary `accounts` (around line 231):

```python
    # Build a depth lookup once.
    depth_for_canon = {du.canonical_url: du.depth for du in result.discovered_urls}

    for canon, ctx in result.enriched_contexts.items():
        d = depth_for_canon.get(canon, 1)
        from pipeline.resolver import _confidence_at_depth  # local import to avoid cycle
        accounts.append({
            "platform": ctx.platform,
            "handle": ctx.handle,
            "url": canon,
            "display_name": ctx.display_name,
            "bio": ctx.bio,
            "follower_count": ctx.follower_count,
            "account_type": _classify_account_type_for(ctx.platform, result.discovered_urls, canon),
            "is_primary": False,
            "discovery_confidence": _confidence_at_depth(d),
            "reasoning": ctx.source_note,
        })
```

And similarly for the unenriched-discovered loop just below it (the one that handles novel platforms / link-in-bio aggregators / budget-skipped profiles):

```python
    for du in result.discovered_urls:
        if du.canonical_url in result.enriched_contexts:
            continue
        accounts.append({
            "platform": du.platform,
            "handle": _synthesize_handle_from_url(du.canonical_url),
            "url": du.canonical_url,
            "display_name": None,
            "bio": None,
            "follower_count": None,
            "account_type": du.account_type,
            "is_primary": False,
            "discovery_confidence": _confidence_at_depth(du.depth),  # was previously hardcoded
            ...
```

(Keep the rest of that dict unchanged. Only `discovery_confidence` changes.)

- [ ] **Step 6: Add a commit-side integration test**

Append to `scripts/tests/pipeline/test_resolver_recursive.py`:

```python
def test_depth_propagates_into_discovered_urls():
    """End-to-end: a depth-2 URL must have depth=2 on its DiscoveredUrl row."""
    with patch("pipeline.resolver.fetch_ig.fetch") as mock_ig, \
         patch("pipeline.resolver.run_gemini_discovery_v2") as mock_gemini, \
         patch("pipeline.resolver.classify") as mock_classify, \
         patch("pipeline.resolver.fetch_seed") as mock_fetch_seed:

        mock_fetch_seed.return_value = _mk_ctx(
            handle="seed", platform="instagram",
            external_urls=["https://instagram.com/sec"],
        )
        mock_ig.return_value = _mk_ctx(
            handle="sec", platform="instagram",
            external_urls=["https://onlyfans.com/sec"],
        )
        classifications = iter([
            Classification(platform="instagram", account_type="social",
                           confidence=1.0, reason="rule:instagram_social"),
            Classification(platform="onlyfans", account_type="monetization",
                           confidence=1.0, reason="rule:onlyfans_monetization"),
        ])
        mock_classify.side_effect = lambda *a, **kw: next(classifications)
        mock_gemini.return_value = DiscoveryResultV2(
            canonical_name="Seed", known_usernames=["seed"],
            display_name_variants=["Seed"], raw_reasoning="",
        )

        budget = BudgetTracker(cap_cents=1000)
        result = resolve_seed(
            handle="seed", platform_hint="instagram",
            supabase=MagicMock(), apify_client=MagicMock(),
            budget=budget,
        )

        by_url = {du.canonical_url: du for du in result.discovered_urls}
        ig = next(du for url, du in by_url.items() if "instagram.com/sec" in url)
        of = next(du for url, du in by_url.items() if "onlyfans.com" in url)
        assert ig.depth == 1, f"IG should be depth 1, got {ig.depth}"
        assert of.depth == 2, f"OF should be depth 2, got {of.depth}"
```

- [ ] **Step 7: Run tests**

```bash
cd scripts && python -m pytest -q
```

Expected: all green.

- [ ] **Step 8: Commit**

```bash
git add scripts/pipeline/resolver.py scripts/discover_creator.py scripts/tests/pipeline/test_resolver_recursive.py
git commit -m "feat(resolver): depth-aware discovery_confidence (0.9 → 0.5 floor)"
```

---

## Task 14 — Automated end-to-end smoke test (Kira-shaped fixture)

**Files:**
- Modify: `scripts/tests/pipeline/test_resolver_recursive.py`

This is the synthetic Kira case: TT seed → IG (depth 1) → linktree (depth 2) → [OF, telegram_channel] (depth 3). All four URLs must surface, with correct depths and account_types.

- [ ] **Step 1: Write the test**

Append:

```python
@patch("pipeline.resolver.aggregators_linktree.resolve")
@patch("pipeline.resolver.aggregators_linktree.is_linktree")
@patch("pipeline.resolver.fetch_ig.fetch")
@patch("pipeline.resolver.run_gemini_bio_mentions")
@patch("pipeline.resolver.run_gemini_discovery_v2")
@patch("pipeline.resolver.classify")
@patch("pipeline.resolver.fetch_seed")
def test_kira_shaped_full_funnel_resolution(
    mock_fetch_seed, mock_classify, mock_gemini_seed, mock_gemini_bio,
    mock_ig_fetch, mock_is_linktree, mock_linktree_resolve,
):
    """End-to-end synthetic of the failing Kira case from PROJECT_STATE.

    Seed: TT @kira (no externals, no bio links).
    Gemini text_mentions: @kirapregiato on instagram.
    IG profile: aggregator URL https://tapforallmylinks.com/kira.
    Aggregator children: [OF, telegram_channel].
    Expected: all 4 destinations recorded; OF + telegram are terminal.
    """
    mock_fetch_seed.return_value = _mk_ctx(
        handle="kira", platform="tiktok", bio="more on @kirapregiato",
        external_urls=[],
    )
    mock_ig_fetch.return_value = _mk_ctx(
        handle="kirapregiato", platform="instagram",
        bio="", external_urls=["https://tapforallmylinks.com/kira"],
    )
    mock_is_linktree.return_value = False  # not linktr.ee — falls through to custom_domain

    # custom_domain.resolve is the actual aggregator we hit; patch THAT instead.
    with patch("pipeline.resolver.aggregators_custom.resolve") as mock_custom_resolve:
        mock_custom_resolve.return_value = [
            "https://onlyfans.com/kira",
            "https://t.me/kirachannel",
        ]

        classifications = iter([
            # IG (from seed text mention)
            Classification(platform="instagram", account_type="social",
                           confidence=1.0, reason="rule:instagram_social"),
            # tapforallmylinks aggregator (from IG external_urls)
            Classification(platform="custom_domain", account_type="link_in_bio",
                           confidence=1.0, reason="rule:custom_domain_aggregator"),
            # OF child
            Classification(platform="onlyfans", account_type="monetization",
                           confidence=1.0, reason="rule:onlyfans_monetization"),
            # Telegram child
            Classification(platform="telegram_channel", account_type="messaging",
                           confidence=1.0, reason="rule:telegram_messaging"),
        ])
        mock_classify.side_effect = lambda *a, **kw: next(classifications)
        mock_gemini_seed.return_value = DiscoveryResultV2(
            canonical_name="Kira", known_usernames=["kira", "kirapregiato"],
            display_name_variants=["Kira"],
            text_mentions=[TextMention(platform="instagram", handle="kirapregiato")],
            raw_reasoning="",
        )
        mock_gemini_bio.return_value = []  # IG bio empty, no mentions

        budget = BudgetTracker(cap_cents=1000)
        result = resolve_seed(
            handle="kira", platform_hint="tiktok",
            supabase=MagicMock(), apify_client=MagicMock(),
            budget=budget,
        )

    by_platform = {du.platform: du for du in result.discovered_urls}
    assert "instagram" in by_platform
    assert "custom_domain" in by_platform
    assert "onlyfans" in by_platform
    assert "telegram_channel" in by_platform

    # Depth check: IG depth=1 (text_mention from seed), aggregator depth=2,
    # children depth=3.
    assert by_platform["instagram"].depth == 1
    assert by_platform["custom_domain"].depth == 2
    assert by_platform["onlyfans"].depth == 3
    assert by_platform["telegram_channel"].depth == 3

    # IG was enriched (we mocked fetch_ig.fetch); aggregator + terminals were not.
    assert any("instagram.com/kirapregiato" in k
               for k in result.enriched_contexts.keys())
    # OF + telegram are messaging/monetization terminals — not enriched in this test
    # (no fetcher mocked for telegram; OF fetcher available but not hit because the
    # aggregator children already populated discovered_urls).
```

- [ ] **Step 2: Run the test**

```bash
cd scripts && python -m pytest tests/pipeline/test_resolver_recursive.py::test_kira_shaped_full_funnel_resolution -v
```

Expected: PASS — this exercises the full chain end-to-end with mocks.

- [ ] **Step 3: Run the full suite**

```bash
cd scripts && python -m pytest -q
```

Expected: all green.

- [ ] **Step 4: Commit**

```bash
git add scripts/tests/pipeline/test_resolver_recursive.py
git commit -m "test(resolver): Kira-shaped end-to-end recursive resolution"
```

---

## Task 15 — Live smoke test on Kira

**Files:** none (operational)

This is the real-world verification. The automated tests prove the logic; this proves the integration with live Apify + Gemini.

- [ ] **Step 1: Confirm the worker is running fresh code**

```bash
bash scripts/worker_ctl.sh restart
bash scripts/worker_ctl.sh status
```

Expected: status shows the worker is alive. (`worker_ctl.sh restart` triggers SIGTERM and lets launchd KeepAlive respawn the process with the latest code — see PROJECT_STATE §15 sync-13 notes.)

- [ ] **Step 2: Re-run discovery for Kira**

In the dev UI: navigate to `/creators/kira-p` (or whatever Kira's slug is — check via the `/creators` index). Click **Re-run Discovery**. Confirm the toast acknowledges the run.

- [ ] **Step 3: Watch the worker log**

```bash
tail -f ~/Library/Logs/the-hub-worker.log
```

Look for the stage labels in order:
- `Fetching profile`
- `Resolving links`
- `Mapping secondary funnels` ← NEW
- `Analyzing`
- `Saving`
- (run completes)

If `Mapping secondary funnels` does NOT appear, the recursion never enriched a secondary. Possible causes: Kira's seed has no fetched-fetchable externals, or the Apify call failed. Check the log for errors.

- [ ] **Step 4: Verify new accounts landed**

Check the live DB via Supabase SQL editor or psql (`/opt/homebrew/opt/libpq/bin/psql`):

```sql
SELECT p.platform, p.handle, p.url, p.discovery_confidence, p.discovery_reason
FROM profiles p
JOIN creators c ON c.id = p.creator_id
WHERE c.canonical_name ILIKE '%kira%'
  AND p.is_active = true
ORDER BY p.discovery_confidence DESC;
```

Expected: profiles for OnlyFans, Telegram (or whatever's actually on her IG aggregator) appear with `discovery_confidence` values lower than 0.9 (depth ≥ 2 → 0.85 or below).

- [ ] **Step 5: Verify the HQ page**

Navigate to Kira's HQ page in the browser. The new accounts should render under the appropriate platform sections.

If anything's off (missing accounts, wrong platform sections, bad URLs), don't fix here — note it, finish Task 16 (sync state), and open follow-up issues.

- [ ] **Step 6: Document the smoke result**

Add a section to `06-Sessions/<today>.md` titled "Recursive funnel resolution — live smoke" with: which creator, which new accounts surfaced, total Apify spend (visible via `bulk_imports.cost_apify_cents`), any anomalies.

---

## Task 16 — Sync project state

**Files:**
- Modify: `PROJECT_STATE.md` (Decisions Log + §14 build order if applicable)
- Modify: `06-Sessions/<today>.md`

- [ ] **Step 1: Run the sync skill**

In the Claude Code session: invoke `/sync-project-state`.

- [ ] **Step 2: Verify the commit and push happened**

```bash
git log --oneline -5
git status
```

Expected: a `chore: sync project state` commit at HEAD; tree clean; branch up to date with origin.

- [ ] **Step 3: Final pytest run**

```bash
cd scripts && python -m pytest -q
```

Expected: all green. Record the new total in the session note.

- [ ] **Step 4: Final tsc check**

```bash
cd "/Users/simon/OS/Living VAULT/Content OS/The Hub" && npx tsc --noEmit
```

Expected: 0 errors.

---

## Cost / Risk Analysis

**Apify cost per discovery (estimated):**

| Scenario | Current (v2 SP1) | Recursive |
|---|---|---|
| Best case (no secondaries) | ~$0.10 | ~$0.10 |
| Typical (2-3 secondaries) | ~$0.30 | ~$0.30 |
| Heavy (5+ secondaries with their own aggregators) | ~$0.50 | ~$0.50 |

Net cost delta: **~$0.001 per secondary** for the bio-mentions Gemini Flash call. The Apify side is unchanged because secondary profile fetches already happen in v2 SP1 — we're just *also using* the bio + external_urls we already pulled.

**Risk: runaway expansion.** Quadruple-bounded:
1. `MAX_DEPTH=6` — defensive cap at the URL classification step
2. `BudgetTracker` — caps total Apify spend per discovery run
3. `visited_canonical` — dedup across all depths, prevents cycles
4. Aggregator no-chain rule — `is_aggregator_child=True` prevents Linktree-from-Beacons

No new failure modes vs. current pipeline.

---

## What this does NOT do

- Post scraping (50–100 recent posts per profile for outliers/trends) → Phase 2 §14 #9, separate scheduled worker
- Re-scraping existing profiles' bios → only runs at discovery time / Re-run Discovery; bio-refresh cadence is a separate question
- Cross-creator funnel inference → `funnel-inference` runtime agent, Phase 4 (§16)
- New fetchers (Snapchat, X, FB beyond the SP1 stub) → SP1.1 follow-up

---

## Self-Review Checklist

- [x] Each task has 2–5-minute steps with explicit commands and code blocks
- [x] No "TBD" / "TODO" / "implement later" placeholders
- [x] Type names consistent (`DiscoveredUrl`, `_confidence_at_depth`, `RECURSIVE_GEMINI`, `MAX_DEPTH`)
- [x] Patch import paths consistent (`pipeline.resolver.run_gemini_discovery_v2`, `pipeline.resolver.run_gemini_bio_mentions`, `pipeline.resolver.fetch_ig.fetch`)
- [x] Existing 4 tests in `test_resolver.py` continue to pass through the refactor
- [x] All open questions resolved per user decisions: `RECURSIVE_GEMINI=ON` default, linear confidence drop, automated smoke before manual smoke
- [x] Termination is natural (no externals + no bio mentions = dead-end); MAX_DEPTH is defensive only
