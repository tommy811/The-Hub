# Discovery Pipeline Rebuild Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace garbage-context discovery (httpx against IG/TikTok login walls) with Apify-grounded context fetching so Gemini receives real bio, follower counts, and link-in-bio destinations — eliminating hallucination from prior-knowledge guessing.

**Architecture:** A thin `apify_details` helper fetches structured profile data (bio, externalUrls, follower count) via Apify actors for IG (`apify/instagram-scraper` in `details` mode) and TikTok (`clockworks/tiktok-scraper`). A new `link_in_bio` resolver follows Linktree/Beacons destinations via direct httpx (these pages are scraping-friendly). `fetch_input_context()` is rewritten to call these, detect empty results (the login-wall signal), and pass structured data into Gemini with an explicit "ground in provided context only" prompt. Pydantic models gain strict `Literal` types on `platform` and `edge_type` to fail at the boundary rather than inside SQL casts. A one-line migration creates the missing `edge_type` enum to fix a latent crash in `commit_discovery_result`.

**Tech Stack:** Python 3.11+, Pydantic v2, `apify-client`, `httpx`, `beautifulsoup4`, `google-generativeai`, `tenacity`, `pytest` + `pytest-mock` (new), Supabase Postgres 17.

---

## File Structure

**Create:**
- `scripts/schemas.py` — Pydantic models (`InputContext`, `ProposedAccount`, `ProposedFunnelEdge`, `DiscoveryResult`). Moved out of `discover_creator.py` for reuse and testability.
- `scripts/apify_details.py` — Apify profile-details fetchers for IG and TikTok. Raises `EmptyDatasetError` on login-wall / empty result.
- `scripts/link_in_bio.py` — Linktree/Beacons/custom-domain link extractor.
- `scripts/tests/__init__.py` — empty init.
- `scripts/tests/conftest.py` — pytest fixtures.
- `scripts/tests/test_schemas.py`
- `scripts/tests/test_apify_details.py`
- `scripts/tests/test_link_in_bio.py`
- `scripts/tests/test_discover_creator.py`
- `scripts/tests/test_worker.py`
- `scripts/tests/fixtures/linktree_sample.html`
- `scripts/tests/fixtures/beacons_sample.html`
- `scripts/tests/fixtures/apify_ig_details.json`
- `scripts/tests/fixtures/apify_tiktok_profile.json`
- `supabase/migrations/20260424150000_create_edge_type_enum.sql`

**Modify:**
- `scripts/discover_creator.py` — new `fetch_input_context()`, new Gemini prompt, tenacity retry on `mark_discovery_failed`, dead-letter on final failure, remove now-duplicated models/enum-injection code.
- `scripts/worker.py` — surface per-task exceptions from `asyncio.gather` instead of swallowing them.
- `scripts/requirements.txt` — add `pytest==8.2.0`, `pytest-mock==3.14.0`.
- `PROJECT_STATE.md` — §4.1 enum note (`edge_type` now live), §20 remove httpx discovery limitation, Decisions Log append.

---

## Task 0: Branch + Test Scaffolding

**Files:**
- Modify: `scripts/requirements.txt`
- Create: `scripts/tests/__init__.py`
- Create: `scripts/tests/conftest.py`

- [ ] **Step 1: Create branch**

```bash
cd "/Users/simon/OS/Living VAULT/Content OS/The Hub"
git checkout main
git pull
git checkout -b phase-2-discovery-rebuild
```

- [ ] **Step 2: Add pytest deps to requirements.txt**

Edit `scripts/requirements.txt`, append two lines:

```
pytest==8.2.0
pytest-mock==3.14.0
```

- [ ] **Step 3: Install deps**

```bash
cd "/Users/simon/OS/Living VAULT/Content OS/The Hub/scripts"
pip install -r requirements.txt
```

Expected: no errors, pytest and pytest-mock installed.

- [ ] **Step 4: Create test scaffolding**

Create `scripts/tests/__init__.py` as an empty file.

Create `scripts/tests/conftest.py`:

```python
# scripts/tests/conftest.py
import sys
from pathlib import Path

# Make `scripts/` importable so `from schemas import ...` works inside tests.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
```

- [ ] **Step 5: Verify pytest discovers the empty test dir**

```bash
cd "/Users/simon/OS/Living VAULT/Content OS/The Hub/scripts"
python -m pytest tests/ -v
```

Expected: `collected 0 items` — no failures, pytest wired up correctly.

- [ ] **Step 6: Commit**

```bash
git add scripts/requirements.txt scripts/tests/__init__.py scripts/tests/conftest.py
git commit -m "chore(pipeline): add pytest scaffolding for discovery tests"
```

---

## Task 1: edge_type Enum Migration (Fix Latent Crash)

**Files:**
- Create: `supabase/migrations/20260424150000_create_edge_type_enum.sql`

Fixes audit §1.1.7 — `commit_discovery_result` RPC casts `(v_edge->>'edge_type')::edge_type` but no such type exists. Will crash first time any funnel edge is committed. `funnel_edges` has 0 rows today, so the conversion is safe.

- [ ] **Step 1: Write the migration**

Create `supabase/migrations/20260424150000_create_edge_type_enum.sql`:

```sql
-- 20260424150000_create_edge_type_enum.sql
-- Fix latent crash in commit_discovery_result: the RPC casts
-- (v_edge->>'edge_type')::edge_type but no such enum existed.
-- funnel_edges is currently empty, so converting the column type is safe.

BEGIN;

-- Guard: abort if any rows slipped in since the audit
DO $$
DECLARE
  row_count int;
BEGIN
  SELECT COUNT(*) INTO row_count FROM funnel_edges;
  IF row_count > 0 THEN
    RAISE EXCEPTION
      'funnel_edges has % row(s). Review existing edge_type values before migrating.',
      row_count;
  END IF;
END $$;

CREATE TYPE edge_type AS ENUM (
  'link_in_bio',
  'direct_link',
  'cta_mention',
  'qr_code',
  'inferred'
);

ALTER TABLE funnel_edges
  ALTER COLUMN edge_type TYPE edge_type USING edge_type::edge_type;

COMMIT;
```

- [ ] **Step 2: Apply the migration via Supabase MCP**

Use the Supabase MCP `apply_migration` tool:

```
name: create_edge_type_enum
query: <contents of migration file, without the filename comment>
```

Expected: migration succeeds, no errors.

- [ ] **Step 3: Verify the enum exists**

Use Supabase MCP `execute_sql`:

```sql
SELECT typname FROM pg_type WHERE typname = 'edge_type';
```

Expected: 1 row returned with `typname = 'edge_type'`.

```sql
SELECT column_name, udt_name
FROM information_schema.columns
WHERE table_name = 'funnel_edges' AND column_name = 'edge_type';
```

Expected: `udt_name = 'edge_type'` (was `'text'` before).

- [ ] **Step 4: Regenerate TypeScript types**

```bash
cd "/Users/simon/OS/Living VAULT/Content OS/The Hub"
npm run db:types
```

Expected: `src/types/database.types.ts` updated; `npx tsc --noEmit` still returns 0.

- [ ] **Step 5: Regenerate SCHEMA.md**

```bash
npm run db:schema
```

Expected: `docs/SCHEMA.md` updated. `edge_type` appears in the Enums section.

- [ ] **Step 6: Commit**

```bash
git add supabase/migrations/20260424150000_create_edge_type_enum.sql \
        src/types/database.types.ts \
        docs/SCHEMA.md
git commit -m "fix(db): create edge_type enum to fix latent RPC crash (audit 1.1.7)"
```

---

## Task 2: Schemas Module

**Files:**
- Create: `scripts/schemas.py`
- Create: `scripts/tests/test_schemas.py`
- Modify: `scripts/discover_creator.py` (remove models — done in Task 5)

Extract Pydantic models to their own module. Add `patreon` to the platform enum. Convert `ProposedAccount.platform` from loose `str` to strict `Literal` (audit item 15 — platform validation gap).

- [ ] **Step 1: Write failing tests**

Create `scripts/tests/test_schemas.py`:

```python
# scripts/tests/test_schemas.py
import pytest
from pydantic import ValidationError

from schemas import (
    InputContext,
    ProposedAccount,
    ProposedFunnelEdge,
    DiscoveryResult,
    PLATFORM_VALUES,
)


class TestProposedAccountPlatform:
    def test_accepts_instagram(self):
        acc = ProposedAccount(
            account_type="social",
            platform="instagram",
            discovery_confidence=0.9,
            reasoning="test",
        )
        assert acc.platform == "instagram"

    def test_accepts_patreon(self):
        acc = ProposedAccount(
            account_type="monetization",
            platform="patreon",
            discovery_confidence=0.9,
            reasoning="test",
        )
        assert acc.platform == "patreon"

    def test_rejects_bogus_platform(self):
        with pytest.raises(ValidationError) as exc:
            ProposedAccount(
                account_type="social",
                platform="mastodon",
                discovery_confidence=0.9,
                reasoning="test",
            )
        assert "platform" in str(exc.value)


class TestProposedFunnelEdge:
    def test_rejects_bogus_edge_type(self):
        with pytest.raises(ValidationError):
            ProposedFunnelEdge(
                from_handle="a",
                from_platform="instagram",
                to_handle="b",
                to_platform="tiktok",
                edge_type="magic_portal",
                confidence=0.9,
            )

    def test_accepts_link_in_bio(self):
        edge = ProposedFunnelEdge(
            from_handle="a",
            from_platform="instagram",
            to_handle="b",
            to_platform="onlyfans",
            edge_type="link_in_bio",
            confidence=0.95,
        )
        assert edge.edge_type == "link_in_bio"


class TestInputContext:
    def test_empty_external_urls_default(self):
        ctx = InputContext(handle="x", platform="instagram")
        assert ctx.external_urls == []

    def test_empty_flag_true_when_no_bio_and_no_followers(self):
        ctx = InputContext(handle="x", platform="instagram")
        assert ctx.is_empty() is True

    def test_empty_flag_false_when_bio_present(self):
        ctx = InputContext(handle="x", platform="instagram", bio="hi")
        assert ctx.is_empty() is False

    def test_empty_flag_false_when_followers_present(self):
        ctx = InputContext(handle="x", platform="instagram", follower_count=100)
        assert ctx.is_empty() is False


class TestPlatformValuesCompleteness:
    def test_includes_patreon(self):
        assert "patreon" in PLATFORM_VALUES

    def test_matches_documented_db_enum(self):
        # Full list from PROJECT_STATE §5, excluding 'other'
        expected = {
            "instagram", "tiktok", "youtube", "patreon", "twitter", "linkedin",
            "facebook", "onlyfans", "fanvue", "fanplace", "amazon_storefront",
            "tiktok_shop", "linktree", "beacons", "custom_domain",
            "telegram_channel", "telegram_cupidbot", "other",
        }
        assert set(PLATFORM_VALUES) == expected
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
cd "/Users/simon/OS/Living VAULT/Content OS/The Hub/scripts"
python -m pytest tests/test_schemas.py -v
```

Expected: all tests FAIL with `ModuleNotFoundError: No module named 'schemas'`.

- [ ] **Step 3: Create the schemas module**

Create `scripts/schemas.py`:

```python
# scripts/schemas.py — Pydantic models for discovery pipeline
from typing import Literal, Optional
from uuid import UUID
from pydantic import BaseModel, Field

PLATFORM_VALUES = (
    "instagram", "tiktok", "youtube", "patreon", "twitter", "linkedin",
    "facebook", "onlyfans", "fanvue", "fanplace", "amazon_storefront",
    "tiktok_shop", "linktree", "beacons", "custom_domain",
    "telegram_channel", "telegram_cupidbot", "other",
)

Platform = Literal[
    "instagram", "tiktok", "youtube", "patreon", "twitter", "linkedin",
    "facebook", "onlyfans", "fanvue", "fanplace", "amazon_storefront",
    "tiktok_shop", "linktree", "beacons", "custom_domain",
    "telegram_channel", "telegram_cupidbot", "other",
]

EdgeType = Literal["link_in_bio", "direct_link", "cta_mention", "qr_code", "inferred"]

AccountType = Literal["social", "monetization", "link_in_bio", "messaging", "other"]

MonetizationModel = Literal[
    "subscription", "tips", "ppv", "affiliate", "brand_deals",
    "ecommerce", "coaching", "saas", "mixed", "unknown",
]


class DiscoveryInput(BaseModel):
    run_id: UUID
    creator_id: UUID
    workspace_id: UUID
    input_handle: Optional[str] = None
    input_url: Optional[str] = None
    input_platform_hint: Optional[str] = None


class InputContext(BaseModel):
    """Structured context passed to Gemini. Replaces the old free-form HTML dump."""
    handle: str
    platform: str
    display_name: Optional[str] = None
    bio: Optional[str] = None
    follower_count: Optional[int] = None
    following_count: Optional[int] = None
    post_count: Optional[int] = None
    avatar_url: Optional[str] = None
    is_verified: bool = False
    external_urls: list[str] = Field(default_factory=list)
    link_in_bio_destinations: list[str] = Field(default_factory=list)
    source_note: Optional[str] = None  # e.g. "apify/instagram-scraper details mode"

    def is_empty(self) -> bool:
        """True when the Apify fetch produced nothing useful (login wall / gone / private)."""
        return (
            not self.bio
            and self.follower_count is None
            and not self.external_urls
        )


class ProposedAccount(BaseModel):
    account_type: AccountType
    platform: Platform
    handle: Optional[str] = None
    url: Optional[str] = None
    display_name: Optional[str] = None
    bio: Optional[str] = None
    follower_count: Optional[int] = None
    is_primary: bool = False
    discovery_confidence: float = Field(ge=0.0, le=1.0)
    reasoning: str


class ProposedFunnelEdge(BaseModel):
    from_handle: str
    from_platform: Platform
    to_handle: str
    to_platform: Platform
    edge_type: EdgeType
    confidence: float = Field(ge=0.0, le=1.0)


class DiscoveryResult(BaseModel):
    canonical_name: str
    known_usernames: list[str]
    display_name_variants: list[str]
    primary_platform: Platform
    primary_niche: Optional[str] = None
    monetization_model: MonetizationModel = "unknown"
    proposed_accounts: list[ProposedAccount]
    proposed_funnel_edges: list[ProposedFunnelEdge]
    raw_reasoning: str
```

- [ ] **Step 4: Run tests to confirm they pass**

```bash
python -m pytest tests/test_schemas.py -v
```

Expected: all tests PASS.

- [ ] **Step 5: Commit**

```bash
git add scripts/schemas.py scripts/tests/test_schemas.py
git commit -m "feat(pipeline): extract schemas module with strict platform/edge_type Literals"
```

---

## Task 3: Apify Details Fetcher

**Files:**
- Create: `scripts/apify_details.py`
- Create: `scripts/tests/test_apify_details.py`
- Create: `scripts/tests/fixtures/apify_ig_details.json`
- Create: `scripts/tests/fixtures/apify_tiktok_profile.json`

Fetch structured profile context from Apify. IG via `apify/instagram-scraper` with `resultsType: "details"`. TikTok via `clockworks/tiktok-scraper` with single-profile mode.

- [ ] **Step 1: Create Apify response fixtures**

Create `scripts/tests/fixtures/apify_ig_details.json`:

```json
[
  {
    "id": "123456789",
    "username": "gothgirlnatalie",
    "url": "https://www.instagram.com/gothgirlnatalie/",
    "fullName": "Natalie Vox",
    "biography": "goth girl ✦ 18+ link below",
    "externalUrls": [
      {"url": "https://linktr.ee/gothgirlnatalie", "title": null}
    ],
    "followersCount": 48200,
    "followsCount": 612,
    "postsCount": 142,
    "profilePicUrl": "https://instagram.com/pic.jpg",
    "profilePicUrlHD": "https://instagram.com/pic_hd.jpg",
    "verified": false,
    "isBusinessAccount": false,
    "isPrivate": false,
    "businessCategoryName": null
  }
]
```

Create `scripts/tests/fixtures/apify_tiktok_profile.json`:

```json
[
  {
    "authorMeta": {
      "id": "6891234567890",
      "name": "gothgirlnatalie",
      "nickName": "Natalie",
      "verified": false,
      "signature": "goth girl ✦ link below",
      "bioLink": {"link": "https://linktr.ee/gothgirlnatalie"},
      "avatar": "https://tiktok.com/pic.jpg",
      "fans": 12400,
      "following": 80,
      "heart": 324000,
      "video": 56,
      "profileUrl": "https://www.tiktok.com/@gothgirlnatalie"
    }
  }
]
```

- [ ] **Step 2: Write failing tests**

Create `scripts/tests/test_apify_details.py`:

```python
# scripts/tests/test_apify_details.py
import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from apify_details import (
    EmptyDatasetError,
    fetch_instagram_details,
    fetch_tiktok_details,
)

FIXTURES = Path(__file__).parent / "fixtures"


def _load(name: str) -> list[dict]:
    return json.loads((FIXTURES / name).read_text())


def _mock_client(dataset_items: list[dict]) -> MagicMock:
    """Build a MagicMock that mimics ApifyClient.actor(id).call(...) + dataset(...).list_items()."""
    client = MagicMock()
    actor = MagicMock()
    dataset = MagicMock()
    run_ret = {"defaultDatasetId": "fake-dataset-id"}
    actor.call.return_value = run_ret
    dataset.list_items.return_value = MagicMock(items=dataset_items)
    client.actor.return_value = actor
    client.dataset.return_value = dataset
    return client


class TestFetchInstagramDetails:
    def test_returns_context_with_bio_and_external_urls(self):
        client = _mock_client(_load("apify_ig_details.json"))
        ctx = fetch_instagram_details(client, "gothgirlnatalie")
        assert ctx.handle == "gothgirlnatalie"
        assert ctx.platform == "instagram"
        assert ctx.bio == "goth girl ✦ 18+ link below"
        assert ctx.follower_count == 48200
        assert ctx.following_count == 612
        assert ctx.post_count == 142
        assert "https://linktr.ee/gothgirlnatalie" in ctx.external_urls
        assert ctx.display_name == "Natalie Vox"
        assert ctx.avatar_url == "https://instagram.com/pic_hd.jpg"
        assert ctx.is_empty() is False

    def test_uses_details_mode(self):
        client = _mock_client(_load("apify_ig_details.json"))
        fetch_instagram_details(client, "gothgirlnatalie")
        call_args = client.actor.return_value.call.call_args
        run_input = call_args.kwargs.get("run_input") or call_args.args[0]
        assert run_input["resultsType"] == "details"
        assert "gothgirlnatalie" in run_input["directUrls"][0]

    def test_raises_on_empty_dataset(self):
        client = _mock_client([])
        with pytest.raises(EmptyDatasetError) as exc:
            fetch_instagram_details(client, "deleteduser")
        assert "deleteduser" in str(exc.value)


class TestFetchTikTokDetails:
    def test_returns_context_from_author_meta(self):
        client = _mock_client(_load("apify_tiktok_profile.json"))
        ctx = fetch_tiktok_details(client, "gothgirlnatalie")
        assert ctx.handle == "gothgirlnatalie"
        assert ctx.platform == "tiktok"
        assert ctx.bio == "goth girl ✦ link below"
        assert ctx.follower_count == 12400
        assert "https://linktr.ee/gothgirlnatalie" in ctx.external_urls
        assert ctx.display_name == "Natalie"
        assert ctx.is_empty() is False

    def test_uses_clockworks_actor(self):
        client = _mock_client(_load("apify_tiktok_profile.json"))
        fetch_tiktok_details(client, "gothgirlnatalie")
        actor_id = client.actor.call_args.args[0]
        assert actor_id == "clockworks/tiktok-scraper"

    def test_raises_on_empty_dataset(self):
        client = _mock_client([])
        with pytest.raises(EmptyDatasetError):
            fetch_tiktok_details(client, "ghost")
```

- [ ] **Step 3: Run tests to confirm they fail**

```bash
python -m pytest tests/test_apify_details.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'apify_details'`.

- [ ] **Step 4: Implement apify_details.py**

Create `scripts/apify_details.py`:

```python
# scripts/apify_details.py — Apify profile-details fetchers for discovery context
from typing import Any, Optional
from apify_client import ApifyClient

from schemas import InputContext


class EmptyDatasetError(RuntimeError):
    """Raised when Apify returns zero items — the login-wall / gone / private signal."""


def _first_or_none(items: list[dict]) -> Optional[dict]:
    return items[0] if items else None


def fetch_instagram_details(client: ApifyClient, handle: str) -> InputContext:
    """Fetch IG profile context via apify/instagram-scraper in details mode.

    Raises EmptyDatasetError if the actor returns no items (login wall, banned, private).
    """
    run_input: dict[str, Any] = {
        "directUrls": [f"https://www.instagram.com/{handle}/"],
        "resultsType": "details",
        "resultsLimit": 1,
    }
    run = client.actor("apify/instagram-scraper").call(run_input=run_input)
    items = client.dataset(run["defaultDatasetId"]).list_items().items

    item = _first_or_none(items)
    if item is None:
        raise EmptyDatasetError(
            f"apify/instagram-scraper returned 0 items for @{handle} — "
            f"likely a login wall, private account, or banned handle."
        )

    external_urls = [
        e["url"] for e in (item.get("externalUrls") or []) if e.get("url")
    ]

    return InputContext(
        handle=handle,
        platform="instagram",
        display_name=item.get("fullName"),
        bio=item.get("biography"),
        follower_count=item.get("followersCount"),
        following_count=item.get("followsCount"),
        post_count=item.get("postsCount"),
        avatar_url=item.get("profilePicUrlHD") or item.get("profilePicUrl"),
        is_verified=bool(item.get("verified", False)),
        external_urls=external_urls,
        source_note="apify/instagram-scraper details mode",
    )


def fetch_tiktok_details(client: ApifyClient, handle: str) -> InputContext:
    """Fetch TikTok profile context via clockworks/tiktok-scraper.

    We request resultsPerPage=1 and read authorMeta from that single post; the actor
    does not expose a true profile-only mode, but authorMeta is stable across posts.
    """
    run_input: dict[str, Any] = {
        "profiles": [handle],
        "resultsPerPage": 1,
        "shouldDownloadVideos": False,
        "shouldDownloadCovers": False,
        "shouldDownloadSubtitles": False,
    }
    run = client.actor("clockworks/tiktok-scraper").call(run_input=run_input)
    items = client.dataset(run["defaultDatasetId"]).list_items().items

    item = _first_or_none(items)
    if item is None:
        raise EmptyDatasetError(
            f"clockworks/tiktok-scraper returned 0 items for @{handle} — "
            f"likely a login wall, private account, or banned handle."
        )

    meta = item.get("authorMeta") or {}
    bio_link = meta.get("bioLink") or {}
    link_url = bio_link.get("link") if isinstance(bio_link, dict) else None

    external_urls: list[str] = []
    if link_url:
        external_urls.append(link_url)

    return InputContext(
        handle=handle,
        platform="tiktok",
        display_name=meta.get("nickName") or meta.get("name"),
        bio=meta.get("signature"),
        follower_count=meta.get("fans"),
        following_count=meta.get("following"),
        post_count=meta.get("video"),
        avatar_url=meta.get("avatar"),
        is_verified=bool(meta.get("verified", False)),
        external_urls=external_urls,
        source_note="clockworks/tiktok-scraper",
    )
```

- [ ] **Step 5: Run tests to confirm they pass**

```bash
python -m pytest tests/test_apify_details.py -v
```

Expected: all 6 tests PASS.

- [ ] **Step 6: Commit**

```bash
git add scripts/apify_details.py scripts/tests/test_apify_details.py scripts/tests/fixtures/
git commit -m "feat(pipeline): apify details fetchers for IG + TikTok (with empty-dataset guard)"
```

---

## Task 4: Link-in-Bio Resolver

**Files:**
- Create: `scripts/link_in_bio.py`
- Create: `scripts/tests/test_link_in_bio.py`
- Create: `scripts/tests/fixtures/linktree_sample.html`
- Create: `scripts/tests/fixtures/beacons_sample.html`

Fetch Linktree/Beacons pages directly (they don't block like IG does) and extract outbound destinations.

- [ ] **Step 1: Create HTML fixtures**

Create `scripts/tests/fixtures/linktree_sample.html`:

```html
<!doctype html>
<html>
<head><title>@gothgirlnatalie | Linktree</title></head>
<body>
<main>
  <a href="https://linktr.ee/gothgirlnatalie" class="internal">Home</a>
  <a href="https://onlyfans.com/gothgirlnatalie" data-testid="LinkButton" target="_blank">OnlyFans</a>
  <a href="https://fanvue.com/gothgirlnatalie" data-testid="LinkButton" target="_blank">Fanvue</a>
  <a href="https://instagram.com/gothgirlnatalie" data-testid="LinkButton" target="_blank">Instagram</a>
  <a href="https://help.linktr.ee/support">Help</a>
  <a href="mailto:contact@example.com">Email</a>
</main>
</body>
</html>
```

Create `scripts/tests/fixtures/beacons_sample.html`:

```html
<!doctype html>
<html>
<head><title>Natalie — Beacons</title></head>
<body>
  <a href="https://beacons.ai/gothgirlnatalie">Home</a>
  <a href="https://onlyfans.com/gothgirlnatalie" rel="noopener" target="_blank">OnlyFans</a>
  <a href="https://patreon.com/gothgirlnatalie" rel="noopener" target="_blank">Patreon</a>
  <a href="https://www.beacons.ai/legal">Legal</a>
</body>
</html>
```

- [ ] **Step 2: Write failing tests**

Create `scripts/tests/test_link_in_bio.py`:

```python
# scripts/tests/test_link_in_bio.py
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from link_in_bio import resolve_link_in_bio, is_aggregator_url

FIXTURES = Path(__file__).parent / "fixtures"


def _mock_response(html: str, status_code: int = 200) -> MagicMock:
    resp = MagicMock()
    resp.status_code = status_code
    resp.text = html
    resp.raise_for_status = MagicMock()
    return resp


class TestIsAggregatorUrl:
    def test_linktree(self):
        assert is_aggregator_url("https://linktr.ee/foo") is True
        assert is_aggregator_url("https://www.linktr.ee/bar") is True

    def test_beacons(self):
        assert is_aggregator_url("https://beacons.ai/foo") is True
        assert is_aggregator_url("https://beacons.page/foo") is True

    def test_non_aggregator(self):
        assert is_aggregator_url("https://onlyfans.com/foo") is False
        assert is_aggregator_url("https://instagram.com/foo") is False


class TestResolveLinkInBio:
    def test_extracts_linktree_destinations(self):
        html = (FIXTURES / "linktree_sample.html").read_text()
        with patch("link_in_bio.httpx.get", return_value=_mock_response(html)):
            dests = resolve_link_in_bio("https://linktr.ee/gothgirlnatalie")
        assert "https://onlyfans.com/gothgirlnatalie" in dests
        assert "https://fanvue.com/gothgirlnatalie" in dests
        assert "https://instagram.com/gothgirlnatalie" in dests
        # Internal links and support pages excluded
        assert not any("linktr.ee" in d for d in dests)
        assert not any("mailto:" in d for d in dests)

    def test_extracts_beacons_destinations(self):
        html = (FIXTURES / "beacons_sample.html").read_text()
        with patch("link_in_bio.httpx.get", return_value=_mock_response(html)):
            dests = resolve_link_in_bio("https://beacons.ai/gothgirlnatalie")
        assert "https://onlyfans.com/gothgirlnatalie" in dests
        assert "https://patreon.com/gothgirlnatalie" in dests
        assert not any("beacons.ai" in d for d in dests)

    def test_returns_empty_on_non_aggregator_url(self):
        # We only resolve known aggregators; arbitrary personal domains are skipped
        dests = resolve_link_in_bio("https://example.com/me")
        assert dests == []

    def test_returns_empty_on_http_error(self):
        with patch("link_in_bio.httpx.get", side_effect=Exception("network")):
            dests = resolve_link_in_bio("https://linktr.ee/foo")
        assert dests == []

    def test_deduplicates(self):
        html = """<html><body>
            <a href="https://onlyfans.com/foo">1</a>
            <a href="https://onlyfans.com/foo">2</a>
        </body></html>"""
        with patch("link_in_bio.httpx.get", return_value=_mock_response(html)):
            dests = resolve_link_in_bio("https://linktr.ee/foo")
        assert dests.count("https://onlyfans.com/foo") == 1
```

- [ ] **Step 3: Run tests to confirm they fail**

```bash
python -m pytest tests/test_link_in_bio.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'link_in_bio'`.

- [ ] **Step 4: Implement link_in_bio.py**

Create `scripts/link_in_bio.py`:

```python
# scripts/link_in_bio.py — Resolve Linktree/Beacons pages to destination URLs
from urllib.parse import urlparse
import httpx
from bs4 import BeautifulSoup

_AGGREGATOR_DOMAINS = {
    "linktr.ee",
    "beacons.ai",
    "beacons.page",
}

_EXCLUDED_SCHEMES = {"mailto", "tel", "javascript"}


def is_aggregator_url(url: str) -> bool:
    try:
        host = urlparse(url).hostname or ""
    except ValueError:
        return False
    host = host.lower().removeprefix("www.")
    return host in _AGGREGATOR_DOMAINS


def _host(url: str) -> str:
    return (urlparse(url).hostname or "").lower().removeprefix("www.")


def resolve_link_in_bio(url: str, timeout: float = 10.0) -> list[str]:
    """Fetch an aggregator URL (Linktree/Beacons) and return outbound destination URLs.

    Returns [] on non-aggregator URLs, HTTP errors, or parse failures. Destinations are
    deduplicated, exclude the aggregator's own domain, and exclude mailto/tel/javascript.
    """
    if not is_aggregator_url(url):
        return []

    try:
        r = httpx.get(url, timeout=timeout, follow_redirects=True)
        r.raise_for_status()
    except Exception:
        return []

    source_host = _host(url)
    soup = BeautifulSoup(r.text, "html.parser")

    seen: set[str] = set()
    out: list[str] = []
    for a in soup.find_all("a", href=True):
        href: str = a["href"].strip()
        if not href or href.startswith("#"):
            continue
        scheme = urlparse(href).scheme.lower()
        if scheme in _EXCLUDED_SCHEMES:
            continue
        if scheme not in {"http", "https"}:
            continue
        dest_host = _host(href)
        if not dest_host or dest_host == source_host:
            continue
        # Also skip aggregator helper domains (help.linktr.ee, www.beacons.ai/legal etc)
        if dest_host.endswith(source_host):
            continue
        if href in seen:
            continue
        seen.add(href)
        out.append(href)

    return out
```

- [ ] **Step 5: Run tests to confirm they pass**

```bash
python -m pytest tests/test_link_in_bio.py -v
```

Expected: all 8 tests PASS.

- [ ] **Step 6: Commit**

```bash
git add scripts/link_in_bio.py scripts/tests/test_link_in_bio.py scripts/tests/fixtures/
git commit -m "feat(pipeline): Linktree/Beacons link-in-bio resolver"
```

---

## Task 5: Discover Creator Rewrite

**Files:**
- Modify: `scripts/discover_creator.py` (full rewrite of context/prompt/error-handling paths)
- Create: `scripts/tests/test_discover_creator.py`

Replace `fetch_input_context()` with a dispatch to `apify_details` based on `input_platform_hint`. Resolve link-in-bio aggregators found in `external_urls`. Rewrite Gemini prompt to explicitly ground in provided context. Add tenacity retry around `mark_discovery_failed` with dead-letter fallback. Remove now-duplicated model definitions and manual schema enum injection.

- [ ] **Step 1: Write failing tests**

Create `scripts/tests/test_discover_creator.py`:

```python
# scripts/tests/test_discover_creator.py
import json
from pathlib import Path
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from schemas import DiscoveryInput, InputContext
import discover_creator as dc


def _make_input(platform: str = "instagram", handle: str = "gothgirlnatalie") -> DiscoveryInput:
    return DiscoveryInput(
        run_id=uuid4(),
        creator_id=uuid4(),
        workspace_id=uuid4(),
        input_handle=handle,
        input_url=None,
        input_platform_hint=platform,
    )


class TestFetchInputContext:
    def test_instagram_route_calls_ig_fetcher(self):
        expected = InputContext(handle="x", platform="instagram", bio="hi")
        with patch("discover_creator.fetch_instagram_details", return_value=expected) as mock_ig, \
             patch("discover_creator.fetch_tiktok_details") as mock_tt, \
             patch("discover_creator.get_apify_client"):
            ctx = dc.fetch_input_context(_make_input(platform="instagram", handle="x"))
        mock_ig.assert_called_once()
        mock_tt.assert_not_called()
        assert ctx.bio == "hi"

    def test_tiktok_route_calls_tt_fetcher(self):
        expected = InputContext(handle="y", platform="tiktok", bio="hello")
        with patch("discover_creator.fetch_tiktok_details", return_value=expected) as mock_tt, \
             patch("discover_creator.fetch_instagram_details") as mock_ig, \
             patch("discover_creator.get_apify_client"):
            ctx = dc.fetch_input_context(_make_input(platform="tiktok", handle="y"))
        mock_tt.assert_called_once()
        mock_ig.assert_not_called()

    def test_empty_dataset_propagates(self):
        from apify_details import EmptyDatasetError
        with patch("discover_creator.fetch_instagram_details",
                   side_effect=EmptyDatasetError("login wall")), \
             patch("discover_creator.get_apify_client"):
            with pytest.raises(EmptyDatasetError):
                dc.fetch_input_context(_make_input())

    def test_resolves_aggregator_urls_in_external_urls(self):
        ctx = InputContext(
            handle="x", platform="instagram",
            bio="goth",
            external_urls=["https://linktr.ee/x", "https://direct.site/x"],
        )
        with patch("discover_creator.fetch_instagram_details", return_value=ctx), \
             patch("discover_creator.resolve_link_in_bio",
                   return_value=["https://onlyfans.com/x"]) as mock_resolve, \
             patch("discover_creator.get_apify_client"):
            result_ctx = dc.fetch_input_context(_make_input())
        # Only the aggregator URL should be handed to resolve_link_in_bio
        mock_resolve.assert_called_once_with("https://linktr.ee/x")
        assert "https://onlyfans.com/x" in result_ctx.link_in_bio_destinations


class TestGeminiPromptGrounding:
    def test_prompt_includes_bio_follower_and_external_urls(self):
        ctx = InputContext(
            handle="gothgirlnatalie", platform="instagram",
            bio="goth girl", follower_count=48200,
            external_urls=["https://linktr.ee/gothgirlnatalie"],
            link_in_bio_destinations=["https://onlyfans.com/gothgirlnatalie"],
            source_note="apify/instagram-scraper details mode",
        )
        prompt = dc.build_prompt(ctx)
        assert "goth girl" in prompt
        assert "48200" in prompt or "48,200" in prompt
        assert "linktr.ee/gothgirlnatalie" in prompt
        assert "onlyfans.com/gothgirlnatalie" in prompt
        # Grounding instruction present
        assert "provided context" in prompt.lower() or "do not hallucinate" in prompt.lower()


class TestRunEmptyContextFailsFast:
    def test_empty_context_triggers_mark_failed(self):
        from apify_details import EmptyDatasetError

        fake_sb = MagicMock()
        fake_sb.rpc.return_value.execute.return_value = None

        with patch("discover_creator.get_supabase", return_value=fake_sb), \
             patch("discover_creator.fetch_input_context",
                   side_effect=EmptyDatasetError("login wall")), \
             patch("discover_creator.run_gemini_discovery") as mock_gemini:
            dc.run(_make_input())

        # Gemini never called — we bailed before it
        mock_gemini.assert_not_called()
        # mark_discovery_failed was invoked
        called_rpc_names = [c.args[0] for c in fake_sb.rpc.call_args_list]
        assert "mark_discovery_failed" in called_rpc_names


class TestMarkDiscoveryFailedRetries:
    def test_retries_on_transient_failure(self):
        fake_sb = MagicMock()
        # First 2 calls raise, third succeeds
        fake_sb.rpc.return_value.execute.side_effect = [
            Exception("transient"),
            Exception("transient"),
            MagicMock(),
        ]
        with patch("discover_creator.get_supabase", return_value=fake_sb):
            dc.mark_discovery_failed_with_retry(fake_sb, uuid4(), "the error")
        # 3 total execute() calls means 2 retries + 1 success
        assert fake_sb.rpc.return_value.execute.call_count == 3

    def test_writes_dead_letter_after_exhausting_retries(self, tmp_path, monkeypatch):
        fake_sb = MagicMock()
        fake_sb.rpc.return_value.execute.side_effect = Exception("permanent")
        monkeypatch.setattr(dc, "DEAD_LETTER_PATH", tmp_path / "deadletter.jsonl")
        run_id = uuid4()
        with patch("discover_creator.get_supabase", return_value=fake_sb):
            dc.mark_discovery_failed_with_retry(fake_sb, run_id, "the error")
        contents = (tmp_path / "deadletter.jsonl").read_text()
        assert str(run_id) in contents
        assert "the error" in contents
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
python -m pytest tests/test_discover_creator.py -v
```

Expected: multiple failures (AttributeError for `build_prompt`, `mark_discovery_failed_with_retry`, `DEAD_LETTER_PATH`; Patches against missing symbols).

- [ ] **Step 3: Rewrite discover_creator.py**

Replace the entire contents of `scripts/discover_creator.py` with:

```python
# scripts/discover_creator.py — Discovery and network analysis logic
import json
import argparse
import os
from pathlib import Path
from typing import Optional
from uuid import UUID

import google.generativeai as genai
from tenacity import retry, stop_after_attempt, wait_exponential

from common import get_supabase, get_gemini_key, console
from schemas import (
    DiscoveryInput,
    DiscoveryResult,
    InputContext,
    PLATFORM_VALUES,
)
from apify_details import (
    EmptyDatasetError,
    fetch_instagram_details,
    fetch_tiktok_details,
)
from apify_scraper import get_apify_client, scrape_instagram_profile
from link_in_bio import is_aggregator_url, resolve_link_in_bio

DEAD_LETTER_PATH = Path(os.environ.get(
    "DISCOVERY_DEAD_LETTER_PATH",
    str(Path(__file__).resolve().parent / "discovery_dead_letter.jsonl"),
))


def _clean_schema(obj):
    if isinstance(obj, dict):
        if "anyOf" in obj or "oneOf" in obj:
            variants = obj.get("anyOf") or obj.get("oneOf")
            non_null = [v for v in variants if not (isinstance(v, dict) and v.get("type") == "null")]
            if len(non_null) == 1:
                return _clean_schema({
                    **non_null[0],
                    **{k: v for k, v in obj.items() if k not in ("anyOf", "oneOf", "default", "title")},
                })
        return {
            k: _clean_schema(v)
            for k, v in obj.items()
            if k not in ("default", "title", "minimum", "maximum", "exclusiveMinimum", "exclusiveMaximum")
        }
    if isinstance(obj, list):
        return [_clean_schema(i) for i in obj]
    return obj


def _inline_refs(schema: dict) -> dict:
    defs = schema.get("$defs", {})

    def resolve(obj):
        if isinstance(obj, dict):
            if "$ref" in obj:
                ref_name = obj["$ref"].split("/")[-1]
                return resolve(defs.get(ref_name, obj))
            return {k: resolve(v) for k, v in obj.items() if k != "$defs"}
        if isinstance(obj, list):
            return [resolve(i) for i in obj]
        return obj

    return resolve(schema)


GEMINI_DISCOVERY_SCHEMA = _clean_schema(_inline_refs(DiscoveryResult.model_json_schema()))


def fetch_input_context(inp: DiscoveryInput) -> InputContext:
    """Fetch structured profile context via Apify. Raises EmptyDatasetError on login wall."""
    if not inp.input_handle:
        raise ValueError("input_handle is required — legacy input_url-only path removed")

    platform = (inp.input_platform_hint or "").lower()
    client = get_apify_client()

    if platform == "instagram":
        ctx = fetch_instagram_details(client, inp.input_handle)
    elif platform == "tiktok":
        ctx = fetch_tiktok_details(client, inp.input_handle)
    else:
        raise ValueError(
            f"Unsupported input_platform_hint={platform!r}. "
            f"Supported: instagram, tiktok."
        )

    # Resolve aggregator URLs (Linktree/Beacons) found in the bio
    destinations: list[str] = []
    for url in ctx.external_urls:
        if is_aggregator_url(url):
            destinations.extend(resolve_link_in_bio(url))

    # Deduplicate while preserving order
    seen: set[str] = set()
    unique_destinations: list[str] = []
    for d in destinations:
        if d not in seen:
            seen.add(d)
            unique_destinations.append(d)

    ctx.link_in_bio_destinations = unique_destinations
    return ctx


def build_prompt(ctx: InputContext) -> str:
    ctx_json = ctx.model_dump_json(indent=2)
    return f"""
You are analyzing a creator's online footprint to discover their true identity, aliases, and platforms.

**Ground every field in the provided context.** Do not rely on prior knowledge of this handle. If a field cannot be determined from the context (bio, external URLs, link-in-bio destinations), return null / "unknown" / an empty list rather than guessing.

Do not hallucinate follower counts, niches, or accounts that aren't evidenced in the context.

## Context
```
{ctx_json}
```

## Task
1. Determine the creator's canonical name. If not clearly stated in display_name or bio, use the handle.
2. Infer primary_niche from bio and link-in-bio destination domains (e.g. onlyfans.com → adult creator; patreon.com → subscription creator).
3. Infer monetization_model from link-in-bio destinations (onlyfans/fanvue → subscription; patreon → subscription; shop/store → ecommerce; otherwise unknown).
4. List every account you can identify:
   - The input handle itself as a `proposed_account` with `is_primary=true`.
   - Each link_in_bio_destination as a separate proposed_account (platform inferred from the domain; account_type = monetization for onlyfans/patreon/fanvue/fanplace, link_in_bio for linktr.ee/beacons.ai, social otherwise).
5. Propose funnel edges from the input handle to each destination (edge_type=link_in_bio when routed via an aggregator; direct_link when listed directly in externalUrls).
6. Confidence 0.9+ only when the account appears literally in the context. 0.5–0.8 for strong inference (e.g. matching-handle OF account from a bio hint). Below 0.5 → don't emit.
""".strip()


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
def run_gemini_discovery(ctx: InputContext) -> DiscoveryResult:
    genai.configure(api_key=get_gemini_key())
    model = genai.GenerativeModel("gemini-2.5-flash")
    prompt = build_prompt(ctx)
    resp = model.generate_content(
        prompt,
        generation_config=genai.GenerationConfig(
            response_mime_type="application/json",
            response_schema=GEMINI_DISCOVERY_SCHEMA,
        ),
    )
    return DiscoveryResult.model_validate_json(resp.text)


def _write_dead_letter(run_id: UUID, error: str) -> None:
    """Append failed run to dead-letter file when mark_discovery_failed RPC itself fails."""
    try:
        DEAD_LETTER_PATH.parent.mkdir(parents=True, exist_ok=True)
        entry = json.dumps({"run_id": str(run_id), "error": error})
        with DEAD_LETTER_PATH.open("a") as f:
            f.write(entry + "\n")
    except Exception as e:
        console.log(f"[red]Dead-letter write failed: {e}[/red]")


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=5), reraise=True)
def _call_mark_discovery_failed(sb, run_id: UUID, error: str) -> None:
    sb.rpc("mark_discovery_failed", {
        "p_run_id": str(run_id),
        "p_error": error,
    }).execute()


def mark_discovery_failed_with_retry(sb, run_id: UUID, error: str) -> None:
    """Call mark_discovery_failed RPC with tenacity retry; dead-letter on final failure."""
    try:
        _call_mark_discovery_failed(sb, run_id, error)
    except Exception as nested:
        console.log(f"[red]mark_discovery_failed exhausted retries: {nested}[/red]")
        _write_dead_letter(run_id, error)


def commit(run_id: UUID, result: DiscoveryResult):
    sb = get_supabase()
    data = result.model_dump(mode="json")
    creator_data = {
        "canonical_name": data["canonical_name"],
        "known_usernames": data["known_usernames"],
        "display_name_variants": data["display_name_variants"],
        "primary_platform": data["primary_platform"],
        "primary_niche": data["primary_niche"],
        "monetization_model": data["monetization_model"],
    }
    sb.rpc("commit_discovery_result", {
        "p_run_id": str(run_id),
        "p_creator_data": creator_data,
        "p_accounts": data["proposed_accounts"],
        "p_funnel_edges": data["proposed_funnel_edges"],
    }).execute()
    console.log(f"[green]Committed discovery run {run_id}[/green]")


def run(inp: DiscoveryInput) -> None:
    sb = get_supabase()
    try:
        console.log(f"[blue]Starting discovery run {inp.run_id} (@{inp.input_handle}, {inp.input_platform_hint})[/blue]")
        ctx = fetch_input_context(inp)
        console.log(f"[cyan]Context: bio={bool(ctx.bio)} followers={ctx.follower_count} external_urls={len(ctx.external_urls)} destinations={len(ctx.link_in_bio_destinations)}[/cyan]")

        result = run_gemini_discovery(ctx)
        commit(inp.run_id, result)

        # Kick off a small IG posts scrape for the primary account
        ig_accounts = [a for a in result.proposed_accounts if a.platform == "instagram"]
        if ig_accounts:
            ig_handle = ig_accounts[0].handle or (
                ig_accounts[0].url.strip("/").split("/")[-1] if ig_accounts[0].url else None
            )
            if ig_handle:
                console.log(f"[cyan]Dispatching Apify posts scrape for @{ig_handle}[/cyan]")
                scrape_instagram_profile(str(inp.workspace_id), ig_handle, limit=5)

    except EmptyDatasetError as e:
        console.log(f"[yellow]Discovery aborted — empty context: {e}[/yellow]")
        mark_discovery_failed_with_retry(sb, inp.run_id, f"empty_context: {e}")
    except Exception as e:
        console.log(f"[red]Fatal discovery error: {e}[/red]")
        mark_discovery_failed_with_retry(sb, inp.run_id, str(e))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", required=True, type=str)
    args = parser.parse_args()

    sb = get_supabase()
    resp = sb.table("discovery_runs").select("*").eq("id", args.run_id).single().execute()
    data = resp.data
    if not data:
        console.log(f"[red]Run {args.run_id} not found[/red]")
        exit(1)

    inp = DiscoveryInput(
        run_id=data["id"],
        creator_id=data["creator_id"],
        workspace_id=data["workspace_id"],
        input_handle=data["input_handle"],
        input_url=data["input_url"],
        input_platform_hint=data["input_platform_hint"],
    )
    run(inp)
```

- [ ] **Step 4: Extract `get_apify_client` to be importable**

Verify `apify_scraper.py` exports `get_apify_client`. If the function is already defined there (line 16), no change is needed — it's just importable now. Confirm with:

```bash
cd "/Users/simon/OS/Living VAULT/Content OS/The Hub/scripts"
python -c "from apify_scraper import get_apify_client; print('ok')"
```

Expected: `ok`.

- [ ] **Step 5: Run discover_creator tests to confirm they pass**

```bash
python -m pytest tests/test_discover_creator.py -v
```

Expected: all 7 tests PASS.

- [ ] **Step 6: Run full test suite to catch regressions**

```bash
python -m pytest tests/ -v
```

Expected: all 21 tests PASS (schemas 8 + apify_details 6 + link_in_bio 8 — plus discover_creator 7 minus overlaps; exact count ≥21).

- [ ] **Step 7: Commit**

```bash
git add scripts/discover_creator.py scripts/tests/test_discover_creator.py
git commit -m "feat(pipeline): Apify-grounded context + grounded Gemini prompt + retry on mark_failed"
```

---

## Task 6: Worker Error Surfacing

**Files:**
- Modify: `scripts/worker.py:44-54`
- Create: `scripts/tests/test_worker.py`

`asyncio.gather(*futures, return_exceptions=True)` at worker.py:54 silently swallows per-task exceptions. Iterate results and log any that are Exception instances.

- [ ] **Step 1: Write failing test**

Create `scripts/tests/test_worker.py`:

```python
# scripts/tests/test_worker.py
import asyncio
from unittest.mock import MagicMock, patch

import pytest


class TestLogGatherResults:
    def test_logs_exceptions_but_does_not_raise(self):
        from worker import log_gather_results

        mock_log = MagicMock()
        results = [None, ValueError("boom"), None, RuntimeError("also boom")]
        claimed = [
            {"id": "a"}, {"id": "b"}, {"id": "c"}, {"id": "d"},
        ]

        log_gather_results(results, claimed, logger=mock_log)

        # Two errors logged
        assert mock_log.call_count == 2
        # The error messages reference the run IDs
        logged = " ".join(str(c.args[0]) for c in mock_log.call_args_list)
        assert "b" in logged
        assert "d" in logged
        assert "boom" in logged
```

- [ ] **Step 2: Run test to confirm it fails**

```bash
python -m pytest tests/test_worker.py -v
```

Expected: FAIL with `ImportError: cannot import name 'log_gather_results'`.

- [ ] **Step 3: Modify worker.py**

Replace `scripts/worker.py` contents with:

```python
# scripts/worker.py — Polling worker for discovery pipeline
import os
import asyncio
from concurrent.futures import ThreadPoolExecutor
from common import get_supabase, console
from discover_creator import run, DiscoveryInput
from dotenv import load_dotenv

load_dotenv()

POLL_INTERVAL_SECONDS = int(os.environ.get("POLL_INTERVAL_SECONDS", "30"))
MAX_CONCURRENT_RUNS = int(os.environ.get("MAX_CONCURRENT_RUNS", "5"))


def process_single(row: dict):
    inp = DiscoveryInput(
        run_id=row["id"],
        creator_id=row["creator_id"],
        workspace_id=row["workspace_id"],
        input_handle=row["input_handle"],
        input_url=row["input_url"],
        input_platform_hint=row["input_platform_hint"],
    )
    run(inp)


def log_gather_results(results: list, claimed: list[dict], logger=None) -> None:
    """Surface exceptions from asyncio.gather(..., return_exceptions=True).

    Without this, per-task crashes are silently absorbed. Logs one line per error
    that includes the run id so we can correlate back to discovery_runs.
    """
    log = logger or console.log
    for result, row in zip(results, claimed):
        if isinstance(result, BaseException):
            log(f"[red]Run {row.get('id')} failed in worker: {type(result).__name__}: {result}[/red]")


async def poll_loop(args=None):
    sb = get_supabase()
    console.log(f"[green]Worker started. Polling every {POLL_INTERVAL_SECONDS}s. Max concurrency: {MAX_CONCURRENT_RUNS}.[/green]")

    with ThreadPoolExecutor(max_workers=MAX_CONCURRENT_RUNS) as pool:
        while True:
            try:
                resp = sb.table("discovery_runs").select("*").eq("status", "pending").limit(MAX_CONCURRENT_RUNS).execute()
                runs = resp.data

                if runs:
                    console.log(f"[cyan]Found {len(runs)} pending runs. Claiming...[/cyan]")
                    claimed = []
                    for r in runs:
                        claim_res = sb.table("discovery_runs").update({"status": "processing"})\
                            .eq("id", r["id"]).eq("status", "pending").execute()
                        if claim_res.data:
                            claimed.append(claim_res.data[0])

                    if claimed:
                        loop = asyncio.get_running_loop()
                        futures = [loop.run_in_executor(pool, process_single, c) for c in claimed]
                        results = await asyncio.gather(*futures, return_exceptions=True)
                        log_gather_results(results, claimed)

            except Exception as e:
                console.log(f"[red]Error in polling loop: {e}[/red]")

            if getattr(args, "once", False):
                break

            await asyncio.sleep(POLL_INTERVAL_SECONDS)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--once", action="store_true", help="Run one iteration and exit")
    args = parser.parse_args()
    asyncio.run(poll_loop(args))
```

- [ ] **Step 4: Run test to confirm it passes**

```bash
python -m pytest tests/test_worker.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add scripts/worker.py scripts/tests/test_worker.py
git commit -m "fix(worker): surface per-task exceptions from asyncio.gather"
```

---

## Task 7: Full Test Suite + Push

- [ ] **Step 1: Run full suite**

```bash
cd "/Users/simon/OS/Living VAULT/Content OS/The Hub/scripts"
python -m pytest tests/ -v
```

Expected: all tests PASS.

- [ ] **Step 2: TypeScript typecheck (migration ripple)**

```bash
cd "/Users/simon/OS/Living VAULT/Content OS/The Hub"
npx tsc --noEmit
```

Expected: exit 0.

- [ ] **Step 3: Push branch**

```bash
git push -u origin phase-2-discovery-rebuild
```

---

## Task 8: Live Smoke Test — Re-run All 3 Creators

This validates the rebuild against real data. Each creator gets a fresh discovery_run via `retry_creator_discovery` RPC, the worker processes it end-to-end, and we verify the committed result reflects Apify truth (not Gemini hallucination from garbage context).

**Preconditions:**
- Branch merged OR checked out locally with `.env` credentials.
- `APIFY_TOKEN` has sufficient credit (~3 × $0.005 = $0.015).
- `SUPABASE_SERVICE_ROLE_KEY`, `GEMINI_API_KEY` set in `scripts/.env`.

- [ ] **Step 1: Fetch the 3 creator IDs via Supabase MCP**

Use Supabase MCP `execute_sql`:

```sql
SELECT id, canonical_name, known_usernames, last_discovery_error, onboarding_status
FROM creators
ORDER BY created_at;
```

Record the three IDs. Expected: Natalie Vox, Aria Swan, Esmae.

- [ ] **Step 2: Queue a new discovery run for each creator**

For each creator ID, call the retry RPC via Supabase MCP `execute_sql`:

```sql
-- Replace <creator_id> for each of the 3 creators
SELECT retry_creator_discovery(
  '<creator_id>'::uuid,
  (SELECT user_id FROM workspace_members LIMIT 1)
);
```

Expected: each call returns a new `discovery_runs.id`. Record all 3 new run IDs.

Verify the runs are queued:

```sql
SELECT id, creator_id, input_handle, input_platform_hint, status, attempt_number
FROM discovery_runs
WHERE status = 'pending'
ORDER BY started_at DESC
LIMIT 3;
```

Expected: 3 rows, all `status='pending'`, one per creator.

- [ ] **Step 3: Run the worker once to process the queue**

```bash
cd "/Users/simon/OS/Living VAULT/Content OS/The Hub/scripts"
python worker.py --once
```

Expected console output (abbreviated):
```
Worker started. Polling every 30s. Max concurrency: 5.
Found 3 pending runs. Claiming...
Starting discovery run <uuid> (@natalievox, instagram)
Context: bio=True followers=... external_urls=... destinations=...
Committed discovery run <uuid>
...
```

No `[red]Fatal discovery error` lines. No `[red]Run ... failed in worker` lines.

- [ ] **Step 4: Verify DB state reflects Apify truth**

Via Supabase MCP `execute_sql`:

```sql
SELECT
  c.canonical_name,
  c.primary_niche,
  c.monetization_model,
  c.onboarding_status,
  c.last_discovery_error,
  p.bio,
  p.follower_count,
  p.following_count,
  p.post_count,
  p.avatar_url IS NOT NULL AS has_avatar
FROM creators c
LEFT JOIN profiles p ON p.creator_id = c.id AND p.is_primary = true
ORDER BY c.created_at;
```

Expected for each row:
- `onboarding_status = 'ready'`
- `last_discovery_error IS NULL` (cleared by the successful retry)
- `bio` is non-null and non-empty
- `follower_count` > 0
- `has_avatar = true`

- [ ] **Step 5: Verify funnel edges populated (for creators with link-in-bio)**

```sql
SELECT
  c.canonical_name,
  COUNT(fe.id) AS edge_count,
  array_agg(fe.edge_type) AS edge_types
FROM creators c
LEFT JOIN funnel_edges fe ON fe.creator_id = c.id
GROUP BY c.id, c.canonical_name
ORDER BY c.canonical_name;
```

Expected: at least one creator has funnel edges > 0 (whichever creators have linktr.ee / beacons.ai destinations). Edge types should be in {`link_in_bio`, `direct_link`, `cta_mention`, `qr_code`, `inferred`}.

- [ ] **Step 6: Verify no dead-letter entries**

```bash
test -f "/Users/simon/OS/Living VAULT/Content OS/The Hub/scripts/discovery_dead_letter.jsonl" \
  && cat "/Users/simon/OS/Living VAULT/Content OS/The Hub/scripts/discovery_dead_letter.jsonl" \
  || echo "no dead letter"
```

Expected: `no dead letter`.

- [ ] **Step 7: Verify UI**

Open the app in Chrome DevTools MCP:

```
navigate_page → http://localhost:3000/creators
```

Expected:
- All 3 creator cards render with updated `bio`, `follower_count`, `avatar_url`
- No "Processing" banners
- No "Failed" states

Check one detail page:

```
navigate_page → http://localhost:3000/creators/<slug>
```

Expected: stats strip shows accurate follower counts; network section shows discovered accounts; no stale error banners.

---

## Task 9: Documentation Updates

**Files:**
- Modify: `PROJECT_STATE.md`

- [ ] **Step 1: Update §20 Known Limitations**

In `PROJECT_STATE.md` §20, delete the final row (the "Discovery pipeline broken (httpx)" entry). The pipeline now uses Apify for context.

- [ ] **Step 2: Append Decisions Log entry**

At the bottom of `PROJECT_STATE.md`, append:

```markdown
- 2026-04-24: Discovery pipeline rebuilt. `fetch_input_context()` now dispatches to Apify (`apify/instagram-scraper` details mode for IG, `clockworks/tiktok-scraper` for TT) instead of httpx-against-login-walls. Link-in-bio resolver follows Linktree/Beacons destinations. Gemini prompt explicitly grounds in provided context rather than prior knowledge. `edge_type` enum created (migration 20260424150000) — fixes audit §1.1.7 latent crash. Pydantic `Literal` on `Platform` and `EdgeType` closes audit item 15 validation gap. `patreon` added to platform enum in schema module. `mark_discovery_failed` gets tenacity retry + dead-letter fallback. Worker surfaces per-task exceptions instead of swallowing them. Smoke-tested by re-running discovery for all 3 existing creators — bio, follower counts, external URLs all now reflect Apify truth.
```

- [ ] **Step 3: Verify docs build still works and commit**

```bash
cd "/Users/simon/OS/Living VAULT/Content OS/The Hub"
git add PROJECT_STATE.md
git commit -m "docs(state): discovery pipeline rebuilt with Apify context + grounded prompt"
git push
```

---

## Done Criteria

- [ ] All 9 tasks checked off
- [ ] `python -m pytest scripts/tests/ -v` → all green
- [ ] `npx tsc --noEmit` → exit 0
- [ ] 3 creators have populated `bio`, `follower_count`, non-null `avatar_url` in Supabase
- [ ] `discovery_runs` shows 3 new rows with `status='completed'` and `error_message IS NULL`
- [ ] `funnel_edges` contains at least 1 row (proves `::edge_type` cast no longer crashes)
- [ ] `discovery_dead_letter.jsonl` does not exist OR is empty
- [ ] `PROJECT_STATE.md` §20 updated, Decisions Log entry appended
- [ ] Branch `phase-2-discovery-rebuild` pushed to origin, PR opened

---

## Rollback Plan

If the live smoke test reveals a regression that can't be fixed in-session:

1. `git revert` the series of commits back to `main`.
2. The `edge_type` enum migration is idempotent to revert: `DROP TYPE edge_type` (safe because `funnel_edges` starts at 0 rows and any rows created during the test would be rolled back with the code).
3. Existing creators in `ready` state with pre-test data are unaffected — retry RPCs only create new `discovery_runs` rows; they don't mutate creators until the commit step.
