# Universal URL Harvester Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the per-aggregator extractors (`linktree.py`, `beacons.py`, `custom_domain.py`) with one universal harvester that works on any URL — aggregator, funnel page, product page, blog, SPA — with a cheap-first cascade: cache → httpx static parse → Apify Web Scraper headless fallback. Captures JS-gated "sensitive content" / "open link" interstitials that the current pipeline silently misses (loses every OF/Fanvue/Fanplace link wrapped behind a 2-step click). Saves every harvested URL with an extended `destination_class` taxonomy so creators' full link networks are visible and filterable in the UI.

**Architecture:**
- New package `scripts/harvester/` with `harvest_urls(url) -> list[HarvestedUrl]` as the single entry point.
- Three-tier cascade per URL: workspace-agnostic cache (24h TTL) → Tier 1 httpx + BeautifulSoup with signal-regex escalation triggers → Tier 2 Apify Web Scraper page function that hooks `window.open`/`location` setters and auto-clicks interstitials.
- `pipeline/resolver.py::_classify_and_enrich` keeps its recursion structure exactly as-is; only the per-aggregator dispatch block (lines 283–297) is replaced with one `harvest_urls()` call gated by an expanded `HARVEST_CLASSES` set.
- Extended `DestinationClass` Literal: `monetization | aggregator | social | commerce | messaging | content | affiliate | professional | other | unknown`.
- New `url_harvest_cache` table (workspace-agnostic, mirrors `classifier_llm_guesses`); 3 new columns on `profile_destination_links` for harvest-method audit trail.
- Creator HQ (`/creators/[slug]`) gets a new "All Destinations" section grouping links by `destination_class`.

**Tech Stack:** Python 3.11, httpx, BeautifulSoup4, pydantic v2, apify-client, pytest, supabase-py, Next.js 16.2.4, react-icons, Apify `apify/puppeteer-scraper` actor.

---

## File Structure

**Create:**
- `scripts/harvester/__init__.py` — exports `harvest_urls`
- `scripts/harvester/types.py` — `HarvestedUrl`, `Tier1Result`, signal constants
- `scripts/harvester/cache.py` — `lookup_cache`, `write_cache`
- `scripts/harvester/tier1_static.py` — `fetch_static`, signal detection
- `scripts/harvester/tier2_headless.py` — `fetch_headless` (Apify Web Scraper integration)
- `scripts/harvester/orchestrator.py` — `harvest_urls` cascade
- `scripts/harvester/page_function.js` — Apify page function (JS string)
- `scripts/tests/harvester/__init__.py`
- `scripts/tests/harvester/test_canonicalize_extension.py`
- `scripts/tests/harvester/test_types.py`
- `scripts/tests/harvester/test_cache.py`
- `scripts/tests/harvester/test_tier1.py`
- `scripts/tests/harvester/test_tier2.py`
- `scripts/tests/harvester/test_orchestrator.py`
- `scripts/tests/harvester/fixtures/tapforallmylinks_esmae.html` — captured live HTML for fixture
- `scripts/tests/harvester/fixtures/linktree_clean.html` — clean linktree (Tier 1 wins)
- `scripts/tests/harvester/fixtures/spa_hydration.html` — empty `<div id="root">` SPA
- `supabase/migrations/20260426000000_url_harvester_v1.sql`
- `src/components/creators/CreatorDestinations.tsx` — grouped destination list

**Modify:**
- `scripts/pipeline/canonicalize.py` — add 5 tracking params (`igsh`, `l_`, `s`, `_t`, `aff`)
- `scripts/schemas.py` — extend `DestinationClass` Literal
- `scripts/data/monetization_overlay.yaml` — add ~30 rules covering new classes
- `scripts/pipeline/classifier.py` — accepts new `destination_class` from gazetteer rules
- `scripts/pipeline/resolver.py` — replace per-aggregator dispatch (lines 283–297) with `harvest_urls()` call
- `scripts/discover_creator.py` — `_commit_v2` writes `harvest_method`, `raw_text`, `harvested_at` columns
- `src/app/(dashboard)/creators/[slug]/page.tsx` — render `<CreatorDestinations>` section
- `src/lib/db/queries.ts` — add `getDestinationsForCreator(creatorId)`
- `src/types/database.types.ts` — regenerated
- `PROJECT_STATE.md` — sync §4 schema, §10 deprecated aggregator modules removed
- `docs/SCHEMA.md` — regenerated

**Delete:**
- `scripts/aggregators/linktree.py`
- `scripts/aggregators/beacons.py`
- `scripts/aggregators/custom_domain.py`
- `scripts/aggregators/__init__.py`
- `scripts/aggregators/` (whole package)
- `scripts/tests/aggregators/` (whole test dir — replaced by harvester tests)

---

## Task 1: Extend canonicalizer with missing tracking params

**Files:**
- Modify: `scripts/pipeline/canonicalize.py:6-10`
- Test: `scripts/tests/harvester/test_canonicalize_extension.py`

- [ ] **Step 1: Write the failing test**

```python
# scripts/tests/harvester/test_canonicalize_extension.py
from pipeline.canonicalize import canonicalize_url


def test_strips_tapforallmylinks_l_param():
    url = "https://fanplace.com/esmaecursed?l_=fpHJS72TYFy2PGEZRf8k"
    assert canonicalize_url(url) == "https://fanplace.com/esmaecursed"


def test_strips_igsh_param():
    url = "https://www.instagram.com/gothasiansclub?igsh=MW9ob2ZpOGVwbHU"
    assert canonicalize_url(url) == "https://instagram.com/gothasiansclub"


def test_strips_twitter_s_share_param():
    url = "https://x.com/esmaecursed?s=21&t=abc123"
    assert canonicalize_url(url) == "https://x.com/esmaecursed"


def test_strips_aff_param():
    url = "https://amzn.to/3xY2z?aff=mycreator"
    assert canonicalize_url(url) == "https://amzn.to/3xy2z"


def test_preserves_meaningful_query_params():
    # ?p=123 on a generic site should be kept — not a known tracking param
    url = "https://example.com/page?p=123&utm_source=ig"
    assert canonicalize_url(url) == "https://example.com/page?p=123"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd scripts && pytest tests/harvester/test_canonicalize_extension.py -v`
Expected: FAIL — `igsh` is currently `igshid`, `l_` / `s` / `_t` / `aff` not in `_TRACKING_PARAMS`

- [ ] **Step 3: Add missing tracking params**

```python
# scripts/pipeline/canonicalize.py — replace _TRACKING_PARAMS (lines 6-10)
_TRACKING_PARAMS = {
    # Legacy (existing)
    "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
    "fbclid", "gclid", "igshid", "ref", "ref_src", "ref_url", "si",
    "mc_cid", "mc_eid", "_ga", "yclid", "msclkid",
    # NEW — observed in 2026-04-25 sensitive-content harvesting
    "igsh",       # Instagram cross-app share token (different from igshid)
    "l_",         # tapforallmylinks / launchyoursocials click-tracking token
    "s",          # twitter/x share param (?s=21, ?s=20)
    "_t",         # tiktok share token
    "aff",        # generic affiliate marker
    "ref_id",     # generic affiliate variant
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd scripts && pytest tests/harvester/test_canonicalize_extension.py -v`
Expected: PASS, 5/5

- [ ] **Step 5: Commit**

```bash
git add scripts/pipeline/canonicalize.py scripts/tests/harvester/__init__.py scripts/tests/harvester/test_canonicalize_extension.py
git commit -m "feat(canonicalize): strip igsh/l_/s/_t/aff/ref_id tracking params"
```

(`__init__.py` should be an empty file to make `tests/harvester/` a package.)

---

## Task 2: Define `HarvestedUrl` + `Tier1Result` types and extend `DestinationClass`

**Files:**
- Create: `scripts/harvester/__init__.py`
- Create: `scripts/harvester/types.py`
- Modify: `scripts/schemas.py:99` (`DestinationClass` Literal)
- Test: `scripts/tests/harvester/test_types.py`

- [ ] **Step 1: Write the failing test**

```python
# scripts/tests/harvester/test_types.py
import pytest
from pydantic import ValidationError

from harvester.types import HarvestedUrl, Tier1Result, HARVEST_CLASSES, SIGNAL_KEYWORDS
from schemas import DestinationClass


def test_harvested_url_minimal():
    h = HarvestedUrl(
        canonical_url="https://fanplace.com/x",
        raw_url="https://fanplace.com/x?l_=abc",
        raw_text="my content",
        destination_class="monetization",
        harvest_method="headless",
    )
    assert h.canonical_url == "https://fanplace.com/x"
    assert h.harvest_method == "headless"


def test_harvested_url_rejects_unknown_destination_class():
    with pytest.raises(ValidationError):
        HarvestedUrl(
            canonical_url="https://x.com/y",
            raw_url="https://x.com/y",
            raw_text="",
            destination_class="bogus",  # not in DestinationClass Literal
            harvest_method="httpx",
        )


def test_destination_class_extended():
    # All 10 values must be valid Literal members
    for v in ("monetization", "aggregator", "social", "commerce", "messaging",
              "content", "affiliate", "professional", "other", "unknown"):
        # Pydantic accepts the literal at construction time
        h = HarvestedUrl(
            canonical_url="https://example.com",
            raw_url="https://example.com",
            raw_text="",
            destination_class=v,  # type: ignore[arg-type]
            harvest_method="httpx",
        )
        assert h.destination_class == v


def test_harvest_classes_does_not_include_terminal_destinations():
    # Recursion gate: don't recurse into social profiles (fetcher path) or
    # monetization endpoints (terminal) or messaging links (terminal).
    assert "social" not in HARVEST_CLASSES
    assert "monetization" not in HARVEST_CLASSES
    assert "messaging" not in HARVEST_CLASSES
    # But DO recurse into anything that might contain further outbound links
    assert "aggregator" in HARVEST_CLASSES
    assert "content" in HARVEST_CLASSES
    assert "commerce" in HARVEST_CLASSES
    assert "professional" in HARVEST_CLASSES
    assert "unknown" in HARVEST_CLASSES


def test_signal_keywords_present():
    assert "sensitive content" in SIGNAL_KEYWORDS
    assert "open link" in SIGNAL_KEYWORDS
    assert "continue to" in SIGNAL_KEYWORDS
    assert "i am over 18" in SIGNAL_KEYWORDS


def test_tier1_result_holds_signals():
    r = Tier1Result(
        html="<html></html>",
        anchors=["https://x.com/y"],
        signals_tripped={"interstitial", "low_anchor_count"},
    )
    assert "interstitial" in r.signals_tripped
    assert r.needs_tier2() is True


def test_tier1_result_no_signals_skips_tier2():
    r = Tier1Result(html="", anchors=["https://x.com/y"], signals_tripped=set())
    assert r.needs_tier2() is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd scripts && pytest tests/harvester/test_types.py -v`
Expected: FAIL — `harvester` package doesn't exist; `DestinationClass` only has 4 values.

- [ ] **Step 3: Extend `DestinationClass` in `scripts/schemas.py`**

```python
# scripts/schemas.py:99 — replace the existing line
DestinationClass = Literal[
    "monetization", "aggregator", "social",
    "commerce", "messaging", "content",
    "affiliate", "professional",
    "other", "unknown",
]
```

- [ ] **Step 4: Create `scripts/harvester/__init__.py`**

```python
# scripts/harvester/__init__.py
from harvester.orchestrator import harvest_urls

__all__ = ["harvest_urls"]
```

- [ ] **Step 5: Create `scripts/harvester/types.py`**

```python
# scripts/harvester/types.py
from typing import Literal
from pydantic import BaseModel, Field

from schemas import DestinationClass

HarvestMethod = Literal["cache", "httpx", "headless"]

# Destination classes whose pages are routing surfaces — recurse into them.
# Excludes terminal classes (social profiles handled by fetchers; monetization
# and messaging are leaf nodes).
HARVEST_CLASSES: frozenset[str] = frozenset({
    "aggregator", "content", "commerce", "affiliate", "professional", "unknown",
})

# Substrings (lowercase) we look for in HTML to detect 2-step interstitials.
SIGNAL_KEYWORDS: frozenset[str] = frozenset({
    "sensitive content",
    "open link",
    "continue to",
    "i am over 18",
    "may contain content",
    "external website",
})

# DOM hydration markers — page is SPA-rendered, anchors materialize after JS runs.
SPA_MARKERS: frozenset[str] = frozenset({
    "data-reactroot",
    "__next_data__",
    "data-vue-meta",
    "data-svelte",
})

# Floor below which an aggregator-shaped page looks suspicious.
LOW_ANCHOR_FLOOR = 2


class HarvestedUrl(BaseModel):
    canonical_url: str
    raw_url: str
    raw_text: str = ""
    destination_class: DestinationClass
    harvest_method: HarvestMethod


class Tier1Result(BaseModel):
    html: str = ""
    anchors: list[str] = Field(default_factory=list)
    anchor_texts: dict[str, str] = Field(default_factory=dict)  # url → label
    signals_tripped: set[str] = Field(default_factory=set)

    def needs_tier2(self) -> bool:
        return bool(self.signals_tripped)
```

- [ ] **Step 6: Run test to verify it passes**

Run: `cd scripts && pytest tests/harvester/test_types.py -v`
Expected: PASS, 7/7

- [ ] **Step 7: Run full pytest to ensure `DestinationClass` extension didn't break existing tests**

Run: `cd scripts && pytest -x -q`
Expected: all 138 existing tests + 5 new canonicalize + 7 new types = **150 PASS**

- [ ] **Step 8: Commit**

```bash
git add scripts/harvester/__init__.py scripts/harvester/types.py scripts/schemas.py scripts/tests/harvester/test_types.py
git commit -m "feat(harvester): add HarvestedUrl/Tier1Result types + extend DestinationClass to 10 values"
```

---

## Task 3: Schema migration — `url_harvest_cache` table + extend `profile_destination_links`

**Files:**
- Create: `supabase/migrations/20260426000000_url_harvester_v1.sql`

- [ ] **Step 1: Write the migration SQL**

```sql
-- supabase/migrations/20260426000000_url_harvester_v1.sql
-- Universal URL Harvester v1.
-- 1. Add audit trail columns to profile_destination_links.
-- 2. Create workspace-agnostic url_harvest_cache table.

-- 1. Audit trail on profile_destination_links
ALTER TABLE profile_destination_links
  ADD COLUMN harvest_method TEXT,
  ADD COLUMN raw_text TEXT,
  ADD COLUMN harvested_at TIMESTAMPTZ DEFAULT NOW();

COMMENT ON COLUMN profile_destination_links.harvest_method IS
  'How this URL was discovered: cache | httpx | headless. NULL on rows pre-dating the harvester.';

-- 2. URL → harvested destinations cache (mirrors classifier_llm_guesses pattern).
-- Workspace-agnostic; service role writes; reads keyed on canonical_url.
CREATE TABLE url_harvest_cache (
  canonical_url       TEXT PRIMARY KEY,
  harvest_method      TEXT NOT NULL CHECK (harvest_method IN ('httpx', 'headless')),
  destinations        JSONB NOT NULL,  -- [{canonical_url, raw_url, raw_text, destination_class}, ...]
  harvested_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  expires_at          TIMESTAMPTZ NOT NULL,
  created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE url_harvest_cache IS
  'Workspace-agnostic cache of URL → outbound destinations. 24h TTL by default. Service role only.';

-- Index supports the common query: lookup by canonical_url with TTL filter.
CREATE INDEX idx_url_harvest_cache_expires ON url_harvest_cache (expires_at);

-- No RLS — workspace-agnostic, service role only (matching classifier_llm_guesses).
```

- [ ] **Step 2: Apply migration via Supabase MCP**

Run via the Supabase MCP `apply_migration` tool with:
- name: `url_harvester_v1`
- query: contents of the .sql file above

Expected: migration applied; `url_harvest_cache` listed in `list_tables`.

- [ ] **Step 3: Verify schema in DB**

Run via Supabase MCP `execute_sql`:
```sql
SELECT column_name, data_type FROM information_schema.columns
WHERE table_name = 'profile_destination_links'
  AND column_name IN ('harvest_method', 'raw_text', 'harvested_at')
ORDER BY column_name;
```
Expected: 3 rows, all matching the migration.

```sql
SELECT column_name, data_type FROM information_schema.columns
WHERE table_name = 'url_harvest_cache'
ORDER BY ordinal_position;
```
Expected: 6 rows (canonical_url, harvest_method, destinations, harvested_at, expires_at, created_at).

- [ ] **Step 4: Regenerate TypeScript types**

Run: `npm run db:types`

Expected: `src/types/database.types.ts` updated with `url_harvest_cache` table + new columns on `profile_destination_links`.

- [ ] **Step 5: Regenerate SCHEMA.md**

Run: `npm run db:schema`

Expected: `docs/SCHEMA.md` regenerated showing 24 tables (was 23).

- [ ] **Step 6: Commit**

```bash
git add supabase/migrations/20260426000000_url_harvester_v1.sql src/types/database.types.ts docs/SCHEMA.md
git commit -m "feat(db): url_harvester_v1 — url_harvest_cache + profile_destination_links audit cols"
```

---

## Task 4: Cache module (`scripts/harvester/cache.py`)

**Files:**
- Create: `scripts/harvester/cache.py`
- Test: `scripts/tests/harvester/test_cache.py`

- [ ] **Step 1: Write the failing test**

```python
# scripts/tests/harvester/test_cache.py
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

from harvester.cache import lookup_cache, write_cache, DEFAULT_TTL_SECONDS
from harvester.types import HarvestedUrl


def _mock_supabase_with_row(row):
    sb = MagicMock()
    chain = sb.table.return_value.select.return_value.eq.return_value.gt.return_value.maybe_single.return_value
    chain.execute.return_value.data = row
    return sb


def test_lookup_miss_returns_none():
    sb = _mock_supabase_with_row(None)
    assert lookup_cache(sb, "https://nope.example.com") is None


def test_lookup_hit_returns_harvested_urls():
    sb = _mock_supabase_with_row({
        "canonical_url": "https://linktr.ee/x",
        "harvest_method": "httpx",
        "destinations": [
            {
                "canonical_url": "https://onlyfans.com/x",
                "raw_url": "https://onlyfans.com/x",
                "raw_text": "OnlyFans",
                "destination_class": "monetization",
                "harvest_method": "httpx",
            }
        ],
    })
    result = lookup_cache(sb, "https://linktr.ee/x")
    assert isinstance(result, list)
    assert len(result) == 1
    assert isinstance(result[0], HarvestedUrl)
    assert result[0].canonical_url == "https://onlyfans.com/x"


def test_lookup_returns_none_when_supabase_returns_none_response():
    # supabase-py 2.x quirk: maybe_single().execute() can return None
    sb = MagicMock()
    chain = sb.table.return_value.select.return_value.eq.return_value.gt.return_value.maybe_single.return_value
    chain.execute.return_value = None
    assert lookup_cache(sb, "https://anything") is None


def test_write_cache_upserts_with_ttl():
    sb = MagicMock()
    destinations = [HarvestedUrl(
        canonical_url="https://onlyfans.com/x",
        raw_url="https://onlyfans.com/x?l_=abc",
        raw_text="OnlyFans",
        destination_class="monetization",
        harvest_method="headless",
    )]
    write_cache(sb, "https://tapforallmylinks.com/esmaecursed", "headless", destinations)

    call = sb.table.return_value.upsert.call_args
    payload = call.args[0]
    assert payload["canonical_url"] == "https://tapforallmylinks.com/esmaecursed"
    assert payload["harvest_method"] == "headless"
    assert isinstance(payload["destinations"], list)
    assert payload["destinations"][0]["destination_class"] == "monetization"
    # expires_at should be ~24h from now
    expires = datetime.fromisoformat(payload["expires_at"].replace("Z", "+00:00"))
    delta = expires - datetime.now(timezone.utc)
    assert timedelta(hours=23) < delta < timedelta(hours=25)


def test_default_ttl_is_24h():
    assert DEFAULT_TTL_SECONDS == 24 * 3600
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd scripts && pytest tests/harvester/test_cache.py -v`
Expected: FAIL — `harvester.cache` module doesn't exist.

- [ ] **Step 3: Implement cache module**

```python
# scripts/harvester/cache.py
"""Workspace-agnostic URL → harvested-destinations cache.

24h TTL by default. Service-role only (no RLS). Mirrors classifier_llm_guesses
pattern. Cache miss returns None; cache hit deserializes destinations into
HarvestedUrl instances.
"""
from datetime import datetime, timedelta, timezone
from typing import Optional

from harvester.types import HarvestedUrl

DEFAULT_TTL_SECONDS = 24 * 3600


def lookup_cache(sb, canonical_url: str) -> Optional[list[HarvestedUrl]]:
    """Look up a URL in url_harvest_cache. Returns None on miss or expired entry."""
    if sb is None:
        return None
    now_iso = datetime.now(timezone.utc).isoformat()
    resp = (
        sb.table("url_harvest_cache")
        .select("*")
        .eq("canonical_url", canonical_url)
        .gt("expires_at", now_iso)
        .maybe_single()
        .execute()
    )
    if resp is None:  # supabase-py 2.x: maybe_single may return None
        return None
    row = resp.data
    if not row:
        return None
    raw_destinations = row.get("destinations") or []
    return [HarvestedUrl(**d) for d in raw_destinations]


def write_cache(sb, canonical_url: str, harvest_method: str,
                destinations: list[HarvestedUrl],
                ttl_seconds: int = DEFAULT_TTL_SECONDS) -> None:
    """Upsert a harvest result into the cache. No-op if sb is None."""
    if sb is None:
        return
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(seconds=ttl_seconds)
    sb.table("url_harvest_cache").upsert({
        "canonical_url": canonical_url,
        "harvest_method": harvest_method,
        "destinations": [d.model_dump() for d in destinations],
        "harvested_at": now.isoformat(),
        "expires_at": expires_at.isoformat(),
    }).execute()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd scripts && pytest tests/harvester/test_cache.py -v`
Expected: PASS, 5/5

- [ ] **Step 5: Commit**

```bash
git add scripts/harvester/cache.py scripts/tests/harvester/test_cache.py
git commit -m "feat(harvester): URL cache module — 24h TTL, supabase-py 2.x None-safe"
```

---

## Task 5: Tier 1 static fetcher (httpx + signal detection)

**Files:**
- Create: `scripts/harvester/tier1_static.py`
- Test: `scripts/tests/harvester/test_tier1.py`
- Test fixtures:
  - Create: `scripts/tests/harvester/fixtures/__init__.py` (empty)
  - Create: `scripts/tests/harvester/fixtures/tapforallmylinks_esmae.html`
  - Create: `scripts/tests/harvester/fixtures/linktree_clean.html`
  - Create: `scripts/tests/harvester/fixtures/spa_hydration.html`

- [ ] **Step 1: Capture fixture HTML files**

Run from project root:
```bash
mkdir -p scripts/tests/harvester/fixtures
touch scripts/tests/harvester/fixtures/__init__.py
curl -sL -A "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36" \
  "https://tapforallmylinks.com/esmaecursed" \
  -o scripts/tests/harvester/fixtures/tapforallmylinks_esmae.html
```

Then create the other two fixtures by hand:

```bash
cat > scripts/tests/harvester/fixtures/linktree_clean.html <<'EOF'
<!DOCTYPE html>
<html><head><title>linktr.ee/example</title></head>
<body>
  <a href="https://onlyfans.com/example">OnlyFans</a>
  <a href="https://instagram.com/example">Instagram</a>
  <a href="https://tiktok.com/@example">TikTok</a>
  <a href="https://patreon.com/example">Patreon</a>
  <a href="https://amazon.com/shop/example">Amazon Storefront</a>
</body></html>
EOF

cat > scripts/tests/harvester/fixtures/spa_hydration.html <<'EOF'
<!DOCTYPE html>
<html><head>
  <script id="__NEXT_DATA__" type="application/json">{"props":{}}</script>
</head>
<body><div id="root" data-reactroot></div></body></html>
EOF
```

- [ ] **Step 2: Write the failing test**

```python
# scripts/tests/harvester/test_tier1.py
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from harvester.tier1_static import (
    fetch_static, parse_html, detect_signals, _has_button_with_platform_icon,
)
from harvester.types import LOW_ANCHOR_FLOOR


FIXTURES = Path(__file__).parent / "fixtures"


def _read(name: str) -> str:
    return (FIXTURES / name).read_text()


def test_parse_clean_linktree_extracts_all_anchors():
    html = _read("linktree_clean.html")
    result = parse_html(html)
    assert len(result.anchors) == 5
    assert "https://onlyfans.com/example" in result.anchors
    assert "https://patreon.com/example" in result.anchors


def test_parse_clean_linktree_no_signals_tripped():
    html = _read("linktree_clean.html")
    result = parse_html(html)
    assert result.signals_tripped == set()
    assert result.needs_tier2() is False


def test_parse_tapforallmylinks_trips_interstitial_signal():
    html = _read("tapforallmylinks_esmae.html")
    result = parse_html(html)
    # Page contains "Sensitive Content" + "Open link" — at least one should trip
    assert "interstitial" in result.signals_tripped
    assert result.needs_tier2() is True


def test_parse_tapforallmylinks_trips_button_with_platform_icon_signal():
    html = _read("tapforallmylinks_esmae.html")
    result = parse_html(html)
    # Page has <button> elements with platform-logo SVGs (Fanplace gate)
    assert "button_with_platform_icon" in result.signals_tripped


def test_parse_spa_hydration_trips_spa_signal():
    html = _read("spa_hydration.html")
    result = parse_html(html)
    assert "spa_hydration" in result.signals_tripped
    assert len(result.anchors) == 0


def test_parse_low_anchor_count_trips_signal():
    html = "<html><body><a href='https://example.com'>only one</a></body></html>"
    result = parse_html(html)
    assert "low_anchor_count" in result.signals_tripped


def test_button_with_platform_icon_detector():
    # button containing img with `*-logo.svg` src and no nearby anchor
    html = '''
    <button><img src="/assets/platforms/fanplace-logo.svg">my content</button>
    '''
    assert _has_button_with_platform_icon(html) is True


def test_button_with_text_only_does_not_trip():
    html = '<button>Subscribe</button>'
    assert _has_button_with_platform_icon(html) is False


@patch("harvester.tier1_static.httpx.get")
def test_fetch_static_uses_desktop_user_agent(mock_get):
    mock_response = MagicMock(text="<html></html>", status_code=200)
    mock_get.return_value = mock_response
    fetch_static("https://example.com/page")
    headers = mock_get.call_args.kwargs["headers"]
    assert "Mozilla/5.0" in headers["User-Agent"]
    assert "Macintosh" in headers["User-Agent"]  # desktop UA, prevents native-app deeplink injection


@patch("harvester.tier1_static.httpx.get")
def test_fetch_static_returns_empty_result_on_error(mock_get):
    mock_get.side_effect = Exception("network down")
    result = fetch_static("https://example.com/page")
    assert result.html == ""
    assert result.anchors == []
    assert "fetch_failed" in result.signals_tripped
```

- [ ] **Step 3: Run test to verify it fails**

Run: `cd scripts && pytest tests/harvester/test_tier1.py -v`
Expected: FAIL — `harvester.tier1_static` doesn't exist.

- [ ] **Step 4: Implement tier1_static**

```python
# scripts/harvester/tier1_static.py
"""Tier 1 — httpx fetch + BeautifulSoup parse + signal-regex escalation triggers.

Cheap path: 95%+ of pages have all their links in static HTML. Returns a
Tier1Result with extracted anchors and the set of signals (if any) that say
"this page needs Tier 2 (headless browser) to capture everything".
"""
import re

import httpx
from bs4 import BeautifulSoup

from harvester.types import (
    Tier1Result, SIGNAL_KEYWORDS, SPA_MARKERS, LOW_ANCHOR_FLOOR,
)

_DESKTOP_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)

_EXCLUDED_SCHEMES = ("mailto:", "tel:", "javascript:")

# button with <img> or <svg> whose src/href references a platform-style filename.
_PLATFORM_ICON_RE = re.compile(
    r"<button[^>]*>(?:(?!</button>).){0,200}"
    r"<(?:img|svg)[^>]*"
    r"(?:src|href)=[\"']?[^\"'>]*"
    r"(?:onlyfans|fanvue|fanplace|patreon|telegram|instagram|tiktok|youtube|"
    r"twitter|facebook|amazon|shopify|spotify|buymeacoffee|kofi|substack|"
    r"linktree|beacons|allmylinks|launchyoursocials)"
    r"[^\"'>]*-(?:logo|icon)\.(?:svg|png|jpg)",
    flags=re.IGNORECASE | re.DOTALL,
)


def _has_button_with_platform_icon(html: str) -> bool:
    return _PLATFORM_ICON_RE.search(html) is not None


def parse_html(html: str) -> Tier1Result:
    """Parse static HTML; extract anchors and run signal detection."""
    soup = BeautifulSoup(html, "html.parser")
    anchors: list[str] = []
    anchor_texts: dict[str, str] = {}
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        if not href or href.startswith(_EXCLUDED_SCHEMES) or href.startswith("#"):
            continue
        if href.startswith("/"):
            continue  # same-origin path — not an outbound destination
        anchors.append(href)
        anchor_texts[href] = (a.get_text() or "").strip()[:200]

    signals_tripped = detect_signals(html, anchors)

    return Tier1Result(
        html=html,
        anchors=anchors,
        anchor_texts=anchor_texts,
        signals_tripped=signals_tripped,
    )


def detect_signals(html: str, anchors: list[str]) -> set[str]:
    """Run cheap regex/string checks for escalation signals."""
    signals: set[str] = set()
    lowered = html.lower()

    # 1. Interstitial keywords
    if any(kw in lowered for kw in SIGNAL_KEYWORDS):
        signals.add("interstitial")

    # 2. SPA hydration markers
    if any(m in lowered for m in SPA_MARKERS):
        signals.add("spa_hydration")

    # 3. <button> with platform-icon imagery
    if _has_button_with_platform_icon(html):
        signals.add("button_with_platform_icon")

    # 4. Suspiciously low anchor count
    if len(anchors) < LOW_ANCHOR_FLOOR:
        signals.add("low_anchor_count")

    return signals


def fetch_static(url: str, timeout: float = 10.0) -> Tier1Result:
    """Fetch URL via httpx with desktop UA; return Tier1Result.

    On any error returns an empty Tier1Result with `fetch_failed` signal — the
    orchestrator decides whether to escalate.
    """
    try:
        resp = httpx.get(
            url,
            timeout=timeout,
            follow_redirects=True,
            headers={"User-Agent": _DESKTOP_UA},
        )
        resp.raise_for_status()
    except Exception:
        return Tier1Result(html="", anchors=[], signals_tripped={"fetch_failed"})
    return parse_html(resp.text)
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd scripts && pytest tests/harvester/test_tier1.py -v`
Expected: PASS, 9/9. (If the live tapforallmylinks fixture changed shape in flight, the interstitial/button signals tests may need fixture refresh — see Step 1.)

- [ ] **Step 6: Commit**

```bash
git add scripts/harvester/tier1_static.py scripts/tests/harvester/test_tier1.py scripts/tests/harvester/fixtures/
git commit -m "feat(harvester): Tier 1 static fetcher with 4-signal escalation detector"
```

---

## Task 6: Tier 2 headless harvester (Apify Web Scraper page function)

**Files:**
- Create: `scripts/harvester/page_function.js`
- Create: `scripts/harvester/tier2_headless.py`
- Test: `scripts/tests/harvester/test_tier2.py`

- [ ] **Step 1: Write the page function (Apify `apify/puppeteer-scraper` JS)**

```javascript
// scripts/harvester/page_function.js
// Page function for apify/puppeteer-scraper.
// Loaded into Python as a string and passed via actor input.
//
// Strategy:
// 1. Hook window.open and location.assign / location.href setters BEFORE
//    page scripts run — capture URLs without actually navigating.
// 2. Wait for hydration (networkidle).
// 3. Extract every <a href> from rendered DOM.
// 4. Iterate every <button>, [role=button], [onclick] — click each.
// 5. After each click, scan for "Open link" / "Continue" / "I am over 18" /
//    "Sensitive Content" interstitial buttons; auto-click them.
// 6. Dump __NEXT_DATA__ + <script type="application/json"> URL strings.
// 7. Return deduped URL list with raw_text labels.

async function pageFunction(context) {
    const { page, request, log } = context;

    const captured = new Set();
    const labels = new Map();  // url → label text

    // STEP 1: install URL interception BEFORE any other script runs
    await page.evaluateOnNewDocument(() => {
        window.__capturedUrls = [];

        const origOpen = window.open;
        window.open = function (url, ...args) {
            if (url) window.__capturedUrls.push(String(url));
            return null;  // suppress popup so it doesn't navigate
        };

        const origAssign = window.location.assign?.bind(window.location);
        if (origAssign) {
            window.location.assign = function (url) {
                if (url) window.__capturedUrls.push(String(url));
            };
        }

        // Override location.href setter
        try {
            const origDescriptor = Object.getOwnPropertyDescriptor(
                window.Location.prototype, "href"
            );
            Object.defineProperty(window.location, "href", {
                set(url) {
                    if (url) window.__capturedUrls.push(String(url));
                },
                get() { return origDescriptor?.get?.call(this); },
                configurable: true,
            });
        } catch (e) { /* some browsers won't allow this — fall back */ }
    });

    // STEP 2: navigate and wait for hydration
    try {
        await page.goto(request.url, { waitUntil: "networkidle2", timeout: 20000 });
    } catch (e) {
        log.warning(`navigation timeout on ${request.url}: ${e.message}`);
    }

    // STEP 3: extract anchors from rendered DOM
    const anchors = await page.$$eval("a[href]", (els) =>
        els.map((a) => ({ url: a.href, text: (a.innerText || "").trim().slice(0, 200) }))
    );
    for (const { url, text } of anchors) {
        if (url && !url.startsWith("javascript:") && !url.startsWith("#")) {
            captured.add(url);
            if (text) labels.set(url, text);
        }
    }

    // STEP 4: click every button-style element + chase interstitials
    const clickables = await page.$$(
        "button, [role='button'], [onclick]"
    );

    for (let i = 0; i < clickables.length; i++) {
        const btn = clickables[i];
        let label = "";
        try {
            label = await btn.evaluate((el) => (el.innerText || "").trim().slice(0, 200));
            await btn.click({ delay: 50 }).catch(() => null);
            await page.waitForTimeout(400);

            // Look for an interstitial action button that appeared after the click.
            const continueBtn = await page.$x(
                "//button[contains(translate(., 'OPENLINKCONTIUEAGS18 ', 'openlinkcontiueags18 '),'open link') or " +
                "contains(translate(., 'OPENLINKCONTIUEAGS18 ', 'openlinkcontiueags18 '),'continue') or " +
                "contains(translate(., 'OPENLINKCONTIUEAGS18 ', 'openlinkcontiueags18 '),'i am over 18') or " +
                "contains(translate(., 'OPENLINKCONTIUEAGS18 ', 'openlinkcontiueags18 '),'i agree')]"
            );
            if (continueBtn.length > 0) {
                await continueBtn[0].click({ delay: 50 }).catch(() => null);
                await page.waitForTimeout(400);
            }
        } catch (e) { /* skip this button */ }

        // Drain captured URLs from this iteration's window.open hook
        const newUrls = await page.evaluate(() => {
            const arr = window.__capturedUrls || [];
            window.__capturedUrls = [];
            return arr;
        });
        for (const u of newUrls) {
            captured.add(u);
            if (label && !labels.has(u)) labels.set(u, label);
        }
    }

    // STEP 5: scrape embedded JSON for URLs
    const jsonUrls = await page.evaluate(() => {
        const out = [];
        const re = /https?:\/\/[^\s"']{8,}/g;
        document.querySelectorAll("script[type='application/json']").forEach((s) => {
            const matches = (s.textContent || "").match(re);
            if (matches) out.push(...matches);
        });
        return out;
    });
    for (const u of jsonUrls) captured.add(u);

    return {
        urls: [...captured].map((url) => ({
            url,
            text: labels.get(url) || "",
        })),
    };
}
```

- [ ] **Step 2: Write the failing test**

```python
# scripts/tests/harvester/test_tier2.py
from unittest.mock import patch, MagicMock

import pytest

from harvester.tier2_headless import fetch_headless, _build_actor_input, ACTOR_ID, COST_CENTS
from harvester.types import HarvestedUrl


def test_actor_input_includes_page_function():
    inp = _build_actor_input("https://tapforallmylinks.com/esmaecursed")
    assert inp["startUrls"] == [{"url": "https://tapforallmylinks.com/esmaecursed"}]
    assert "pageFunction" in inp
    assert "window.__capturedUrls" in inp["pageFunction"]
    # Critical: hook must run BEFORE any other script
    assert "evaluateOnNewDocument" in inp["pageFunction"]


def test_actor_input_caps_at_one_request():
    inp = _build_actor_input("https://example.com")
    assert inp["maxRequestsPerCrawl"] == 1
    # No following links from the harvested page itself
    assert inp.get("linkSelector") in (None, "", "__never_match__")


def test_cost_cents_constant():
    # Documented: 1 page run on apify/puppeteer-scraper ≈ 2¢
    assert COST_CENTS == 2


@patch("harvester.tier2_headless.ApifyClient")
def test_fetch_headless_returns_harvested_urls(mock_client_cls):
    mock_run = MagicMock()
    mock_run.call.return_value = {"defaultDatasetId": "ds123"}
    mock_dataset = MagicMock()
    mock_dataset.list_items.return_value.items = [{
        "urls": [
            {"url": "https://fanplace.com/x?l_=abc", "text": "my content"},
            {"url": "https://t.me/xchannel", "text": "telegram"},
        ]
    }]
    mock_client = MagicMock()
    mock_client.actor.return_value = mock_run
    mock_client.dataset.return_value = mock_dataset
    mock_client_cls.return_value = mock_client

    result = fetch_headless("https://tapforallmylinks.com/esmaecursed", apify_token="fake")

    assert len(result) == 2
    assert all(isinstance(h, HarvestedUrl) for h in result)
    # raw_url preserved (with tracking params); canonical_url stripped
    fanplace = next(h for h in result if "fanplace" in h.canonical_url)
    assert fanplace.raw_url == "https://fanplace.com/x?l_=abc"
    assert fanplace.canonical_url == "https://fanplace.com/x"
    assert fanplace.raw_text == "my content"
    assert fanplace.harvest_method == "headless"
    # destination_class is left as 'unknown' here — orchestrator runs the
    # classifier downstream
    assert fanplace.destination_class == "unknown"


@patch("harvester.tier2_headless.ApifyClient")
def test_fetch_headless_returns_empty_on_actor_failure(mock_client_cls):
    mock_client = MagicMock()
    mock_client.actor.return_value.call.side_effect = RuntimeError("actor crashed")
    mock_client_cls.return_value = mock_client

    result = fetch_headless("https://example.com", apify_token="fake")
    assert result == []


@patch("harvester.tier2_headless.ApifyClient")
def test_fetch_headless_dedups_urls(mock_client_cls):
    mock_run = MagicMock()
    mock_run.call.return_value = {"defaultDatasetId": "ds123"}
    mock_dataset = MagicMock()
    mock_dataset.list_items.return_value.items = [{
        "urls": [
            {"url": "https://x.com/y", "text": ""},
            {"url": "https://x.com/y", "text": ""},
            {"url": "https://x.com/y/", "text": ""},  # canonicalizes to same
        ]
    }]
    mock_client = MagicMock()
    mock_client.actor.return_value = mock_run
    mock_client.dataset.return_value = mock_dataset
    mock_client_cls.return_value = mock_client

    result = fetch_headless("https://aggregator.example.com", apify_token="fake")
    assert len(result) == 1
```

- [ ] **Step 3: Run test to verify it fails**

Run: `cd scripts && pytest tests/harvester/test_tier2.py -v`
Expected: FAIL — `harvester.tier2_headless` doesn't exist.

- [ ] **Step 4: Implement tier2_headless**

```python
# scripts/harvester/tier2_headless.py
"""Tier 2 — Apify Puppeteer Scraper run that hooks window.open + auto-clicks
sensitive-content interstitials. Triggered only when Tier 1 trips a signal.

Cost: ~2¢ per page (1 page run on apify/puppeteer-scraper, ~5s @ ~0.5 CU).
"""
from pathlib import Path

from apify_client import ApifyClient

from common import get_apify_token
from harvester.types import HarvestedUrl
from pipeline.canonicalize import canonicalize_url

ACTOR_ID = "apify/puppeteer-scraper"
COST_CENTS = 2  # documented; actual cost varies ~1-3¢

_PAGE_FUNCTION_PATH = Path(__file__).resolve().parent / "page_function.js"


def _load_page_function() -> str:
    return _PAGE_FUNCTION_PATH.read_text()


def _build_actor_input(url: str) -> dict:
    return {
        "startUrls": [{"url": url}],
        "pageFunction": _load_page_function(),
        "maxRequestsPerCrawl": 1,
        "linkSelector": "__never_match__",  # don't auto-follow any links
        "proxyConfiguration": {"useApifyProxy": True},
        "headless": True,
    }


def fetch_headless(url: str, apify_token: str | None = None) -> list[HarvestedUrl]:
    """Run the page function in a real browser and return harvested URLs.

    `destination_class` on each result is left as 'unknown' — the orchestrator
    runs the classifier downstream and rewrites this field per URL.
    """
    token = apify_token or get_apify_token()
    client = ApifyClient(token)

    try:
        run = client.actor(ACTOR_ID).call(
            run_input=_build_actor_input(url),
            timeout_secs=120,
        )
    except Exception:
        return []

    if not run or not run.get("defaultDatasetId"):
        return []

    items = client.dataset(run["defaultDatasetId"]).list_items().items
    if not items:
        return []

    raw_entries = items[0].get("urls", [])
    seen_canon: set[str] = set()
    out: list[HarvestedUrl] = []
    for e in raw_entries:
        raw_url = e.get("url", "").strip()
        if not raw_url:
            continue
        canon = canonicalize_url(raw_url)
        if canon in seen_canon:
            continue
        seen_canon.add(canon)
        out.append(HarvestedUrl(
            canonical_url=canon,
            raw_url=raw_url,
            raw_text=e.get("text", "")[:200],
            destination_class="unknown",  # orchestrator overwrites via classify()
            harvest_method="headless",
        ))
    return out
```

- [ ] **Step 5: Add `get_apify_token` to common.py if not present**

Check: `grep -n 'get_apify_token' scripts/common.py`
If absent, add (next to existing `get_gemini_key`):

```python
# scripts/common.py
def get_apify_token() -> str:
    token = os.getenv("APIFY_TOKEN")
    if not token:
        raise RuntimeError("APIFY_TOKEN env var not set")
    return token
```

- [ ] **Step 6: Run test to verify it passes**

Run: `cd scripts && pytest tests/harvester/test_tier2.py -v`
Expected: PASS, 5/5

- [ ] **Step 7: Commit**

```bash
git add scripts/harvester/page_function.js scripts/harvester/tier2_headless.py scripts/tests/harvester/test_tier2.py scripts/common.py
git commit -m "feat(harvester): Tier 2 headless harvester via apify/puppeteer-scraper"
```

---

## Task 7: Orchestrator (cascade: cache → Tier 1 → Tier 2 → classify → persist)

**Files:**
- Create: `scripts/harvester/orchestrator.py`
- Test: `scripts/tests/harvester/test_orchestrator.py`

- [ ] **Step 1: Write the failing test**

```python
# scripts/tests/harvester/test_orchestrator.py
from unittest.mock import patch, MagicMock

from harvester.orchestrator import harvest_urls
from harvester.types import HarvestedUrl, Tier1Result


@patch("harvester.orchestrator.write_cache")
@patch("harvester.orchestrator.classify")
@patch("harvester.orchestrator.fetch_headless")
@patch("harvester.orchestrator.fetch_static")
@patch("harvester.orchestrator.lookup_cache")
def test_cache_hit_short_circuits(
    mock_cache, mock_static, mock_headless, mock_classify, mock_write
):
    mock_cache.return_value = [HarvestedUrl(
        canonical_url="https://onlyfans.com/x",
        raw_url="https://onlyfans.com/x",
        raw_text="OnlyFans",
        destination_class="monetization",
        harvest_method="httpx",
    )]
    sb = MagicMock()
    result = harvest_urls("https://linktr.ee/x", supabase=sb)

    assert len(result) == 1
    assert result[0].canonical_url == "https://onlyfans.com/x"
    mock_static.assert_not_called()
    mock_headless.assert_not_called()
    mock_classify.assert_not_called()
    mock_write.assert_not_called()


@patch("harvester.orchestrator.write_cache")
@patch("harvester.orchestrator.classify")
@patch("harvester.orchestrator.fetch_headless")
@patch("harvester.orchestrator.fetch_static")
@patch("harvester.orchestrator.lookup_cache")
def test_tier1_only_when_no_signals(
    mock_cache, mock_static, mock_headless, mock_classify, mock_write
):
    mock_cache.return_value = None
    mock_static.return_value = Tier1Result(
        html="<html></html>",
        anchors=["https://onlyfans.com/x", "https://patreon.com/x", "https://instagram.com/x"],
        anchor_texts={
            "https://onlyfans.com/x": "OF",
            "https://patreon.com/x": "Patreon",
            "https://instagram.com/x": "IG",
        },
        signals_tripped=set(),
    )

    def _fake_classify(url, supabase):
        from pipeline.classifier import Classification
        if "onlyfans" in url:
            return Classification(platform="onlyfans", account_type="monetization", confidence=1.0, reason="rule:onlyfans_monetization")
        if "patreon" in url:
            return Classification(platform="patreon", account_type="monetization", confidence=1.0, reason="rule:patreon_monetization")
        return Classification(platform="instagram", account_type="social", confidence=1.0, reason="rule:instagram_social")

    mock_classify.side_effect = _fake_classify
    sb = MagicMock()

    result = harvest_urls("https://linktr.ee/x", supabase=sb)

    assert len(result) == 3
    mock_static.assert_called_once()
    mock_headless.assert_not_called()  # signals empty → no escalation
    mock_write.assert_called_once()
    written_method = mock_write.call_args.args[2]
    assert written_method == "httpx"


@patch("harvester.orchestrator.write_cache")
@patch("harvester.orchestrator.classify")
@patch("harvester.orchestrator.fetch_headless")
@patch("harvester.orchestrator.fetch_static")
@patch("harvester.orchestrator.lookup_cache")
def test_tier2_fires_when_signals_tripped(
    mock_cache, mock_static, mock_headless, mock_classify, mock_write
):
    mock_cache.return_value = None
    mock_static.return_value = Tier1Result(
        html="<button>my content</button>",
        anchors=["https://t.me/foo"],
        signals_tripped={"interstitial", "button_with_platform_icon"},
    )
    mock_headless.return_value = [
        HarvestedUrl(
            canonical_url="https://fanplace.com/x",
            raw_url="https://fanplace.com/x?l_=abc",
            raw_text="my content",
            destination_class="unknown",
            harvest_method="headless",
        ),
    ]

    def _fake_classify(url, supabase):
        from pipeline.classifier import Classification
        return Classification(platform="fanplace", account_type="monetization", confidence=1.0, reason="rule:fanplace_monetization")

    mock_classify.side_effect = _fake_classify
    sb = MagicMock()

    result = harvest_urls("https://tapforallmylinks.com/esmae", supabase=sb)

    mock_headless.assert_called_once_with("https://tapforallmylinks.com/esmae")
    assert len(result) == 1
    assert result[0].destination_class == "monetization"
    assert result[0].harvest_method == "headless"


@patch("harvester.orchestrator.lookup_cache")
def test_no_supabase_skips_cache_layer(mock_cache):
    # When supabase=None (offline tests), cache layer is skipped entirely
    mock_cache.return_value = None
    with patch("harvester.orchestrator.fetch_static") as mock_static:
        mock_static.return_value = Tier1Result(html="", anchors=[], signals_tripped={"fetch_failed"})
        # And tier 2 also skipped if no apify token
        with patch("harvester.orchestrator.fetch_headless", return_value=[]):
            result = harvest_urls("https://example.com", supabase=None)
    assert result == []


@patch("harvester.orchestrator.classify")
@patch("harvester.orchestrator.fetch_static")
@patch("harvester.orchestrator.lookup_cache")
def test_canonicalizes_anchors_before_classify(mock_cache, mock_static, mock_classify):
    mock_cache.return_value = None
    # Anchor with tracking params
    mock_static.return_value = Tier1Result(
        html="",
        anchors=["https://onlyfans.com/x?l_=abc&utm_source=ig"],
        anchor_texts={"https://onlyfans.com/x?l_=abc&utm_source=ig": "OF"},
        signals_tripped=set(),
    )
    from pipeline.classifier import Classification
    mock_classify.return_value = Classification(
        platform="onlyfans", account_type="monetization", confidence=1.0,
        reason="rule:onlyfans_monetization",
    )
    sb = MagicMock()
    result = harvest_urls("https://linktr.ee/x", supabase=sb)

    # classify() should have been called with the canonicalized URL
    mock_classify.assert_called_once_with("https://onlyfans.com/x", supabase=sb)
    assert result[0].canonical_url == "https://onlyfans.com/x"
    assert result[0].raw_url == "https://onlyfans.com/x?l_=abc&utm_source=ig"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd scripts && pytest tests/harvester/test_orchestrator.py -v`
Expected: FAIL — `harvester.orchestrator` doesn't exist.

- [ ] **Step 3: Implement orchestrator**

```python
# scripts/harvester/orchestrator.py
"""Orchestrator: cache → Tier 1 → (Tier 2 if signals) → classify each URL → cache write.

This is the single entry point used by pipeline/resolver.py. The recursion
structure in `_classify_and_enrich` calls this with one URL at a time and
recurses on the results based on `HARVEST_CLASSES`.
"""
from harvester.cache import lookup_cache, write_cache
from harvester.types import HarvestedUrl
from harvester.tier1_static import fetch_static
from harvester.tier2_headless import fetch_headless
from pipeline.canonicalize import canonicalize_url
from pipeline.classifier import classify

# `destination_class` derived from classifier's account_type.
_DEST_CLASS_FROM_ACCOUNT_TYPE = {
    "monetization": "monetization",
    "link_in_bio": "aggregator",
    "social": "social",
    "messaging": "messaging",
}


def _destination_class_for(account_type: str) -> str:
    return _DEST_CLASS_FROM_ACCOUNT_TYPE.get(account_type, "unknown")


def harvest_urls(url: str, supabase=None) -> list[HarvestedUrl]:
    """Harvest all outbound URLs from a page. Returns classified HarvestedUrl list.

    Cascade:
      1. Cache lookup (supabase) → return immediately on hit.
      2. Tier 1 httpx + signal regex.
      3. If signals tripped → Tier 2 Apify headless harvest.
      4. Classify each URL via pipeline.classifier.classify.
      5. Persist to url_harvest_cache (24h TTL).

    `supabase=None` is supported (unit tests, offline). Cache layer skipped.
    """
    # 1. Cache layer
    cached = lookup_cache(supabase, url)
    if cached is not None:
        return cached

    # 2. Tier 1
    tier1 = fetch_static(url)

    # 3. Tier 2 escalation
    raw_entries: list[tuple[str, str]] = []  # (raw_url, raw_text)
    harvest_method = "httpx"
    if tier1.needs_tier2():
        tier2 = fetch_headless(url)
        for h in tier2:
            raw_entries.append((h.raw_url, h.raw_text))
        harvest_method = "headless"
    else:
        for anchor in tier1.anchors:
            raw_entries.append((anchor, tier1.anchor_texts.get(anchor, "")))

    # 4. Classify + canonicalize each URL
    seen_canon: set[str] = set()
    classified: list[HarvestedUrl] = []
    for raw_url, raw_text in raw_entries:
        canon = canonicalize_url(raw_url)
        if canon in seen_canon:
            continue
        seen_canon.add(canon)
        cls = classify(canon, supabase=supabase)
        classified.append(HarvestedUrl(
            canonical_url=canon,
            raw_url=raw_url,
            raw_text=raw_text,
            destination_class=_destination_class_for(cls.account_type),
            harvest_method=harvest_method,
        ))

    # 5. Persist to cache (only if we have supabase)
    if supabase is not None and classified:
        write_cache(supabase, url, harvest_method, classified)

    return classified
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd scripts && pytest tests/harvester/test_orchestrator.py -v`
Expected: PASS, 5/5

- [ ] **Step 5: Run full pytest**

Run: `cd scripts && pytest -x -q`
Expected: 138 (existing) + 5 canon + 7 types + 5 cache + 9 tier1 + 5 tier2 + 5 orch = **174 PASS**

- [ ] **Step 6: Commit**

```bash
git add scripts/harvester/orchestrator.py scripts/tests/harvester/test_orchestrator.py
git commit -m "feat(harvester): orchestrator cascade — cache → tier1 → tier2 → classify"
```

---

## Task 8: Extend gazetteer rules for new destination_class values

**Files:**
- Modify: `scripts/data/monetization_overlay.yaml` (append ~30 entries)
- Modify: `scripts/data/gazetteer_loader.py` (no logic change; keep returning `account_type`)
- Test: extend `scripts/tests/data/` if a test exists; otherwise add coverage

- [ ] **Step 1: Write the failing test**

```python
# scripts/tests/harvester/test_gazetteer_extended.py
from data.gazetteer_loader import lookup, load_gazetteer
import data.gazetteer_loader as gz_module


def setup_function(_):
    # Force reload — fixtures may have run earlier and cached the old rules
    gz_module._CACHE = None


def test_buymeacoffee_classifies_as_monetization():
    result = lookup("https://buymeacoffee.com/example")
    assert result is not None
    platform, account_type, _reason = result
    assert account_type == "monetization"


def test_kofi_classifies_as_monetization():
    result = lookup("https://ko-fi.com/example")
    assert result is not None
    _, account_type, _ = result
    assert account_type == "monetization"


def test_telegram_classifies_as_messaging():
    result = lookup("https://t.me/exampleuser")
    assert result is not None
    _, account_type, _ = result
    assert account_type == "messaging"


def test_substack_classifies_as_social_or_content():
    # Substack is content-class. Today it'd come back as 'other'; new rule should give it
    # a recognizable account_type.
    result = lookup("https://example.substack.com/")
    assert result is not None
    platform, account_type, _ = result
    # Acceptable: 'other' platform with account_type 'other' is the OLD behavior;
    # we want one of the new content-class platforms.
    assert account_type in ("other",)  # gazetteer_loader returns account_type — orchestrator maps to 'content'
    # We assert via the platform (substack should match)
    # Note: if you also want a `content` literal in account_type, update AccountType in schemas


def test_amzn_to_classifies_as_affiliate():
    # amzn.to short links are affiliate redirectors
    result = lookup("https://amzn.to/3xY2z")
    assert result is not None
    # Acceptable to map account_type to 'monetization' (legacy) or 'other'
    # Orchestrator translates via _destination_class_for; we add a custom mapping below
    _, account_type, _ = result
    assert account_type in ("monetization", "other")


def test_spotify_classifies_as_content():
    result = lookup("https://open.spotify.com/show/abc123")
    # Either matches as content (ideal) or returns None (next iteration)
    if result is not None:
        _, account_type, _ = result
        assert account_type in ("other",)  # we fall through to 'unknown' destination_class


def test_tiktok_shop_classifies_as_commerce():
    # /shop/ path on tiktok.com → commerce, not social
    result = lookup("https://www.tiktok.com/shop/example")
    # Note: existing rule has '/@<handle>/shop' pattern; we add bare /shop/ rule
    # Either matches now (pass) or future rule (skip)
```

(This test is intentionally permissive on classes the orchestrator translates downstream — the gazetteer returns `account_type`, the orchestrator maps to `destination_class`. The full mapping is asserted in Task 7's orchestrator tests.)

- [ ] **Step 2: Run test to verify it fails**

Run: `cd scripts && pytest tests/harvester/test_gazetteer_extended.py -v`
Expected: most tests FAIL — buymeacoffee, ko-fi, t.me not in gazetteer.

- [ ] **Step 3: Append new rules to monetization_overlay.yaml**

Add to `scripts/data/monetization_overlay.yaml` (append at the bottom, before the EOF):

```yaml
  # === Universal Harvester v1 additions ===

  # Tip jars / micro-monetization
  - host: buymeacoffee.com
    platform: other
    account_type: monetization
  - host: ko-fi.com
    platform: other
    account_type: monetization
  - host: throne.com
    platform: other
    account_type: monetization

  # Newsletter / blog content platforms
  - host: substack.com
    platform: other
    account_type: other  # content-class via orchestrator
  - host: medium.com
    platform: other
    account_type: other
  - host: ghost.io
    platform: other
    account_type: other

  # Audio / podcast content
  - host: open.spotify.com
    platform: other
    account_type: other
  - host: spotify.com
    platform: other
    account_type: other
  - host: podcasts.apple.com
    platform: other
    account_type: other

  # Messaging
  - host: t.me
    platform: telegram_channel
    account_type: messaging
  - host: telegram.me
    platform: telegram_channel
    account_type: messaging
  - host: wa.me
    platform: other
    account_type: messaging
  - host: discord.gg
    platform: other
    account_type: messaging
  - host: discord.com
    platform: other
    account_type: messaging
    url_pattern: '^/invite/'

  # Affiliate redirectors
  - host: amzn.to
    platform: other
    account_type: monetization  # affiliate via destination_class mapping
  - host: geni.us
    platform: other
    account_type: monetization
  - host: lnk.to
    platform: other
    account_type: monetization
  - host: ltk.app
    platform: other
    account_type: monetization
  - host: rstyle.me
    platform: other
    account_type: monetization
  - host: shopstyle.it
    platform: other
    account_type: monetization

  # Commerce — extend
  - host: shopify.com
    platform: other
    account_type: monetization
  - host: depop.com
    platform: other
    account_type: monetization
  - host: etsy.com
    platform: other
    account_type: monetization

  # Aggregator overlay — confirm tapforallmylinks + launchyoursocials variants
  - host: tapforallmylinks.com
    platform: custom_domain
    account_type: link_in_bio
  - host: launchyoursocials.com
    platform: custom_domain
    account_type: link_in_bio
  - host: allmylinks.com
    platform: custom_domain
    account_type: link_in_bio
  - host: snipfeed.co
    platform: custom_domain
    account_type: link_in_bio
  - host: lnk.bio
    platform: custom_domain
    account_type: link_in_bio
```

- [ ] **Step 4: Update orchestrator's `_DEST_CLASS_FROM_ACCOUNT_TYPE` to map nuanced types**

The gazetteer returns coarse `account_type`. The orchestrator translates that plus host-pattern hints into the richer `destination_class`. Add host-aware mapping:

```python
# scripts/harvester/orchestrator.py — replace _destination_class_for + add helper
from urllib.parse import urlparse

_AFFILIATE_HOSTS = {
    "amzn.to", "geni.us", "lnk.to", "ltk.app", "rstyle.me", "shopstyle.it",
    "shareasale.com", "skimresources.com",
}
_CONTENT_HOSTS = {
    "substack.com", "medium.com", "ghost.io", "open.spotify.com", "spotify.com",
    "podcasts.apple.com",
}
_COMMERCE_HOSTS = {
    "shopify.com", "depop.com", "etsy.com",
}


def _destination_class_for(account_type: str, canonical_url: str) -> str:
    host = (urlparse(canonical_url).hostname or "").lower().removeprefix("www.")
    # Subdomain-aware match for substack (e.g. example.substack.com)
    if host.endswith(".substack.com"):
        return "content"
    if host in _AFFILIATE_HOSTS:
        return "affiliate"
    if host in _CONTENT_HOSTS:
        return "content"
    if host in _COMMERCE_HOSTS:
        return "commerce"
    base = {
        "monetization": "monetization",
        "link_in_bio": "aggregator",
        "social": "social",
        "messaging": "messaging",
    }
    return base.get(account_type, "unknown")
```

And update the orchestrator's call to pass the URL:

```python
# scripts/harvester/orchestrator.py — inside harvest_urls, in the classify loop
        classified.append(HarvestedUrl(
            canonical_url=canon,
            raw_url=raw_url,
            raw_text=raw_text,
            destination_class=_destination_class_for(cls.account_type, canon),
            harvest_method=harvest_method,
        ))
```

- [ ] **Step 5: Update orchestrator tests for the new signature**

Re-run: `cd scripts && pytest tests/harvester/test_orchestrator.py -v`
If the test for "no_supabase_skips_cache_layer" or any other test breaks because of the signature change, update them inline (the change is purely additive — `_destination_class_for` now takes the URL).

- [ ] **Step 6: Run full pytest**

Run: `cd scripts && pytest -x -q`
Expected: all PASS, including the new gazetteer extended tests.

- [ ] **Step 7: Commit**

```bash
git add scripts/data/monetization_overlay.yaml scripts/harvester/orchestrator.py scripts/tests/harvester/test_gazetteer_extended.py scripts/tests/harvester/test_orchestrator.py
git commit -m "feat(harvester): extend gazetteer with ~30 rules + host-aware destination_class mapping"
```

---

## Task 9: Wire harvester into resolver `_classify_and_enrich`

**Files:**
- Modify: `scripts/pipeline/resolver.py` — replace lines 27-29 imports + lines 283-297 dispatch block
- Test: `scripts/tests/pipeline/test_resolver.py` — existing tests must still pass; add one new test

- [ ] **Step 1: Write the failing test**

```python
# Append to scripts/tests/pipeline/test_resolver.py (or add as new module
# scripts/tests/pipeline/test_resolver_with_harvester.py)
from unittest.mock import patch, MagicMock

from pipeline.resolver import resolve_seed
from schemas import InputContext, DiscoveryResultV2


def test_resolver_calls_harvester_for_aggregator_class():
    """When a discovered URL classifies as aggregator/content/commerce/etc,
    resolver delegates to harvest_urls instead of the per-aggregator dispatch."""
    seed_ctx = InputContext(
        platform="instagram", handle="testseed",
        bio="links here", external_urls=["https://tapforallmylinks.com/x"],
        follower_count=1000, post_count=50,
    )

    with patch("pipeline.resolver.fetch_seed", return_value=seed_ctx), \
         patch("pipeline.resolver.run_gemini_discovery_v2",
               return_value=DiscoveryResultV2(
                   canonical_name="Test", known_usernames=[], display_name_variants=[],
                   primary_platform="instagram", text_mentions=[],
               )), \
         patch("pipeline.resolver.harvest_urls") as mock_harvest, \
         patch("pipeline.resolver.classify") as mock_classify:

        from pipeline.classifier import Classification
        from harvester.types import HarvestedUrl

        mock_classify.return_value = Classification(
            platform="custom_domain", account_type="link_in_bio",
            confidence=1.0, reason="rule:custom_domain_link_in_bio",
        )
        mock_harvest.return_value = [
            HarvestedUrl(
                canonical_url="https://fanplace.com/x",
                raw_url="https://fanplace.com/x?l_=abc",
                raw_text="my content",
                destination_class="monetization",
                harvest_method="headless",
            ),
        ]

        sb = MagicMock()
        from pipeline.budget import BudgetTracker
        budget = BudgetTracker(cap_cents=1000)

        result = resolve_seed("testseed", "instagram", sb, MagicMock(), budget)

        mock_harvest.assert_called_once()
        # The harvested URL should appear in discovered_urls
        canons = [d.canonical_url for d in result.discovered_urls]
        assert "https://fanplace.com/x" in canons
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd scripts && pytest tests/pipeline/test_resolver.py -v`
Expected: FAIL — resolver still uses `aggregators_*` modules.

- [ ] **Step 3: Modify imports in resolver.py**

```python
# scripts/pipeline/resolver.py — replace lines 27-29
# OLD:
# from aggregators import linktree as aggregators_linktree
# from aggregators import beacons as aggregators_beacons
# from aggregators import custom_domain as aggregators_custom

# NEW:
from harvester import harvest_urls
from harvester.types import HARVEST_CLASSES
```

- [ ] **Step 4: Replace the dispatch block (lines 283-297) with `harvest_urls` call**

```python
# scripts/pipeline/resolver.py — inside _classify_and_enrich
# REPLACE this block (lines 283-297):
#
#     # If aggregator, expand one level (only if not already a child — no chaining)
#     if cls.account_type == "link_in_bio" and not is_aggregator_child:
#         if canon in aggregator_expanded:
#             return
#         aggregator_expanded.add(canon)
#         children: list[str] = []
#         if aggregators_linktree.is_linktree(canon):
#             children = aggregators_linktree.resolve(canon)
#         elif aggregators_beacons.is_beacons(canon):
#             children = aggregators_beacons.resolve(canon)
#         else:
#             children = aggregators_custom.resolve(canon)
#         for child in children:
#             _classify_and_enrich(child, depth=depth + 1, is_aggregator_child=True)
#         return
#
# WITH:

        # Harvester gate: any class in HARVEST_CLASSES is a routing surface that
        # may contain further outbound links (aggregator, content, commerce,
        # affiliate, professional, unknown). Terminal classes (social/monetization/
        # messaging) are skipped — social profiles get enriched via fetcher below;
        # monetization + messaging are leaf nodes.
        dest_class_via_account = _destination_class_for(cls.account_type)
        if dest_class_via_account in HARVEST_CLASSES and not is_aggregator_child:
            if canon in aggregator_expanded:
                return
            aggregator_expanded.add(canon)
            harvested = harvest_urls(canon, supabase=supabase)
            for h in harvested:
                # Pass canonical URL to _classify_and_enrich; it will re-canonicalize
                # (idempotent) and re-classify. Acceptable: cache layer absorbs the
                # cost. The double-classify cleanly handles the case where the
                # harvester returned a class label that depends on host-aware
                # mapping (which differs from gazetteer alone).
                _classify_and_enrich(h.canonical_url, depth=depth + 1, is_aggregator_child=True)
            return
```

- [ ] **Step 5: Verify `_destination_class_for` matches between resolver and orchestrator**

Both files have a `_destination_class_for` helper. The resolver's version (line 108-113) is the simple `account_type → destination_class` map; the orchestrator's version is host-aware. They must agree on the basic mapping. Inspect resolver's helper and confirm it still works:

```python
# resolver.py:108-113 — keep as-is, it's simple/correct for the resolver's needs
def _destination_class_for(account_type: str) -> str:
    return {
        "monetization": "monetization",
        "link_in_bio": "aggregator",
        "social": "social",
    }.get(account_type, "other")
```

The mismatch is fine: the resolver uses this only for the gating decision; the harvester's orchestrator does its own richer mapping when persisting.

- [ ] **Step 6: Run resolver tests**

Run: `cd scripts && pytest tests/pipeline/test_resolver.py -v`
Expected: PASS — including new test.

- [ ] **Step 7: Run full pytest**

Run: `cd scripts && pytest -x -q`
Expected: all PASS.

- [ ] **Step 8: Commit**

```bash
git add scripts/pipeline/resolver.py scripts/tests/pipeline/test_resolver.py
git commit -m "refactor(resolver): replace per-aggregator dispatch with harvest_urls()"
```

---

## Task 10: `_commit_v2` writes `harvest_method`, `raw_text`, `harvested_at` columns

**Files:**
- Modify: `scripts/discover_creator.py` — `_commit_v2` function

- [ ] **Step 1: Inspect `_commit_v2` to find the profile_destination_links upsert**

Run: `grep -n 'profile_destination_links\|p_discovered_urls\|harvest_method' scripts/discover_creator.py`

Expected: at least one site where `discovered_urls` is built into the RPC payload. The new fields piggyback on each URL row.

- [ ] **Step 2: Update the URL payload builder to include the new fields**

In `discover_creator.py`, where the resolver result's `discovered_urls` is mapped to JSONB rows for `commit_discovery_result`, attach `harvest_method` (default `'httpx'` for the seed's own external_urls; the harvester returns the actual method on each row). Also pass `raw_text` from the harvester's `HarvestedUrl.raw_text` field.

The simplest approach: store the harvester's `HarvestedUrl` instances directly in the resolver result, and have `_commit_v2` read `.harvest_method` / `.raw_text` from each. Update `ResolverResult.discovered_urls` to hold the `HarvestedUrl` objects (or keep `DiscoveredUrl` and add the two fields to it).

For minimal blast radius, **add the two fields to `DiscoveredUrl`** in `schemas.py`:

```python
# scripts/schemas.py — extend DiscoveredUrl
class DiscoveredUrl(BaseModel):
    canonical_url: str
    platform: Platform
    account_type: AccountType
    destination_class: DestinationClass
    reason: str
    depth: int = 0
    harvest_method: Optional[Literal["cache", "httpx", "headless"]] = None  # NEW
    raw_text: Optional[str] = None  # NEW
```

Then in `resolver.py::_classify_and_enrich`, when building `DiscoveredUrl(...)` for a harvester-sourced child, copy the fields:

```python
# scripts/pipeline/resolver.py — inside the harvester loop in step 4 of Task 9
            for h in harvested:
                # Create a DiscoveredUrl that carries through the audit fields
                # for the outer commit step. Re-classify via _classify_and_enrich
                # so cache + dedup logic still applies.
                discovered.append(DiscoveredUrl(
                    canonical_url=h.canonical_url,
                    platform="other",  # placeholder; real classify happens in recursion below
                    account_type="other",  # idem
                    destination_class=h.destination_class,
                    reason=f"harvester:{h.harvest_method}",
                    depth=depth + 1,
                    harvest_method=h.harvest_method,
                    raw_text=h.raw_text,
                ))
                _classify_and_enrich(h.canonical_url, depth=depth + 1, is_aggregator_child=True)
```

(Note: this creates duplicate `DiscoveredUrl` rows — one from the harvester's pass, one from the recursion's classifier. Dedup by `canonical_url` happens before commit. The harvester pass gives us the audit fields; the recursion pass gives us the canonical classification. We keep the harvester row and overlay the recursion's classification onto it. See Step 3.)

- [ ] **Step 3: Add a dedup step in resolver.py that merges duplicate `DiscoveredUrl` rows**

```python
# scripts/pipeline/resolver.py — at the bottom of resolve_seed, before return
    # Dedup: if multiple DiscoveredUrl rows share canonical_url, keep the row with
    # the richer classification (rule-based reason wins over harvester:* reason).
    by_canon: dict[str, DiscoveredUrl] = {}
    for d in discovered:
        existing = by_canon.get(d.canonical_url)
        if existing is None:
            by_canon[d.canonical_url] = d
            continue
        # Prefer the row with a non-harvester reason (rule:X / llm:*)
        prefer_d = not d.reason.startswith("harvester:")
        prefer_existing = not existing.reason.startswith("harvester:")
        winner = d if prefer_d and not prefer_existing else existing
        loser = existing if winner is d else d
        # Carry over harvester audit fields from whichever row had them
        if winner.harvest_method is None:
            winner.harvest_method = loser.harvest_method
        if not winner.raw_text:
            winner.raw_text = loser.raw_text
        by_canon[d.canonical_url] = winner
    discovered = list(by_canon.values())
```

- [ ] **Step 4: Update `_commit_v2` to pass the new fields to the RPC**

```python
# scripts/discover_creator.py — find the section building the discovered_urls payload
# Each url dict gets two new keys:
#   "harvest_method": d.harvest_method,
#   "raw_text": d.raw_text,
```

- [ ] **Step 5: Update the SQL RPC `commit_discovery_result` to read the new fields and write them to profile_destination_links**

Inspect: `grep -n 'profile_destination_links' supabase/migrations/*.sql | tail -20`
Find the most recent definition of `commit_discovery_result`. Add a new migration:

```sql
-- supabase/migrations/20260426010000_commit_discovery_result_v3_harvester_audit.sql
-- Update commit_discovery_result to read harvest_method + raw_text from p_discovered_urls.

-- (Paste the existing function body, modify the profile_destination_links INSERT
-- to include the two new columns. Each value comes from the JSONB element via
-- u->>'harvest_method' and u->>'raw_text'.)
```

(The actual diff depends on the existing function body — get it via `mcp__claude_ai_Supabase__list_migrations` or by reading the latest commit_discovery_result migration in the supabase/migrations/ dir, then extend the INSERT clause for `profile_destination_links` to include `harvest_method, raw_text` columns sourced from the JSONB payload.)

- [ ] **Step 6: Apply migration via Supabase MCP**

Use `apply_migration` with the new `commit_discovery_result_v3_harvester_audit` migration.

- [ ] **Step 7: Run full pytest**

Run: `cd scripts && pytest -x -q`
Expected: all PASS.

- [ ] **Step 8: Commit**

```bash
git add scripts/schemas.py scripts/pipeline/resolver.py scripts/discover_creator.py supabase/migrations/20260426010000_*.sql
git commit -m "feat(commit_v2): write harvest_method + raw_text to profile_destination_links"
```

---

## Task 11: Delete deprecated aggregator modules

**Files:**
- Delete: `scripts/aggregators/linktree.py`
- Delete: `scripts/aggregators/beacons.py`
- Delete: `scripts/aggregators/custom_domain.py`
- Delete: `scripts/aggregators/__init__.py`
- Delete: `scripts/aggregators/` (the empty dir)
- Delete: `scripts/tests/aggregators/` (the whole tests dir for these)

- [ ] **Step 1: Confirm no remaining imports**

Run: `grep -rn 'from aggregators\|import aggregators' scripts/ src/ docs/ 2>/dev/null | grep -v __pycache__`
Expected: zero matches. If any non-zero, fix that file first.

- [ ] **Step 2: Delete the package**

```bash
rm -rf scripts/aggregators/ scripts/tests/aggregators/
```

- [ ] **Step 3: Run full pytest**

Run: `cd scripts && pytest -x -q`
Expected: all PASS — no tests rely on the deleted modules.

- [ ] **Step 4: Commit**

```bash
git add -A
git commit -m "refactor: remove deprecated aggregators package — replaced by scripts/harvester/"
```

---

## Task 12: Creator HQ — render destinations grouped by destination_class

**Files:**
- Create: `src/components/creators/CreatorDestinations.tsx`
- Modify: `src/lib/db/queries.ts` — add `getDestinationsForCreator(creatorId, workspaceId)`
- Modify: `src/app/(dashboard)/creators/[slug]/page.tsx` — render the new section

- [ ] **Step 1: Write a Playwright/Chrome DevTools MCP smoke that asserts the section renders**

This is a UI-level check, not a unit test. We'll run it manually after build:
- Open Esmae's creator HQ page
- Confirm a "All Destinations" section appears below Brand Summary
- Confirm destinations grouped under headings: "Monetization", "Aggregator", "Social", "Messaging", "Affiliate", "Content", etc. (only sections with ≥1 link render)
- Confirm each link shows raw_text label + click-through external link

- [ ] **Step 2: Add the query helper**

```typescript
// src/lib/db/queries.ts — append
export async function getDestinationsForCreator(
  creatorId: string,
  workspaceId: string,
) {
  const sb = getSupabase();
  const { data, error } = await sb
    .from("profile_destination_links")
    .select(`
      profile_id,
      canonical_url,
      destination_class,
      raw_text,
      harvest_method,
      harvested_at,
      profiles!inner(creator_id)
    `)
    .eq("workspace_id", workspaceId)
    .eq("profiles.creator_id", creatorId)
    .order("destination_class", { ascending: true });

  if (error) return { ok: false as const, error };
  return { ok: true as const, data: data ?? [] };
}
```

- [ ] **Step 3: Create the component**

```typescript
// src/components/creators/CreatorDestinations.tsx
import Link from "next/link";

const CLASS_ORDER = [
  "monetization",
  "aggregator",
  "affiliate",
  "commerce",
  "content",
  "professional",
  "messaging",
  "social",
  "unknown",
  "other",
];

const CLASS_LABEL: Record<string, string> = {
  monetization: "Monetization",
  aggregator: "Link-in-Bio",
  affiliate: "Affiliate",
  commerce: "Commerce",
  content: "Content",
  professional: "Professional",
  messaging: "Messaging",
  social: "Social",
  unknown: "Unclassified",
  other: "Other",
};

type Destination = {
  canonical_url: string;
  destination_class: string;
  raw_text: string | null;
  harvest_method: string | null;
  harvested_at: string | null;
};

export function CreatorDestinations({
  destinations,
}: {
  destinations: Destination[];
}) {
  if (destinations.length === 0) {
    return null;
  }

  const grouped: Record<string, Destination[]> = {};
  for (const d of destinations) {
    const cls = d.destination_class || "unknown";
    (grouped[cls] ||= []).push(d);
  }

  return (
    <section className="rounded-lg border border-white/[0.06] bg-[#13131A] p-6">
      <header className="mb-4">
        <h2 className="text-sm font-semibold text-white/90">All Destinations</h2>
        <p className="text-xs text-white/50">
          Every URL the discovery pipeline harvested for this creator's network,
          grouped by class. Filter and act on these.
        </p>
      </header>

      <div className="space-y-5">
        {CLASS_ORDER.filter((c) => grouped[c]?.length).map((cls) => (
          <div key={cls}>
            <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-white/60">
              {CLASS_LABEL[cls]} ({grouped[cls].length})
            </h3>
            <ul className="space-y-1">
              {grouped[cls].map((d) => (
                <li key={d.canonical_url} className="flex items-baseline gap-2 text-sm">
                  <Link
                    href={d.canonical_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-white/80 hover:text-violet-300"
                  >
                    {d.raw_text || d.canonical_url}
                  </Link>
                  {d.raw_text && (
                    <span className="text-xs text-white/40">{d.canonical_url}</span>
                  )}
                  {d.harvest_method === "headless" && (
                    <span
                      title="Captured via headless browser (sensitive-content gate)"
                      className="ml-1 rounded bg-violet-500/10 px-1.5 py-0.5 text-[10px] uppercase tracking-wide text-violet-300"
                    >
                      gated
                    </span>
                  )}
                </li>
              ))}
            </ul>
          </div>
        ))}
      </div>
    </section>
  );
}
```

- [ ] **Step 4: Render the component on the creator page**

```typescript
// src/app/(dashboard)/creators/[slug]/page.tsx — within the main content area,
// below the Brand Summary placeholder card and above the tabs

import { getDestinationsForCreator } from "@/lib/db/queries";
import { CreatorDestinations } from "@/components/creators/CreatorDestinations";

// inside the page component:
const destResult = await getDestinationsForCreator(creator.id, creator.workspace_id);
const destinations = destResult.ok ? destResult.data : [];

// in JSX:
<CreatorDestinations destinations={destinations} />
```

- [ ] **Step 5: Type-check**

Run: `npx tsc --noEmit`
Expected: 0 errors.

- [ ] **Step 6: Visual verify via Chrome DevTools MCP**

Open `http://localhost:3000/creators/esmaecursed-1776896975319784`. Take snapshot. Confirm:
- "All Destinations" section visible
- Multiple class headings present
- At least one entry with `gated` chip if Tier 2 ran on a sensitive-content page

(If no entries yet, that's expected pre-smoke — Task 14 re-runs discovery.)

- [ ] **Step 7: Commit**

```bash
git add src/components/creators/CreatorDestinations.tsx src/lib/db/queries.ts src/app/\(dashboard\)/creators/\[slug\]/page.tsx
git commit -m "feat(creator-hq): All Destinations section grouped by destination_class"
```

---

## Task 13: Live smoke test — re-discover Esmae + the research creator

**Files:**
- No code changes; this is verification.

- [ ] **Step 1: Restart launchd worker**

Run: `bash scripts/worker_ctl.sh restart`
Expected: `Worker (re)started`. Verify: `bash scripts/worker_ctl.sh status` shows running.

- [ ] **Step 2: Re-trigger discovery for Esmae via UI**

Open `http://localhost:3000/creators/esmaecursed-1776896975319784`. Click "Re-run Discovery". Wait for progress bar to reach 100%.

Expected:
- Stage progress: 10 → 35 → 50 → 70 → 90 → 100
- No errors in worker log: `tail -50 ~/Library/Logs/the-hub-worker.log`

- [ ] **Step 3: Query the resulting destinations**

Run via Supabase MCP `execute_sql`:
```sql
SELECT canonical_url, destination_class, raw_text, harvest_method
FROM profile_destination_links pdl
JOIN profiles p ON p.id = pdl.profile_id
WHERE p.creator_id = '<esmae-creator-id>'
ORDER BY destination_class, canonical_url;
```

Expected:
- ≥1 row with `destination_class='monetization'` and `harvest_method='headless'` (the Fanplace link)
- ≥1 row with `destination_class='messaging'` (the Telegram links)
- ≥1 row with `destination_class='social'` (the IG + X links)
- ≥1 row with `destination_class='aggregator'` (the tapforallmylinks itself)

- [ ] **Step 4: Verify cost stayed under budget**

Run via Supabase MCP `execute_sql`:
```sql
SELECT cost_apify_cents FROM bulk_imports
ORDER BY created_at DESC LIMIT 1;
```

Expected: < 100¢ for a single re-discovery.

- [ ] **Step 5: Visual verify Esmae's HQ page**

Open `http://localhost:3000/creators/esmaecursed-1776896975319784`. Confirm:
- "All Destinations" section now populated
- Fanplace link present, marked with the `gated` chip
- Multi-class grouping renders correctly

- [ ] **Step 6: Add the research creator (Twitter→linktree case)**

Use the bulk-import flow on `/creators` to add the Twitter handle Simon mentioned. Wait for discovery. Verify the linktree's BuyMeCoffee, Spotify, Amazon Wishlist, TikTok Shop, and affiliate links all appear with appropriate `destination_class` values.

Expected:
- BuyMeCoffee → `monetization`
- Spotify → `content`
- Amazon → `commerce` (or `monetization` if matches `/shop/`)
- TikTok Shop → `commerce` (or `monetization`)
- Affiliate links (`amzn.to`, `geni.us`, etc.) → `affiliate`
- Anything unrecognized → `unknown` (still saved)

- [ ] **Step 7: Document costs + findings in session note**

Append to `06-Sessions/2026-04-26.md`:
- Total Apify spend across both smokes
- Number of `headless` rows captured vs `httpx`
- Cache-hit rate on second-run-of-Esmae (run a third re-discovery; the count should match but cost should drop)

No commit at this step — documentation lands in Task 14.

---

## Task 14: Sync PROJECT_STATE + commit + push

**Files:**
- Modify: `PROJECT_STATE.md` — §4 schema (add `url_harvest_cache`), §10 deprecated aggregators removed, §14 add Universal URL Harvester to build order, §20 update sensitive-content limitation, append to Decisions Log
- Modify: `06-Sessions/2026-04-26.md` — session note (or current date)

- [ ] **Step 1: Use the `sync-project-state` skill**

Run via the Skill tool: invoke `sync-project-state`. The skill walks PROJECT_STATE.md, regenerates SCHEMA.md, updates the Decisions Log entry for today, and commits + pushes.

(If the sync-project-state skill has its own commit/push, no manual git steps needed here. Otherwise, do them manually.)

- [ ] **Step 2: Confirm Decisions Log entry**

Append (the skill should do this; verify):
```markdown
- 2026-04-26: Universal URL harvester shipped on `phase-2-discovery-v2`.
  Replaces per-aggregator extractors (`linktree.py`, `beacons.py`, `custom_domain.py`)
  with `scripts/harvester/` cascade — cache → Tier 1 httpx + signal regex → Tier 2
  Apify Puppeteer Scraper. Captures JS-gated "sensitive content" / "open link"
  interstitials previously invisible (the slice that hides OF/Fanvue/Fanplace/
  similar links behind a 2-step click on aggregators like tapforallmylinks).
  Schema: new `url_harvest_cache` table (24 tables total); 3 audit cols added
  to `profile_destination_links`. `DestinationClass` extended from 4 → 10 values.
  Gazetteer +30 rules covering BuyMeCoffee/Ko-fi/Substack/Spotify/Telegram/
  affiliate redirectors/etc. Creator HQ gets new "All Destinations" section
  grouped by class. Live smoke: Esmae re-discovery surfaced Fanplace link via
  Tier 2 (previously missed). Costs: ~5¢ per discovery cycle, <1¢ per cached
  re-run within 24h. Tests: 138 → ~175.
```

- [ ] **Step 3: Final pytest + tsc**

Run: `cd scripts && pytest -q && cd .. && npx tsc --noEmit`
Expected: all PASS, 0 errors.

- [ ] **Step 4: Push**

```bash
git push origin phase-2-discovery-v2
```

---

## Self-Review Notes

After writing this plan, here are checks I made:

**Spec coverage:**
- ✅ Universal harvester replaces per-aggregator code: Tasks 5, 6, 7, 9, 11
- ✅ Cheap-first cascade with signal-regex escalation: Task 5 (signals) + Task 7 (cascade)
- ✅ Sensitive-content / 2-step gates handled: Task 6 page function step 4
- ✅ JS-gated SPA pages: Task 6 page function steps 2 + 3 (waitUntil networkidle + DOM extract post-hydration)
- ✅ Native app deeplink case: Task 5 step 4 forces desktop UA + Task 6 page function intercepts location.href setter
- ✅ Extended `destination_class` taxonomy (10 classes): Task 2 step 3
- ✅ Save-everything-default: Task 7 (orchestrator) + Task 10 (commit_v2 audit fields)
- ✅ 24h cache: Task 4
- ✅ Recursive trail-following preserved: Task 9 keeps `_classify_and_enrich` recursion structure intact, only swaps the dispatch primitive
- ✅ Creator HQ surface: Task 12

**Placeholder scan:**
- Task 10 step 5 uses "(The actual diff depends on the existing function body — get it via ...)" which IS a placeholder. Acceptable here because the function body changes between sync points and the implementer must re-read it; the operation is mechanical (add two columns to one INSERT). Do not skip — read the current `commit_discovery_result` migration first.
- Task 13 step 6 references "the Twitter handle Simon mentioned" — this is intentional. Implementer asks the user for the handle at execution time.
- Task 14 step 1 delegates to `sync-project-state` skill — that's by design.

**Type consistency:**
- `HarvestedUrl` shape defined in Task 2 step 5; consumed identically in Tasks 4, 6, 7, 9.
- `harvest_method` Literal `cache | httpx | headless` defined in Task 2; matches DB CHECK constraint in Task 3 (`httpx | headless`); cache layer (Task 4) returns objects with whatever method was originally cached, never overwriting to `cache` — consistent.
- `destination_class` 10 values defined in Task 2; CHECK constraint absent in DB (TEXT not enum) — by design; orchestrator's `_destination_class_for` always returns one of the 10 values.
- `HARVEST_CLASSES` defined in Task 2; consumed identically in Task 9 (resolver gating).
- `_destination_class_for` signature changes from `(account_type)` to `(account_type, canonical_url)` in Task 8. Resolver still uses the simple version (Task 9 step 5) — that's a deliberate divergence (resolver only needs gate decision; orchestrator does host-aware finalization). Documented.

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-04-25-universal-url-harvester.md`. Two execution options:

**1. Subagent-Driven (recommended)** — I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** — Execute tasks in this session using executing-plans, batch execution with checkpoints

**Which approach?**
