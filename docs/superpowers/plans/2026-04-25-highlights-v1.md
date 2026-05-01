# Highlights v1 (Funnel-only) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Surface CTAs that IG creators park in story highlights — link stickers + caption-mentioned handles — and feed them through the existing `_classify_and_enrich` recursion. Closes the funnel-completeness gap that bio + external_urls scraping leaves open.

**Architecture:** Add a third source to `_expand(ctx, depth)` — for `ctx.platform == "instagram"` at `depth >= 1`, scrape highlights via `apify/instagram-scraper` `resultsType: "stories"`, parse `story_link_stickers[].url` and `mentions[]`, then dispatch each link through `_classify_and_enrich(..., depth+1)`. Triple-bounded against runaway: existing `visited_canonical` + `BudgetTracker` + new `DISCOVERY_HIGHLIGHTS_ENABLED` kill switch. No new tables, no UI changes, no schema migration.

**Tech Stack:** Python 3.11+, Pydantic v2, pytest (existing 122 tests must stay green), `apify/instagram-scraper` actor in `stories` mode, existing tenacity retry pattern. The `discover_creator.py` `_commit_v2` path is untouched — highlights-surfaced URLs flow through the existing `discovered_urls → commit_discovery_result → profile_destination_links / profiles` plumbing.

---

## File Structure

| File | Responsibility | Action |
|---|---|---|
| `scripts/schemas.py` | Pydantic models. Add `HighlightLink` (url, source, source_text). | Modify |
| `scripts/fetchers/instagram_highlights.py` | `fetch_highlights(client, handle) -> list[HighlightLink]`. Apify call + parser, tenacity retry, returns `[]` on any error. | Create |
| `scripts/pipeline/resolver.py` | New `HIGHLIGHTS_ENABLED` constant + `HIGHLIGHTS_COST_CENTS` + `fetch_highlights` wrapper at module level (so tests can patch `pipeline.resolver.fetch_highlights`). Wire highlights branch into `_expand` for IG depth ≥ 1. | Modify |
| `scripts/tests/fetchers/test_instagram_highlights.py` | Unit tests for the fetcher (mock the Apify client). | Create |
| `scripts/tests/pipeline/test_resolver_recursive.py` | Integration tests for the resolver wiring. Existing tests must keep passing. | Modify |

---

## Pre-Execution Notes for the Worker

1. The pytest baseline must be **122 passing** before you start (the recursive-funnel work landed there). Run `cd scripts && python -m pytest -q` as Task 0 step 2 and record the exact number — if it differs, use that as your baseline.
2. **Mock pattern:** the resolver imports `fetch_highlights` from `fetchers.instagram_highlights` as a re-exported wrapper at module scope, exactly like `run_gemini_bio_mentions`. Tests patch `pipeline.resolver.fetch_highlights` (NOT `fetchers.instagram_highlights.fetch_highlights`).
3. The `_mk_ctx` helper in `test_resolver_recursive.py` is the canonical fixture — extend it if needed but don't replace it. The `Classification` import for stubbing the classifier is already there.
4. The Apify call shape mirrors the existing `instagram.py` `_call_actor` exactly. The only differences: `resultsType: "stories"` and `addParentData: true`. Reuse `is_transient_apify_error` and `EmptyDatasetError` from `fetchers.base`.
5. Don't break `MagicMock()` supabase or `MagicMock()` apify_client patterns. The fetcher must accept any client-shaped object as long as the test mocks `client.actor(...).call(...)` and `client.dataset(...).list_items()`.
6. The smoke test (Task 9) is a build gate. If `apify/instagram-scraper` `stories` mode does not return pinned highlights (only live stories), STOP and escalate. Don't invent a workaround — the design doc has a documented fallback (`louisdeconinck/instagram-highlights-scraper`) that needs Simon's call.

---

## Task 0 — Pre-flight

**Files:** none

- [ ] **Step 1: Confirm git state**

```bash
git status
git branch --show-current
```

Expected: tree clean (or only `.tmp/` untracked); branch is `phase-2-discovery-v2` (or whichever branch the recursive-funnel work landed on). If you want isolation, `git checkout -b phase-2-highlights-v1`. Otherwise stay on the current branch — the commits will be small and reviewable.

- [ ] **Step 2: Confirm pytest baseline**

```bash
cd scripts && python -m pytest -q
```

Expected: `122 passed` (or whatever the recursive-funnel work left it at). Record the number — every subsequent task that adds tests must show baseline+N passing.

- [ ] **Step 3: Confirm tsc baseline**

```bash
cd "/Users/simon/OS/Living VAULT/Content OS/The Hub" && npx tsc --noEmit
```

Expected: 0 errors. (No TS changes are planned — this is a sanity check.)

- [ ] **Step 4: Read the resolver and its existing tests**

Read `scripts/pipeline/resolver.py` end-to-end (focus on `_expand`, `_classify_and_enrich`, the existing `run_gemini_bio_mentions` wrapper). Read `scripts/tests/pipeline/test_resolver_recursive.py` skim — note the `_mk_ctx` fixture and the `@patch("pipeline.resolver.run_gemini_bio_mentions")` pattern. The new tests follow the same shape.

---

## Task 1 — Add `HighlightLink` Pydantic model

**Files:**
- Modify: `scripts/schemas.py`
- Modify: `scripts/tests/test_schemas.py` (or create if it doesn't yet have a HighlightLink section)

- [ ] **Step 1: Write the failing test**

Append to `scripts/tests/test_schemas.py`:

```python
class TestHighlightLink:
    def test_link_sticker_minimal(self):
        from schemas import HighlightLink
        link = HighlightLink(
            url="https://onlyfans.com/kira",
            source="highlight_link_sticker",
        )
        assert link.url == "https://onlyfans.com/kira"
        assert link.source == "highlight_link_sticker"
        assert link.platform is None  # only relevant for caption mentions
        assert link.handle is None
        assert link.source_text is None  # optional context

    def test_caption_mention_with_platform_handle(self):
        from schemas import HighlightLink
        link = HighlightLink(
            url="",  # synthesized later
            source="highlight_caption_mention",
            platform="tiktok",
            handle="kira_tt",
            source_text="follow my tt @kira_tt",
        )
        assert link.platform == "tiktok"
        assert link.handle == "kira_tt"

    def test_rejects_unknown_source(self):
        from schemas import HighlightLink
        from pydantic import ValidationError
        import pytest as _pt
        with _pt.raises(ValidationError):
            HighlightLink(url="https://x", source="not_a_real_source")
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
cd scripts && python -m pytest tests/test_schemas.py::TestHighlightLink -v
```

Expected: FAIL with `ImportError: cannot import name 'HighlightLink'` (or similar).

- [ ] **Step 3: Add the model**

In `scripts/schemas.py`, after the `TextMention` class (around line 117), add:

```python
HighlightSource = Literal["highlight_link_sticker", "highlight_caption_mention"]


class HighlightLink(BaseModel):
    """A URL or handle surfaced from an IG highlight item.

    Two flavors:
    - `highlight_link_sticker`: an absolute URL clicked through the link sticker.
      `url` is populated; `platform`/`handle` may be None.
    - `highlight_caption_mention`: a @handle mention in the caption/text overlay,
      extracted by Gemini. `platform` + `handle` are populated; `url` is "" (the
      resolver synthesizes it via _synthesize_url).
    """
    url: str = ""
    source: HighlightSource
    platform: Optional[Platform] = None
    handle: Optional[str] = None
    source_text: Optional[str] = None  # raw caption / sticker title for debugging
```

Make sure `Optional`, `Literal`, `Platform`, and `BaseModel` are already imported at the top — they are (verified at design time).

- [ ] **Step 4: Run all tests to verify nothing else broke**

```bash
cd scripts && python -m pytest -q
```

Expected: `125 passed` (122 baseline + 3 new). No failures.

- [ ] **Step 5: Commit**

```bash
git add scripts/schemas.py scripts/tests/test_schemas.py
git commit -m "feat(schemas): add HighlightLink for IG highlights link/mention surfacing"
```

---

## Task 2 — Implement `fetch_highlights` (unit-tested fetcher)

**Files:**
- Create: `scripts/fetchers/instagram_highlights.py`
- Create: `scripts/tests/fetchers/test_instagram_highlights.py`

- [ ] **Step 1: Write the failing test**

Create `scripts/tests/fetchers/test_instagram_highlights.py`:

```python
# scripts/tests/fetchers/test_instagram_highlights.py
from unittest.mock import MagicMock
import pytest

from schemas import HighlightLink


def _mk_apify_client(items: list[dict]) -> MagicMock:
    """Build a mock Apify client whose actor.call → dataset.list_items returns items."""
    client = MagicMock()
    client.actor.return_value.call.return_value = {"defaultDatasetId": "ds-fake"}
    client.dataset.return_value.list_items.return_value = MagicMock(items=items)
    return client


def test_fetch_highlights_extracts_link_stickers():
    from fetchers.instagram_highlights import fetch_highlights
    items = [
        {
            "pk": "1",
            "taken_at": 1700000000,
            "media_type": 1,
            "story_link_stickers": [
                {"display_url": "https://onlyfans.com/kira",
                 "link_title": "OnlyFans",
                 "url": "https://onlyfans.com/kira"},
            ],
            "mentions": [],
        },
    ]
    client = _mk_apify_client(items)
    out = fetch_highlights(client, "kirapregiato")
    assert len(out) == 1
    assert isinstance(out[0], HighlightLink)
    assert out[0].source == "highlight_link_sticker"
    assert out[0].url == "https://onlyfans.com/kira"


def test_fetch_highlights_extracts_caption_mentions():
    from fetchers.instagram_highlights import fetch_highlights
    items = [
        {
            "pk": "2",
            "taken_at": 1700000000,
            "media_type": 1,
            "story_link_stickers": [],
            "mentions": [{"username": "kira_tt"}, {"username": "kira_yt"}],
        },
    ]
    client = _mk_apify_client(items)
    out = fetch_highlights(client, "kirapregiato")
    handles = sorted(h.handle for h in out if h.source == "highlight_caption_mention")
    # Both mentions surface, but platform must be None (caller's job to figure out
    # which platform — we don't guess).
    assert handles == ["kira_tt", "kira_yt"]
    for link in out:
        assert link.source == "highlight_caption_mention"
        assert link.platform is None  # platform inference deferred to caller


def test_fetch_highlights_returns_empty_for_empty_dataset():
    from fetchers.instagram_highlights import fetch_highlights
    client = _mk_apify_client([])
    assert fetch_highlights(client, "kirapregiato") == []


def test_fetch_highlights_skips_items_without_anything():
    from fetchers.instagram_highlights import fetch_highlights
    items = [
        {"pk": "3", "taken_at": 1, "media_type": 1,
         "story_link_stickers": [], "mentions": []},
        {"pk": "4", "taken_at": 1, "media_type": 1},  # missing both keys entirely
    ]
    client = _mk_apify_client(items)
    assert fetch_highlights(client, "kirapregiato") == []


def test_fetch_highlights_dedupes_within_run():
    from fetchers.instagram_highlights import fetch_highlights
    items = [
        {"pk": "5", "taken_at": 1, "media_type": 1,
         "story_link_stickers": [{"url": "https://onlyfans.com/kira"}],
         "mentions": []},
        {"pk": "6", "taken_at": 2, "media_type": 1,
         "story_link_stickers": [{"url": "https://onlyfans.com/kira"}],  # dup
                "mentions": []},
    ]
    client = _mk_apify_client(items)
    out = fetch_highlights(client, "kirapregiato")
    urls = [h.url for h in out]
    assert urls.count("https://onlyfans.com/kira") == 1


def test_fetch_highlights_returns_empty_on_apify_error():
    """Top-level exception handler: never raise, log and return []."""
    from fetchers.instagram_highlights import fetch_highlights
    client = MagicMock()
    client.actor.return_value.call.side_effect = RuntimeError("boom")
    out = fetch_highlights(client, "kirapregiato")
    assert out == []
```

Also create `scripts/tests/fetchers/__init__.py` if it doesn't already exist (it does — verified at design time). No action needed if the file is present.

- [ ] **Step 2: Run the tests to verify they fail**

```bash
cd scripts && python -m pytest tests/fetchers/test_instagram_highlights.py -v
```

Expected: ImportError — `fetchers.instagram_highlights` doesn't exist yet.

- [ ] **Step 3: Implement the fetcher**

Create `scripts/fetchers/instagram_highlights.py`:

```python
# scripts/fetchers/instagram_highlights.py — Apify IG highlights fetcher (stories mode)
import logging
from typing import Any

from apify_client import ApifyClient
from tenacity import (
    retry, stop_after_attempt, wait_exponential, retry_if_exception, before_sleep_log,
)

from schemas import HighlightLink
from fetchers.base import is_transient_apify_error


_log = logging.getLogger(__name__)


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=2, min=3, max=15),
    retry=retry_if_exception(is_transient_apify_error),
    reraise=True,
    before_sleep=before_sleep_log(_log, logging.WARNING),
)
def _call_actor(client: ApifyClient, run_input: dict[str, Any]) -> dict:
    """Wraps the Apify actor call with retry on transient proxy/challenge errors.

    Mirrors fetchers/instagram.py::_call_actor exactly — same retry profile.
    """
    return client.actor("apify/instagram-scraper").call(run_input=run_input)


def _parse_link_stickers(item: dict) -> list[HighlightLink]:
    """Extract HighlightLink rows from one story-item's story_link_stickers."""
    out: list[HighlightLink] = []
    for s in (item.get("story_link_stickers") or []):
        url = (s or {}).get("url")
        if not url:
            continue
        title = (s or {}).get("link_title")
        out.append(HighlightLink(
            url=url,
            source="highlight_link_sticker",
            source_text=title,
        ))
    return out


def _parse_mentions(item: dict) -> list[HighlightLink]:
    """Extract HighlightLink rows from one story-item's mentions[]."""
    out: list[HighlightLink] = []
    for m in (item.get("mentions") or []):
        handle = (m or {}).get("username") if isinstance(m, dict) else m
        if not handle:
            continue
        out.append(HighlightLink(
            url="",
            source="highlight_caption_mention",
            platform=None,  # caller's responsibility to infer (resolver may dispatch
                            # to multiple synthesis attempts or skip if ambiguous)
            handle=str(handle).lstrip("@"),
        ))
    return out


def fetch_highlights(client: ApifyClient, handle: str) -> list[HighlightLink]:
    """Fetch IG highlights for `handle` and return surfaced URLs/mentions.

    Uses apify/instagram-scraper resultsType=stories (which Instagram's reel_media
    endpoint covers — includes pinned highlights when addParentData is True).

    Returns [] on:
    - Empty dataset (no highlights, private profile, login wall)
    - Any exception (network, schema mismatch, rate limit after retries)

    NEVER raises — a failed highlights extraction must not crash discovery.
    Same contract as run_gemini_bio_mentions.
    """
    try:
        run_input: dict[str, Any] = {
            "directUrls": [f"https://www.instagram.com/{handle}/"],
            "resultsType": "stories",
            "resultsLimit": 200,  # generous — most creators have <50 highlight items
            "addParentData": True,  # required to attribute items to parent highlight
        }
        run = _call_actor(client, run_input)
        items = client.dataset(run["defaultDatasetId"]).list_items().items or []
    except Exception as e:
        _log.warning("highlights extraction failed for @%s: %s", handle, e)
        return []

    seen_urls: set[str] = set()
    seen_mentions: set[str] = set()
    out: list[HighlightLink] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        for link in _parse_link_stickers(item):
            if link.url in seen_urls:
                continue
            seen_urls.add(link.url)
            out.append(link)
        for link in _parse_mentions(item):
            key = f"{link.platform}|{link.handle}"
            if key in seen_mentions:
                continue
            seen_mentions.add(key)
            out.append(link)
    return out
```

- [ ] **Step 4: Run the unit tests**

```bash
cd scripts && python -m pytest tests/fetchers/test_instagram_highlights.py -v
```

Expected: 6 passed.

- [ ] **Step 5: Run the full suite**

```bash
cd scripts && python -m pytest -q
```

Expected: `131 passed` (125 + 6 new). All green.

- [ ] **Step 6: Commit**

```bash
git add scripts/fetchers/instagram_highlights.py scripts/tests/fetchers/test_instagram_highlights.py
git commit -m "feat(fetchers): instagram_highlights — surface link stickers + mentions"
```

---

## Task 3 — Add `fetch_highlights` wrapper at resolver module scope

**Files:**
- Modify: `scripts/pipeline/resolver.py`
- Modify: `scripts/tests/pipeline/test_resolver_recursive.py`

The resolver tests patch fetchers at `pipeline.resolver.<name>`. We need the same shape for `fetch_highlights`.

- [ ] **Step 1: Write the failing test**

Append to `scripts/tests/pipeline/test_resolver_recursive.py`:

```python
def test_resolver_module_exposes_fetch_highlights_wrapper():
    """The resolver re-exports fetch_highlights so tests can patch at this site."""
    from pipeline import resolver
    assert hasattr(resolver, "fetch_highlights"), \
        "pipeline.resolver must export fetch_highlights for test patching"
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
cd scripts && python -m pytest tests/pipeline/test_resolver_recursive.py::test_resolver_module_exposes_fetch_highlights_wrapper -v
```

Expected: FAIL — `pipeline.resolver` has no attribute `fetch_highlights`.

- [ ] **Step 3: Add the wrapper**

In `scripts/pipeline/resolver.py`, alongside the existing `run_gemini_bio_mentions` wrapper (around line 163), add:

```python
def fetch_highlights(client: ApifyClient, handle: str) -> list:
    """Re-exported from fetchers.instagram_highlights so tests can patch at this site.

    Imported lazily inside the function to avoid eager Apify client init at
    module load time — same pattern as run_gemini_bio_mentions.
    """
    from fetchers.instagram_highlights import fetch_highlights as _impl
    return _impl(client, handle)
```

(Type annotation uses `list` rather than `list[HighlightLink]` to keep the wrapper light. The implementation has the strict typing.)

- [ ] **Step 4: Run the test**

```bash
cd scripts && python -m pytest tests/pipeline/test_resolver_recursive.py::test_resolver_module_exposes_fetch_highlights_wrapper -v
```

Expected: PASS.

- [ ] **Step 5: Run all tests**

```bash
cd scripts && python -m pytest -q
```

Expected: 132 passed (131 + 1 new).

- [ ] **Step 6: Commit**

```bash
git add scripts/pipeline/resolver.py scripts/tests/pipeline/test_resolver_recursive.py
git commit -m "feat(resolver): re-export fetch_highlights wrapper for test patching"
```

---

## Task 4 — Add `HIGHLIGHTS_ENABLED` env flag + `HIGHLIGHTS_COST_CENTS` constant

**Files:**
- Modify: `scripts/pipeline/resolver.py`
- Modify: `scripts/tests/pipeline/test_resolver_recursive.py`

- [ ] **Step 1: Write the failing test**

Append to `scripts/tests/pipeline/test_resolver_recursive.py`:

```python
def test_resolver_module_exposes_highlights_enabled_constant():
    from pipeline import resolver
    assert hasattr(resolver, "HIGHLIGHTS_ENABLED")
    assert isinstance(resolver.HIGHLIGHTS_ENABLED, bool)


def test_resolver_module_exposes_highlights_cost_cents_constant():
    from pipeline import resolver
    assert hasattr(resolver, "HIGHLIGHTS_COST_CENTS")
    assert isinstance(resolver.HIGHLIGHTS_COST_CENTS, int)
    assert resolver.HIGHLIGHTS_COST_CENTS > 0
```

- [ ] **Step 2: Run the tests to verify they fail**

```bash
cd scripts && python -m pytest tests/pipeline/test_resolver_recursive.py -k "highlights_enabled_constant or highlights_cost_cents_constant" -v
```

Expected: 2 failures (`AttributeError`).

- [ ] **Step 3: Add the constants**

In `scripts/pipeline/resolver.py`, just below the existing `RECURSIVE_GEMINI` line (around line 45), add:

```python
# When True, enriched IG profiles at depth >= 1 get a highlights scrape via
# apify/instagram-scraper resultsType=stories. Default ON — closes the gap where
# CTAs live in highlights instead of bio. Kill switch for emergency rollback.
HIGHLIGHTS_ENABLED = os.getenv("DISCOVERY_HIGHLIGHTS_ENABLED", "1") == "1"

# Cost gate for the highlights scrape. Hand-maintained, err on the high side per
# existing _APIFY_COSTS convention. ~50 story items per profile × $1/1000 = $0.05.
HIGHLIGHTS_COST_CENTS = int(os.getenv("DISCOVERY_HIGHLIGHTS_COST_CENTS", "5"))
```

- [ ] **Step 4: Run the tests**

```bash
cd scripts && python -m pytest tests/pipeline/test_resolver_recursive.py -k "highlights_enabled_constant or highlights_cost_cents_constant" -v
```

Expected: 2 passed.

- [ ] **Step 5: Run all tests**

```bash
cd scripts && python -m pytest -q
```

Expected: 134 passed.

- [ ] **Step 6: Commit**

```bash
git add scripts/pipeline/resolver.py scripts/tests/pipeline/test_resolver_recursive.py
git commit -m "feat(resolver): HIGHLIGHTS_ENABLED env flag + HIGHLIGHTS_COST_CENTS"
```

---

## Task 5 — TDD: Wire highlights link stickers into `_expand` (depth ≥ 1, IG only)

**Files:**
- Modify: `scripts/pipeline/resolver.py`
- Modify: `scripts/tests/pipeline/test_resolver_recursive.py`

This is the core feature. The first assertion: a depth-1 IG profile with a highlight link sticker pointing to OnlyFans makes that OF URL appear in `discovered_urls` at depth 2.

- [ ] **Step 1: Write the failing test**

Append to `scripts/tests/pipeline/test_resolver_recursive.py`:

```python
@patch("pipeline.resolver.fetch_highlights")
@patch("pipeline.resolver.run_gemini_bio_mentions")
@patch("pipeline.resolver.fetch_ig.fetch")
@patch("pipeline.resolver.run_gemini_discovery_v2")
@patch("pipeline.resolver.classify")
@patch("pipeline.resolver.fetch_seed")
def test_highlight_link_sticker_lands_in_discovered_urls(
    mock_fetch_seed, mock_classify, mock_gemini_seed, mock_ig_fetch,
    mock_gemini_bio, mock_fetch_highlights,
):
    """Depth-1 IG profile has a highlight with an OF link sticker.
    The OF URL must land in discovered_urls at depth 2."""
    from schemas import HighlightLink

    mock_fetch_seed.return_value = _mk_ctx(
        handle="seed", platform="instagram",
        external_urls=["https://instagram.com/sec"],
    )
    # Depth-1 IG profile: empty bio, no externals — only highlights are the source
    mock_ig_fetch.return_value = _mk_ctx(
        handle="sec", platform="instagram",
        bio="", external_urls=[],
    )
    mock_gemini_bio.return_value = []  # no bio mentions
    mock_fetch_highlights.return_value = [
        HighlightLink(
            url="https://onlyfans.com/sec",
            source="highlight_link_sticker",
        ),
    ]

    classifications = iter([
        Classification(platform="instagram", account_type="social",
                       confidence=1.0, reason="rule:instagram_social"),
        Classification(platform="onlyfans", account_type="monetization",
                       confidence=1.0, reason="rule:onlyfans_monetization"),
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

    by_url = {du.canonical_url: du for du in result.discovered_urls}
    of = next((du for url, du in by_url.items() if "onlyfans.com/sec" in url), None)
    assert of is not None, \
        f"highlight-surfaced OF URL missing from {list(by_url.keys())}"
    assert of.depth == 2, f"OF should be depth 2, got {of.depth}"
    # And fetch_highlights was actually called (for the depth-1 IG)
    assert mock_fetch_highlights.called
    # And NOT called for the seed (depth 0)
    assert mock_fetch_highlights.call_count == 1
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
cd scripts && python -m pytest tests/pipeline/test_resolver_recursive.py::test_highlight_link_sticker_lands_in_discovered_urls -v
```

Expected: FAIL — `mock_fetch_highlights.called` is False because nothing in `_expand` calls it yet, and the OF URL is missing.

- [ ] **Step 3: Wire highlights into `_expand`**

In `scripts/pipeline/resolver.py`, update `_expand` (currently at lines 311–334) to add a third branch after bio-mentions. The full new body:

```python
    def _expand(ctx: InputContext, depth: int) -> None:
        """Expand ctx's outbound links + bio mentions + IG highlights one hop further.

        ctx is at `depth`; surfaced URLs are processed at depth+1. Highlights only
        fire for IG profiles at depth >= 1 (the seed gets full Gemini canonicalization;
        seed highlights land in v2 where there's a UI to display them).
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
        if (
            depth >= 1
            and ctx.platform == "instagram"
            and HIGHLIGHTS_ENABLED
            and budget.can_afford(HIGHLIGHTS_COST_CENTS)
        ):
            try:
                budget.debit("apify/instagram-scraper-stories", HIGHLIGHTS_COST_CENTS)
                links = fetch_highlights(apify_client, ctx.handle)
            except BudgetExhaustedError:
                return
            except Exception as e:
                console.log(f"[yellow]highlights branch failed for @{ctx.handle}: {e}[/yellow]")
                return
            for link in links:
                if link.source == "highlight_link_sticker" and link.url:
                    try:
                        _classify_and_enrich(link.url, depth=depth + 1)
                    except BudgetExhaustedError:
                        return
                elif link.source == "highlight_caption_mention" and link.platform and link.handle:
                    # Reuse _synthesize_url with a TextMention shim — the helper
                    # only inspects platform + handle.
                    from schemas import TextMention
                    synth = _synthesize_url(TextMention(
                        platform=link.platform, handle=link.handle, source="enriched_bio",
                    ))
                    if synth:
                        try:
                            _classify_and_enrich(synth, depth=depth + 1)
                        except BudgetExhaustedError:
                            return
```

Note: the caption-mention branch requires `link.platform`, but our v1 fetcher returns `platform=None` for caption mentions (Apify gives us `mentions[].username` only — no platform attribution). That's intentional: when `platform is None`, the caption-mention branch is a no-op, and the link is silently skipped. This is consistent with v1 scope: "extract URLs/handles for the resolver to follow." If the platform can't be inferred, we can't synthesize a URL, so we skip — same behavior as bio-mentions when Gemini returns an unrecognized platform string.

- [ ] **Step 4: Run the test**

```bash
cd scripts && python -m pytest tests/pipeline/test_resolver_recursive.py::test_highlight_link_sticker_lands_in_discovered_urls -v
```

Expected: PASS.

- [ ] **Step 5: Run all tests**

```bash
cd scripts && python -m pytest -q
```

Expected: 135 passed.

- [ ] **Step 6: Commit**

```bash
git add scripts/pipeline/resolver.py scripts/tests/pipeline/test_resolver_recursive.py
git commit -m "feat(resolver): wire IG highlights link stickers into _expand"
```

---

## Task 6 — TDD: Highlights skipped at depth 0 (seed) and for non-IG platforms

**Files:**
- Modify: `scripts/tests/pipeline/test_resolver_recursive.py`

- [ ] **Step 1: Write the test**

Append:

```python
@patch("pipeline.resolver.fetch_highlights")
@patch("pipeline.resolver.run_gemini_bio_mentions")
@patch("pipeline.resolver.fetch_ig.fetch")
@patch("pipeline.resolver.run_gemini_discovery_v2")
@patch("pipeline.resolver.classify")
@patch("pipeline.resolver.fetch_seed")
def test_highlights_not_called_for_seed_or_non_ig(
    mock_fetch_seed, mock_classify, mock_gemini_seed, mock_ig_fetch,
    mock_gemini_bio, mock_fetch_highlights,
):
    """Seed (depth 0) never triggers highlights. A TT secondary (depth 1) doesn't either."""
    mock_fetch_seed.return_value = _mk_ctx(
        handle="seed", platform="instagram",
        external_urls=["https://tiktok.com/@sec_tt"],  # depth-1 TT
    )
    # Mock the TT fetcher so the secondary enriches successfully
    with patch("pipeline.resolver.fetch_tt.fetch") as mock_tt_fetch:
        mock_tt_fetch.return_value = _mk_ctx(
            handle="sec_tt", platform="tiktok",
            bio="", external_urls=[],
        )
        mock_gemini_bio.return_value = []
        mock_classify.return_value = Classification(
            platform="tiktok", account_type="social",
            confidence=1.0, reason="rule:tiktok_social",
        )
        mock_gemini_seed.return_value = DiscoveryResultV2(
            canonical_name="Seed", known_usernames=["seed"],
            display_name_variants=["Seed"], raw_reasoning="",
        )
        budget = BudgetTracker(cap_cents=1000)
        resolve_seed(
            handle="seed", platform_hint="instagram",
            supabase=MagicMock(), apify_client=MagicMock(),
            budget=budget,
        )

    # Highlights branch must never have fired:
    # - seed is depth 0 (skipped by `depth >= 1` gate)
    # - the only secondary is TT (skipped by `ctx.platform == "instagram"` gate)
    assert not mock_fetch_highlights.called, \
        "fetch_highlights was called despite no IG depth-1 profile"
```

- [ ] **Step 2: Run the test**

```bash
cd scripts && python -m pytest tests/pipeline/test_resolver_recursive.py::test_highlights_not_called_for_seed_or_non_ig -v
```

Expected: PASS (Task 5's gates already enforce this).

- [ ] **Step 3: Run all tests**

```bash
cd scripts && python -m pytest -q
```

Expected: 136 passed.

- [ ] **Step 4: Commit**

```bash
git add scripts/tests/pipeline/test_resolver_recursive.py
git commit -m "test(resolver): highlights skipped for seed depth-0 and non-IG secondaries"
```

---

## Task 7 — TDD: Highlights failure returns gracefully

**Files:**
- Modify: `scripts/tests/pipeline/test_resolver_recursive.py`

- [ ] **Step 1: Write the test**

Append:

```python
@patch("pipeline.resolver.fetch_highlights")
@patch("pipeline.resolver.run_gemini_bio_mentions")
@patch("pipeline.resolver.fetch_ig.fetch")
@patch("pipeline.resolver.run_gemini_discovery_v2")
@patch("pipeline.resolver.classify")
@patch("pipeline.resolver.fetch_seed")
def test_highlights_failure_does_not_crash_resolver(
    mock_fetch_seed, mock_classify, mock_gemini_seed, mock_ig_fetch,
    mock_gemini_bio, mock_fetch_highlights,
):
    """When fetch_highlights raises, resolver completes cleanly. Other branches (
    external_urls, bio_mentions) still surface their URLs."""
    mock_fetch_seed.return_value = _mk_ctx(
        handle="seed", platform="instagram",
        external_urls=["https://instagram.com/sec"],
    )
    mock_ig_fetch.return_value = _mk_ctx(
        handle="sec", platform="instagram",
        bio="follow @sec_tt on tiktok",
        external_urls=["https://onlyfans.com/sec"],
    )
    # bio_mentions returns something — must still surface
    mock_gemini_bio.return_value = [
        TextMention(platform="tiktok", handle="sec_tt", source="enriched_bio"),
    ]
    # Highlights fetcher blows up
    mock_fetch_highlights.side_effect = RuntimeError("apify timeout")

    classifications = iter([
        Classification(platform="instagram", account_type="social",
                       confidence=1.0, reason="rule:instagram_social"),
        Classification(platform="onlyfans", account_type="monetization",
                       confidence=1.0, reason="rule:onlyfans_monetization"),
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

    # No exception leaked — resolver returned cleanly.
    assert isinstance(result, ResolverResult)
    urls = [du.canonical_url for du in result.discovered_urls]
    # external_urls branch landed
    assert any("onlyfans.com/sec" in u for u in urls)
    # bio_mentions branch landed
    assert any("tiktok.com/@sec_tt" in u for u in urls)
```

- [ ] **Step 2: Run the test**

```bash
cd scripts && python -m pytest tests/pipeline/test_resolver_recursive.py::test_highlights_failure_does_not_crash_resolver -v
```

Expected: PASS — Task 5's `try/except Exception` swallows the failure.

- [ ] **Step 3: Run all tests**

```bash
cd scripts && python -m pytest -q
```

Expected: 137 passed.

- [ ] **Step 4: Commit**

```bash
git add scripts/tests/pipeline/test_resolver_recursive.py
git commit -m "test(resolver): highlights failure returns resolver cleanly"
```

---

## Task 8 — TDD: `HIGHLIGHTS_ENABLED=0` skips the entire branch

**Files:**
- Modify: `scripts/tests/pipeline/test_resolver_recursive.py`

- [ ] **Step 1: Write the test**

Append:

```python
@patch("pipeline.resolver.fetch_highlights")
@patch("pipeline.resolver.run_gemini_bio_mentions")
@patch("pipeline.resolver.fetch_ig.fetch")
@patch("pipeline.resolver.run_gemini_discovery_v2")
@patch("pipeline.resolver.classify")
@patch("pipeline.resolver.fetch_seed")
def test_highlights_disabled_skips_branch(
    mock_fetch_seed, mock_classify, mock_gemini_seed, mock_ig_fetch,
    mock_gemini_bio, mock_fetch_highlights, monkeypatch,
):
    """HIGHLIGHTS_ENABLED=False — fetch_highlights is never called even for IG depth 1."""
    monkeypatch.setattr("pipeline.resolver.HIGHLIGHTS_ENABLED", False)

    mock_fetch_seed.return_value = _mk_ctx(
        handle="seed", platform="instagram",
        external_urls=["https://instagram.com/sec"],
    )
    mock_ig_fetch.return_value = _mk_ctx(
        handle="sec", platform="instagram", bio="", external_urls=[],
    )
    mock_gemini_bio.return_value = []
    mock_classify.return_value = Classification(
        platform="instagram", account_type="social",
        confidence=1.0, reason="rule:instagram_social",
    )
    mock_gemini_seed.return_value = DiscoveryResultV2(
        canonical_name="Seed", known_usernames=["seed"],
        display_name_variants=["Seed"], raw_reasoning="",
    )

    budget = BudgetTracker(cap_cents=1000)
    resolve_seed(
        handle="seed", platform_hint="instagram",
        supabase=MagicMock(), apify_client=MagicMock(),
        budget=budget,
    )
    assert not mock_fetch_highlights.called, \
        "highlights branch fired despite HIGHLIGHTS_ENABLED=False"
    # Budget should NOT have been debited for highlights
    assert budget.spent_cents < 20, \
        f"budget debited for highlights: spent={budget.spent_cents}c"
```

- [ ] **Step 2: Run the test**

```bash
cd scripts && python -m pytest tests/pipeline/test_resolver_recursive.py::test_highlights_disabled_skips_branch -v
```

Expected: PASS.

- [ ] **Step 3: Run all tests**

```bash
cd scripts && python -m pytest -q
```

Expected: 138 passed.

- [ ] **Step 4: Commit**

```bash
git add scripts/tests/pipeline/test_resolver_recursive.py
git commit -m "test(resolver): HIGHLIGHTS_ENABLED=0 skips highlights branch entirely"
```

---

## Task 9 — Live smoke test

**Files:** none (operational)

This is the build gate. The automated tests prove the wiring; this proves `apify/instagram-scraper` `resultsType=stories` actually returns pinned highlights with link stickers.

- [ ] **Step 1: Pick a smoke target**

Find a creator known to use highlights for CTAs. Two paths:
- Check the recursive funnel session note (`06-Sessions/2026-04-25.md` or whichever has the Kira smoke) for any creators flagged as "highlights-only."
- Pick `@esmae` if her IG has highlights named "OF", "LINKS", or similar (Simon flagged this archetype in the brainstorm).
- Or browse 2–3 creators in the workspace's HQ pages and pick one whose IG (in the browser) has a "LINKS" or "OF" highlight visible on profile.

Record the chosen handle in the session note before running.

- [ ] **Step 2: Confirm the worker is running fresh code**

```bash
bash scripts/worker_ctl.sh restart
bash scripts/worker_ctl.sh status
```

Expected: status shows worker alive.

- [ ] **Step 3: Re-run discovery for the smoke creator**

In the dev UI: navigate to the creator's HQ page, click **Re-run Discovery**, confirm toast.

- [ ] **Step 4: Watch the worker log**

```bash
tail -f ~/Library/Logs/the-hub-worker.log
```

Watch for:
- `Mapping secondary funnels` (from recursive funnel) — confirms a depth-1 IG was enriched.
- An Apify call to `apify/instagram-scraper` with `resultsType: "stories"` — visible in the worker log if your log level is INFO or below.
- New `discovered_urls` rows landing.

- [ ] **Step 5: Verify highlights were returned**

```sql
SELECT p.platform, p.handle, p.url, p.discovery_confidence, p.discovery_reason
FROM profiles p
JOIN creators c ON c.id = p.creator_id
WHERE c.canonical_name ILIKE '%<smoke_creator>%'
  AND p.is_active = true
  AND p.created_at > now() - interval '10 minutes'
ORDER BY p.discovery_confidence DESC;
```

Look for rows that weren't there before — those are highlights-surfaced. Cross-check with the creator's actual IG profile in a browser: the URLs in the highlight link stickers should match.

- [ ] **Step 6: Build gate decision**

If new URLs appeared that match link stickers visible in the creator's IG highlights → **PROCEED to Task 10**.

If NO new URLs appeared AND the creator definitely has highlight link stickers visible in the browser → **STOP and ESCALATE to Simon**:
- The `apify/instagram-scraper` `stories` mode may not return pinned highlights.
- The fallback per the spec is `louisdeconinck/instagram-highlights-scraper`, which has `mentions` but no documented `linkSticker` output (would reduce v1 to caption-mention-only). Simon decides.

- [ ] **Step 7: Document the smoke result**

Add a section to `06-Sessions/<today>.md` titled "Highlights v1 — live smoke" with: which creator, which new URLs surfaced, any anomalies, total Apify spend (visible via `bulk_imports.cost_apify_cents` if applicable, or the worker log).

---

## Task 10 — Sync project state

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

Expected: 138 passed (or higher). Record the new total in the session note.

- [ ] **Step 4: Final tsc check**

```bash
cd "/Users/simon/OS/Living VAULT/Content OS/The Hub" && npx tsc --noEmit
```

Expected: 0 errors.

---

## Cost / Risk Analysis

**Apify cost per discovery (estimated):**

| Scenario | Recursive funnel only | + Highlights v1 |
|---|---|---|
| Best case (no IG secondaries) | ~$0.10 | ~$0.10 (no highlights call) |
| Typical (2–3 IG secondaries with highlights) | ~$0.30 | ~$0.40–$0.45 |
| Heavy (5+ IG secondaries with highlights + aggregators) | ~$0.50 | ~$0.65–$0.75 |

Net delta: **+5 cents per IG depth-1 secondary**, capped by `BudgetTracker` at $1.00/run by default.

**Risk: runaway expansion.** Triple-bounded:
1. `MAX_DEPTH=6` — defensive cap at the URL classification step.
2. `BudgetTracker` — caps total Apify spend per discovery run.
3. `visited_canonical` — dedup across all branches (external_urls, bio_mentions, highlights).
4. **NEW:** `DISCOVERY_HIGHLIGHTS_ENABLED=0` — operator kill switch.

No new failure modes vs. the recursive funnel.

---

## What this does NOT do

- Persistent media storage, downloadable assets — v2.
- Highlights tab in Creator HQ — v2.
- Scheduled refresh worker — v2.
- Vision-LLM extraction of CTAs from image overlays — v2 or later.
- Highlights for non-IG platforms — deferred (TikTok/YT have different primitives).
- Highlights for the seed itself — v2 (no UI home in v1).
- Caption-mention platform inference when Apify only gives `username` — v1 skips these. Adding Gemini-driven platform inference is a follow-up if smoke shows we're losing many CTAs to this gap.

---

## Self-Review Checklist

- [x] Each task has 2–5-minute steps with explicit commands and code blocks.
- [x] No "TBD" / "TODO" / "implement later" placeholders.
- [x] Type names consistent (`HighlightLink`, `HIGHLIGHTS_ENABLED`, `HIGHLIGHTS_COST_CENTS`, `fetch_highlights`).
- [x] Patch import paths consistent (`pipeline.resolver.fetch_highlights`, mirrors `pipeline.resolver.run_gemini_bio_mentions`).
- [x] Existing 122 tests in the suite continue to pass through every task.
- [x] Build gate (smoke test) explicit: STOP and escalate if `apify/instagram-scraper` `stories` mode doesn't return pinned highlights.
- [x] Triple-bounded against runaway: visited_canonical + BudgetTracker + HIGHLIGHTS_ENABLED kill switch.
- [x] No new tables, no UI, no schema migration — confirmed against v1 scope.
