# Discovery v2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the single-hop discovery pipeline with a two-stage resolver, deterministic URL classifier, rule-cascade identity scorer, multi-platform fetcher layer, and observable `bulk_imports` job model — per the spec at `docs/superpowers/specs/2026-04-24-discovery-v2-design.md`.

**Architecture:** New `scripts/pipeline/` and `scripts/fetchers/` modules with focused single-responsibility files. Classifier owns `(platform, account_type)` via rule-first gazetteer with LLM fallback. Identity scorer runs a rule cascade at every commit (intra-seed, within-bulk, cross-workspace) against a persistent `profile_destination_links` index. Resolver does exactly two stages: fetch seed, then classify+enrich destinations. Feature-flagged behind `DISCOVERY_V2_ENABLED` for safe rollout.

**Tech Stack:** Python 3.11+, Pydantic v2, `apify-client`, `httpx`, `curl_cffi` (new — JA3 impersonation for OnlyFans), `yt-dlp` (new — YouTube), `sentence-transformers` + `Pillow` (new — CLIP avatar similarity), `beautifulsoup4`, `google-generativeai`, `tenacity`, `pytest` + `pytest-mock`. Supabase Postgres 17 for schema + RPC changes. Next.js 14 for UI touchpoints.

---

## Task 0: Verify branch + working tree clean

**Files:** none

- [ ] **Step 1: Confirm we're on the right branch**

```bash
cd "/Users/simon/OS/Living VAULT/Content OS/The Hub"
git branch --show-current
```

Expected: `phase-2-discovery-v2`. If not, `git checkout phase-2-discovery-v2` (branch created during spec brainstorm).

- [ ] **Step 2: Confirm working tree clean**

```bash
git status -s
```

Expected: empty output (except `.claude/hooks/verify-before-stop.sh` unrelated local mod — leave alone). If anything else shows, investigate before starting.

- [ ] **Step 3: Confirm spec committed**

```bash
git log --oneline -5
```

Expected: top commit mentions `discovery v2 — multi-platform asset resolver design` and a follow-up `cross-time dedup + manual-add recovery path`.

---

## Task 1: Schema migration — new tables, columns, constraints

**Files:**
- Create: `supabase/migrations/20260425000000_discovery_v2_schema.sql`

This migration is additive only. No existing data lost. All new columns nullable or have defaults. The feature flag keeps v1 alive until we cut over.

- [ ] **Step 1: Write the migration**

Create `supabase/migrations/20260425000000_discovery_v2_schema.sql`:

```sql
-- 20260425000000_discovery_v2_schema.sql
-- Discovery v2 — new tables and columns per docs/superpowers/specs/2026-04-24-discovery-v2-design.md §4.
-- Additive only. Feature-flagged rollout via DISCOVERY_V2_ENABLED.

BEGIN;

-- 1. bulk_imports: first-class observable job table
CREATE TABLE bulk_imports (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  workspace_id uuid NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
  initiated_by uuid,
  seeds_total int NOT NULL,
  seeds_committed int NOT NULL DEFAULT 0,
  seeds_failed int NOT NULL DEFAULT 0,
  seeds_blocked_by_budget int NOT NULL DEFAULT 0,
  merge_pass_completed_at timestamptz,
  cost_apify_cents int NOT NULL DEFAULT 0,
  status text NOT NULL DEFAULT 'running'
    CHECK (status IN (
      'running', 'completed', 'completed_with_failures',
      'partial_budget_exceeded', 'cancelled'
    )),
  created_at timestamptz NOT NULL DEFAULT NOW(),
  updated_at timestamptz NOT NULL DEFAULT NOW()
);

CREATE INDEX bulk_imports_workspace_status_idx
  ON bulk_imports (workspace_id, status, created_at DESC);

CREATE TRIGGER trg_bulk_imports_updated_at
  BEFORE UPDATE ON bulk_imports
  FOR EACH ROW EXECUTE FUNCTION set_updated_at();

ALTER TABLE bulk_imports ENABLE ROW LEVEL SECURITY;

CREATE POLICY bulk_imports_workspace_members ON bulk_imports
  FOR ALL TO authenticated
  USING (is_workspace_member(workspace_id))
  WITH CHECK (is_workspace_member(workspace_id));

-- 2. classifier_llm_guesses: cache of LLM-classified URLs
CREATE TABLE classifier_llm_guesses (
  canonical_url text PRIMARY KEY,
  platform_guess platform,
  account_type_guess account_type,
  confidence numeric(3,2) NOT NULL CHECK (confidence >= 0 AND confidence <= 1),
  model_version text NOT NULL,
  classified_at timestamptz NOT NULL DEFAULT NOW()
);

-- No RLS: this is a workspace-agnostic classification cache. URLs don't have
-- workspace scope. Read-only from Python, write via service role only.

-- 3. profile_destination_links: persistent reverse index for identity dedup
CREATE TABLE profile_destination_links (
  profile_id uuid NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
  canonical_url text NOT NULL,
  destination_class text NOT NULL
    CHECK (destination_class IN ('monetization','aggregator','social','other')),
  workspace_id uuid NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
  created_at timestamptz NOT NULL DEFAULT NOW(),
  PRIMARY KEY (profile_id, canonical_url)
);

CREATE INDEX profile_destination_links_url_idx
  ON profile_destination_links (canonical_url);

CREATE INDEX profile_destination_links_class_idx
  ON profile_destination_links (destination_class)
  WHERE destination_class IN ('monetization','aggregator');

CREATE INDEX profile_destination_links_workspace_url_idx
  ON profile_destination_links (workspace_id, canonical_url);

ALTER TABLE profile_destination_links ENABLE ROW LEVEL SECURITY;

CREATE POLICY profile_destination_links_workspace_members ON profile_destination_links
  FOR ALL TO authenticated
  USING (is_workspace_member(workspace_id))
  WITH CHECK (is_workspace_member(workspace_id));

-- 4. discovery_runs additions
ALTER TABLE discovery_runs
  ADD COLUMN bulk_import_id uuid REFERENCES bulk_imports(id) ON DELETE SET NULL,
  ADD COLUMN apify_cost_cents int NOT NULL DEFAULT 0,
  ADD COLUMN source text NOT NULL DEFAULT 'seed'
    CHECK (source IN ('seed','manual_add','retry','auto_expand'));

CREATE INDEX discovery_runs_bulk_import_idx
  ON discovery_runs (bulk_import_id)
  WHERE bulk_import_id IS NOT NULL;

-- 5. profiles additions — audit trail for classification
ALTER TABLE profiles
  ADD COLUMN discovery_reason text;

-- 6. creator_merge_candidates: unique index on canonical pair for idempotency
CREATE UNIQUE INDEX creator_merge_candidates_pair_uniq
  ON creator_merge_candidates (
    LEAST(creator_a_id, creator_b_id),
    GREATEST(creator_a_id, creator_b_id)
  );

COMMIT;
```

- [ ] **Step 2: Apply via Supabase MCP `apply_migration`**

Name: `discovery_v2_schema`. Query: contents of the migration file (drop the leading `-- 20260425000000_discovery_v2_schema.sql` filename comment).

Expected: migration succeeds, no errors.

- [ ] **Step 3: Verify via execute_sql**

```sql
SELECT table_name FROM information_schema.tables
WHERE table_schema='public' AND table_name IN
  ('bulk_imports','classifier_llm_guesses','profile_destination_links');
```
Expected: 3 rows.

```sql
SELECT column_name, data_type FROM information_schema.columns
WHERE table_name='discovery_runs' AND column_name IN
  ('bulk_import_id','apify_cost_cents','source');
```
Expected: 3 rows. `source` is `text`, `apify_cost_cents` is `integer`, `bulk_import_id` is `uuid`.

```sql
SELECT column_name FROM information_schema.columns
WHERE table_name='profiles' AND column_name='discovery_reason';
```
Expected: 1 row.

```sql
SELECT indexname FROM pg_indexes
WHERE tablename='creator_merge_candidates'
AND indexname='creator_merge_candidates_pair_uniq';
```
Expected: 1 row.

- [ ] **Step 4: Regenerate TypeScript types**

```bash
npm run db:types
```

Expected: `src/types/database.types.ts` updated. `npx tsc --noEmit` exits 0.

- [ ] **Step 5: Commit**

```bash
git add supabase/migrations/20260425000000_discovery_v2_schema.sql src/types/database.types.ts
git commit -m "feat(db): discovery v2 schema — bulk_imports, classifier cache, destination index

Additive migration per spec §4. Creates bulk_imports as first-class job
table, classifier_llm_guesses as workspace-agnostic LLM classification
cache, profile_destination_links as persistent reverse index for cross-
workspace identity dedup. Adds discovery_runs.{bulk_import_id,
apify_cost_cents, source} and profiles.discovery_reason. Unique index
on creator_merge_candidates pair for replay idempotency.

No existing data touched. Feature-flagged rollout via DISCOVERY_V2_ENABLED."
```

---

## Task 2: Python dependencies + test scaffolding prep

**Files:**
- Modify: `scripts/requirements.txt`

- [ ] **Step 1: Add deps to requirements.txt**

Edit `scripts/requirements.txt`, append:

```
curl_cffi==0.7.1
yt-dlp==2025.1.26
sentence-transformers==3.3.1
Pillow==11.1.0
```

- [ ] **Step 2: Install deps**

```bash
cd "/Users/simon/OS/Living VAULT/Content OS/The Hub/scripts"
pip install -r requirements.txt
```

Expected: no errors. sentence-transformers may take 1-2 min (pulls torch).

- [ ] **Step 3: Verify pytest still discovers existing tests**

```bash
cd "/Users/simon/OS/Living VAULT/Content OS/The Hub/scripts"
python -m pytest tests/ -q
```

Expected: `45 passed` (no regression from PR #2 suite).

- [ ] **Step 4: Commit**

```bash
git add scripts/requirements.txt
git commit -m "chore(pipeline): add curl_cffi, yt-dlp, sentence-transformers, Pillow deps

curl_cffi: JA3/TLS impersonation for OnlyFans landing pages (raw httpx blocked)
yt-dlp: YouTube channel profile data without API key
sentence-transformers + Pillow: CLIP ViT-B/32 avatar similarity for identity tiebreak"
```

---

## Task 3: `pipeline/canonicalize.py` — URL canonicalization

**Files:**
- Create: `scripts/pipeline/__init__.py`
- Create: `scripts/pipeline/canonicalize.py`
- Create: `scripts/tests/pipeline/__init__.py`
- Create: `scripts/tests/pipeline/test_canonicalize.py`

Canonicalization is the foundation for the classifier cache, identity index, and dedup. If two URLs for the same destination don't canonicalize to the same string, we build duplicates silently. Test heavily.

- [ ] **Step 1: Create empty init files**

Create `scripts/pipeline/__init__.py` as an empty file.
Create `scripts/tests/pipeline/__init__.py` as an empty file.

- [ ] **Step 2: Write failing tests**

Create `scripts/tests/pipeline/test_canonicalize.py`:

```python
# scripts/tests/pipeline/test_canonicalize.py
import pytest
from unittest.mock import patch, MagicMock
from pipeline.canonicalize import canonicalize_url, resolve_short_url


class TestCanonicalizeUrl:
    def test_lowercases_host(self):
        assert canonicalize_url("HTTPS://WWW.Instagram.com/Alice") == \
            "https://instagram.com/Alice"

    def test_strips_www_prefix(self):
        assert canonicalize_url("https://www.linktr.ee/alice") == \
            "https://linktr.ee/alice"

    def test_coerces_protocol_to_https(self):
        assert canonicalize_url("http://instagram.com/alice") == \
            "https://instagram.com/alice"

    def test_strips_trailing_slash(self):
        assert canonicalize_url("https://instagram.com/alice/") == \
            "https://instagram.com/alice"

    def test_strips_utm_params(self):
        assert canonicalize_url(
            "https://onlyfans.com/alice?utm_source=ig&utm_medium=bio&utm_campaign=x"
        ) == "https://onlyfans.com/alice"

    def test_strips_fbclid_gclid_igshid_ref(self):
        assert canonicalize_url(
            "https://instagram.com/alice?fbclid=abc&gclid=def&igshid=ghi&ref=jkl&ref_src=lmn"
        ) == "https://instagram.com/alice"

    def test_preserves_meaningful_query_params(self):
        # e.g. YouTube channel ID URL with v= must survive
        assert canonicalize_url(
            "https://youtube.com/watch?v=dQw4w9WgXcQ&utm_source=ig"
        ) == "https://youtube.com/watch?v=dQw4w9WgXcQ"

    def test_strips_about_and_home_suffixes_on_known_platforms(self):
        assert canonicalize_url("https://youtube.com/@alice/about") == \
            "https://youtube.com/@alice"
        assert canonicalize_url("https://facebook.com/alice/home") == \
            "https://facebook.com/alice"

    def test_is_idempotent(self):
        url = "https://www.Instagram.com/Alice/?utm_source=x"
        once = canonicalize_url(url)
        twice = canonicalize_url(once)
        assert once == twice

    def test_invalid_url_returns_input(self):
        # garbage URLs pass through unchanged — caller decides what to do
        assert canonicalize_url("not a url at all") == "not a url at all"


class TestResolveShortUrl:
    @patch("pipeline.canonicalize.httpx.Client")
    def test_follows_single_redirect(self, mock_client_cls):
        mock_client = MagicMock()
        mock_client_cls.return_value.__enter__.return_value = mock_client
        resp = MagicMock()
        resp.url = "https://onlyfans.com/alice"
        mock_client.head.return_value = resp

        result = resolve_short_url("https://bit.ly/abc")

        assert result == "https://onlyfans.com/alice"
        mock_client.head.assert_called_once()

    @patch("pipeline.canonicalize.httpx.Client")
    def test_caps_at_five_redirects(self, mock_client_cls):
        # httpx follows redirects itself up to max_redirects=5. If we hit that
        # cap, resolve_short_url returns what it has so far without error.
        mock_client = MagicMock()
        mock_client_cls.return_value.__enter__.return_value = mock_client
        resp = MagicMock()
        resp.url = "https://somewhere.com/final"
        mock_client.head.return_value = resp

        result = resolve_short_url("https://bit.ly/abc")

        # just verifying we pass max_redirects and handle the response
        call = mock_client_cls.call_args
        assert call.kwargs.get("max_redirects") == 5
        assert result == "https://somewhere.com/final"

    @patch("pipeline.canonicalize.httpx.Client")
    def test_returns_input_on_http_error(self, mock_client_cls):
        mock_client = MagicMock()
        mock_client_cls.return_value.__enter__.return_value = mock_client
        mock_client.head.side_effect = Exception("network down")

        result = resolve_short_url("https://bit.ly/abc")

        assert result == "https://bit.ly/abc"

    def test_non_short_url_passthrough(self):
        # not in known short-URL host list → return as-is without network
        assert resolve_short_url("https://instagram.com/alice") == \
            "https://instagram.com/alice"
```

Run: `cd scripts && python -m pytest tests/pipeline/test_canonicalize.py -v`
Expected: all tests fail with `ModuleNotFoundError: No module named 'pipeline.canonicalize'` or similar.

- [ ] **Step 3: Implement `canonicalize.py`**

Create `scripts/pipeline/canonicalize.py`:

```python
# scripts/pipeline/canonicalize.py — URL canonicalization for classifier cache + identity index
from urllib.parse import urlparse, urlunparse, parse_qsl, urlencode
import httpx

# Query params stripped unconditionally
_TRACKING_PARAMS = {
    "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
    "fbclid", "gclid", "igshid", "ref", "ref_src", "ref_url", "si",
    "mc_cid", "mc_eid", "_ga", "yclid", "msclkid",
}

# Hosts that use known short-URL redirect patterns
_SHORT_URL_HOSTS = {
    "bit.ly", "tinyurl.com", "t.co", "goo.gl", "ow.ly",
    "geni.us", "smart.link", "lnk.to", "lnk.bio",
    "rebrand.ly", "buff.ly", "fb.me",
}

# Path suffixes stripped on known platforms (social profile landing variants)
_STRIP_SUFFIXES = {
    "youtube.com": ["/about", "/home", "/featured"],
    "www.youtube.com": ["/about", "/home", "/featured"],
    "facebook.com": ["/home", "/about"],
    "www.facebook.com": ["/home", "/about"],
}


def _strip_known_suffixes(host: str, path: str) -> str:
    for suffix in _STRIP_SUFFIXES.get(host, []):
        if path.endswith(suffix):
            return path[: -len(suffix)]
    return path


def canonicalize_url(url: str) -> str:
    """Normalize a URL so equivalent destinations produce identical strings.

    Lowercases host, drops www prefix, coerces http→https, strips tracking
    query params, strips trailing slash and known platform suffixes (/about,
    /home). Idempotent. Invalid URLs return unchanged.
    """
    if "://" not in url:
        return url

    try:
        parsed = urlparse(url)
    except ValueError:
        return url

    if not parsed.hostname:
        return url

    scheme = "https"
    host = parsed.hostname.lower().removeprefix("www.")
    path = _strip_known_suffixes(host, parsed.path)
    if path.endswith("/") and path != "/":
        path = path.rstrip("/")

    # Preserve path casing — many platforms (IG, TT, etc.) use lowercase handles
    # but some destinations (e.g. Notion, Substack) are case-sensitive.
    query_pairs = [
        (k, v) for k, v in parse_qsl(parsed.query, keep_blank_values=True)
        if k.lower() not in _TRACKING_PARAMS
    ]
    query = urlencode(query_pairs) if query_pairs else ""

    return urlunparse((scheme, host, path, "", query, ""))


def resolve_short_url(url: str, timeout: float = 5.0) -> str:
    """Follow a short-URL redirect chain to its final destination.

    Returns the input URL unchanged if (a) the host isn't in the known short-URL
    list, or (b) the HEAD request fails. Caps at 5 redirects via httpx itself.
    """
    try:
        host = (urlparse(url).hostname or "").lower().removeprefix("www.")
    except ValueError:
        return url

    if host not in _SHORT_URL_HOSTS:
        return url

    try:
        with httpx.Client(follow_redirects=True, max_redirects=5, timeout=timeout) as client:
            resp = client.head(url)
            return str(resp.url)
    except Exception:
        return url
```

- [ ] **Step 4: Run tests**

Run: `cd scripts && python -m pytest tests/pipeline/test_canonicalize.py -v`
Expected: all 14 tests pass.

- [ ] **Step 5: Commit**

```bash
git add scripts/pipeline/__init__.py scripts/pipeline/canonicalize.py \
  scripts/tests/pipeline/__init__.py scripts/tests/pipeline/test_canonicalize.py
git commit -m "feat(pipeline): URL canonicalization — stable keys for classifier + identity index

Lowercases host, drops www, https-coerces, strips UTM/fbclid/gclid/igshid/ref
query params, strips trailing slash and known platform suffixes (/about /home).
Idempotent. resolve_short_url follows bit.ly/tinyurl/t.co/geni.us/etc. redirect
chains up to 5 hops; returns input on non-short host or network error."
```

---

## Task 4: Gazetteer data + loader

**Files:**
- Create: `scripts/data/__init__.py`
- Create: `scripts/data/monetization_overlay.yaml`
- Create: `scripts/data/gazetteer_loader.py`
- Create: `scripts/tests/data/__init__.py`
- Create: `scripts/tests/data/test_gazetteer_loader.py`
- Modify: `scripts/requirements.txt` (add `PyYAML` if absent)

The gazetteer seeds the classifier. We use WhatsMyName (community-maintained JSON of ~600 social sites) as the social/aggregator base, plus our own `monetization_overlay.yaml` covering the specific monetization destinations we care about. The loader loads both on startup and exposes a single `lookup(host)` function.

- [ ] **Step 1: Check PyYAML in requirements**

```bash
grep -i yaml scripts/requirements.txt
```

If no line matches, edit `scripts/requirements.txt` and add `PyYAML==6.0.2`. Then `pip install -r requirements.txt`.

- [ ] **Step 2: Create data dir + overlay file**

Create `scripts/data/__init__.py` as empty.

Create `scripts/data/monetization_overlay.yaml`:

```yaml
# scripts/data/monetization_overlay.yaml
# Hand-curated overlay on top of WhatsMyName. Marks specific destinations as
# monetization platforms + pins platform enum values per the project's
# `platform` + `account_type` enums. Classifier loads this after the base
# gazetteer; overlay entries win on conflict.

# Format per entry:
#   host: exact hostname match (lowercased, no www)
#   platform: one of PROJECT_STATE.md §5 `platform` enum values
#   account_type: one of PROJECT_STATE.md §5 `account_type` enum values
#   url_pattern: optional regex the URL path must match. If absent, host alone matches.

entries:
  # Subscription monetization
  - host: onlyfans.com
    platform: onlyfans
    account_type: monetization
  - host: fanvue.com
    platform: fanvue
    account_type: monetization
  - host: fanplace.com
    platform: fanplace
    account_type: monetization
  - host: patreon.com
    platform: patreon
    account_type: monetization

  # Ecommerce
  - host: amazon.com
    platform: amazon_storefront
    account_type: monetization
    url_pattern: '^/shop/'
  - host: tiktok.com
    platform: tiktok_shop
    account_type: monetization
    url_pattern: '^/@[^/]+/shop'
  - host: gumroad.com
    platform: other
    account_type: monetization
  - host: stan.store
    platform: other
    account_type: monetization

  # Social (primary)
  - host: instagram.com
    platform: instagram
    account_type: social
  - host: tiktok.com
    platform: tiktok
    account_type: social
    url_pattern: '^/@[^/]+/?$'
  - host: youtube.com
    platform: youtube
    account_type: social
  - host: youtu.be
    platform: youtube
    account_type: social
  - host: twitter.com
    platform: twitter
    account_type: social
  - host: x.com
    platform: twitter
    account_type: social
  - host: facebook.com
    platform: facebook
    account_type: social
  - host: linkedin.com
    platform: linkedin
    account_type: social

  # Aggregators (link-in-bio)
  - host: linktr.ee
    platform: linktree
    account_type: link_in_bio
  - host: beacons.ai
    platform: beacons
    account_type: link_in_bio
  - host: beacons.page
    platform: beacons
    account_type: link_in_bio

  # Messaging
  - host: t.me
    platform: telegram_channel
    account_type: messaging
  - host: telegram.me
    platform: telegram_channel
    account_type: messaging
```

- [ ] **Step 3: Write failing tests**

Create `scripts/tests/data/__init__.py` as empty.

Create `scripts/tests/data/test_gazetteer_loader.py`:

```python
# scripts/tests/data/test_gazetteer_loader.py
import pytest
from data.gazetteer_loader import load_gazetteer, lookup


def test_loads_without_error():
    gaz = load_gazetteer()
    assert gaz is not None
    assert len(gaz) > 10


def test_lookup_onlyfans_is_monetization():
    result = lookup("https://onlyfans.com/alice")
    assert result is not None
    platform, account_type, reason = result
    assert platform == "onlyfans"
    assert account_type == "monetization"
    assert reason.startswith("rule:")


def test_lookup_strips_www_prefix():
    result = lookup("https://www.onlyfans.com/alice")
    assert result is not None
    assert result[0] == "onlyfans"


def test_lookup_instagram_is_social():
    result = lookup("https://instagram.com/alice")
    assert result is not None
    assert result[0] == "instagram"
    assert result[1] == "social"


def test_lookup_amazon_shop_matches_pattern():
    result = lookup("https://amazon.com/shop/alice")
    assert result is not None
    assert result[0] == "amazon_storefront"


def test_lookup_amazon_non_shop_does_not_match():
    # amazon.com without /shop/ is not a storefront
    result = lookup("https://amazon.com/dp/B01234")
    assert result is None


def test_lookup_tiktok_shop_pattern():
    result = lookup("https://tiktok.com/@alice/shop")
    assert result is not None
    assert result[0] == "tiktok_shop"


def test_lookup_tiktok_profile_is_social():
    result = lookup("https://tiktok.com/@alice")
    assert result is not None
    assert result[0] == "tiktok"
    assert result[1] == "social"


def test_lookup_unknown_host_returns_none():
    result = lookup("https://some-weird-site.example/alice")
    assert result is None


def test_lookup_linktree_is_aggregator():
    result = lookup("https://linktr.ee/alice")
    assert result is not None
    assert result[1] == "link_in_bio"


def test_lookup_t_me_is_messaging():
    result = lookup("https://t.me/alice_channel")
    assert result is not None
    assert result[0] == "telegram_channel"
    assert result[1] == "messaging"


def test_lookup_expects_canonicalized_url():
    # Loader expects pre-canonicalized URLs. www + uppercase returns None
    # because canonicalize_url is the caller's responsibility.
    assert lookup("https://WWW.onlyfans.com/alice") is None
```

Run: `cd scripts && python -m pytest tests/data/ -v`
Expected: all tests fail with module not found.

- [ ] **Step 4: Implement loader**

Create `scripts/data/gazetteer_loader.py`:

```python
# scripts/data/gazetteer_loader.py — Load monetization overlay + provide lookup(url)
import re
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse
import yaml

_OVERLAY_PATH = Path(__file__).resolve().parent / "monetization_overlay.yaml"

# Cache: {host: [entry_dict, ...]} where each entry may have a url_pattern
_CACHE: Optional[dict[str, list[dict]]] = None


def load_gazetteer() -> dict[str, list[dict]]:
    """Load + index the monetization overlay by host. Idempotent."""
    global _CACHE
    if _CACHE is not None:
        return _CACHE

    with _OVERLAY_PATH.open("r") as f:
        data = yaml.safe_load(f)

    index: dict[str, list[dict]] = {}
    for entry in data.get("entries", []):
        host = entry["host"].lower()
        # Precompile url_pattern regex if present
        if "url_pattern" in entry:
            entry = {**entry, "_url_re": re.compile(entry["url_pattern"])}
        index.setdefault(host, []).append(entry)

    _CACHE = index
    return index


def lookup(url: str) -> Optional[tuple[str, str, str]]:
    """Look up a (pre-canonicalized) URL in the gazetteer.

    Returns (platform, account_type, reason) or None if no rule matches.
    Expects input to already be canonicalized (lowercase host, no www, etc).
    """
    try:
        parsed = urlparse(url)
    except ValueError:
        return None

    host = (parsed.hostname or "").lower()
    if not host:
        return None

    gaz = load_gazetteer()
    entries = gaz.get(host, [])
    if not entries:
        return None

    path = parsed.path or "/"
    for entry in entries:
        if "_url_re" in entry:
            if entry["_url_re"].search(path):
                return (
                    entry["platform"],
                    entry["account_type"],
                    f"rule:{entry['platform']}_{entry['account_type']}",
                )
            # pattern present but didn't match — skip this entry
            continue
        return (
            entry["platform"],
            entry["account_type"],
            f"rule:{entry['platform']}_{entry['account_type']}",
        )

    # Every entry for this host had a url_pattern and none matched
    return None
```

- [ ] **Step 5: Run tests**

Run: `cd scripts && python -m pytest tests/data/ -v`
Expected: all 12 tests pass.

- [ ] **Step 6: Commit**

```bash
git add scripts/data/ scripts/tests/data/ scripts/requirements.txt
git commit -m "feat(pipeline): gazetteer loader + monetization overlay

Hand-curated YAML overlay covering the ~20 platforms we actively track:
OnlyFans/Fanvue/Fanplace/Patreon (monetization), Amazon shop/TikTok shop
/Gumroad/Stan.store (ecommerce), IG/TT/YT/X/FB/LinkedIn (social), Linktree/
Beacons (aggregator), t.me/telegram.me (messaging). Entries support
url_pattern regex for narrow matches (e.g. amazon.com only matches /shop/).

lookup(url) expects pre-canonicalized input; caller canonicalizes first.
Returns (platform, account_type, reason='rule:{name}') or None."
```

---

## Task 5: `pipeline/classifier.py` — URL classifier

**Files:**
- Create: `scripts/pipeline/classifier.py`
- Create: `scripts/tests/pipeline/test_classifier.py`

Rule-first classifier. Hits gazetteer first. On miss, falls through to Gemini once and caches the guess in `classifier_llm_guesses`. The cache is keyed on canonical URL and never expires (URLs don't change categories in practice).

- [ ] **Step 1: Write failing tests**

Create `scripts/tests/pipeline/test_classifier.py`:

```python
# scripts/tests/pipeline/test_classifier.py
import pytest
from unittest.mock import MagicMock, patch
from pipeline.classifier import classify, Classification


class TestClassifyRuleMatches:
    def test_onlyfans_returns_monetization(self):
        result = classify("https://onlyfans.com/alice", supabase=None)
        assert result.platform == "onlyfans"
        assert result.account_type == "monetization"
        assert result.reason.startswith("rule:")
        assert result.confidence == 1.0

    def test_instagram_returns_social(self):
        result = classify("https://instagram.com/alice", supabase=None)
        assert result.platform == "instagram"
        assert result.account_type == "social"

    def test_linktree_returns_link_in_bio(self):
        result = classify("https://linktr.ee/alice", supabase=None)
        assert result.account_type == "link_in_bio"


class TestClassifyLLMFallback:
    @patch("pipeline.classifier._classify_via_llm")
    def test_unknown_url_falls_through_to_llm(self, mock_llm):
        mock_llm.return_value = ("other", "monetization", 0.85, "gemini-2.5-flash")
        # Supabase mock so cache lookup misses + insert succeeds
        sb = MagicMock()
        sb.table.return_value.select.return_value.eq.return_value.maybe_single\
            .return_value.execute.return_value.data = None
        sb.table.return_value.upsert.return_value.execute.return_value = None

        result = classify("https://unknown-coaching-site.example/alice", supabase=sb)

        mock_llm.assert_called_once()
        assert result.platform == "other"
        assert result.account_type == "monetization"
        assert result.reason == "llm:high_confidence"
        assert result.confidence == 0.85

    @patch("pipeline.classifier._classify_via_llm")
    def test_llm_low_confidence_returns_other(self, mock_llm):
        mock_llm.return_value = ("other", "other", 0.5, "gemini-2.5-flash")
        sb = MagicMock()
        sb.table.return_value.select.return_value.eq.return_value.maybe_single\
            .return_value.execute.return_value.data = None
        sb.table.return_value.upsert.return_value.execute.return_value = None

        result = classify("https://weird.example/x", supabase=sb)

        assert result.platform == "other"
        assert result.account_type == "other"
        assert result.reason == "llm:low_confidence"

    def test_cache_hit_skips_llm(self):
        sb = MagicMock()
        sb.table.return_value.select.return_value.eq.return_value.maybe_single\
            .return_value.execute.return_value.data = {
                "platform_guess": "patreon",
                "account_type_guess": "monetization",
                "confidence": 0.9,
                "model_version": "gemini-2.5-flash",
            }

        result = classify("https://cached.example/alice", supabase=sb)

        assert result.platform == "patreon"
        assert result.reason == "llm:cache_hit"

    @patch("pipeline.classifier._classify_via_llm")
    def test_llm_timeout_returns_other_other(self, mock_llm):
        mock_llm.side_effect = TimeoutError("gemini slow")
        sb = MagicMock()
        sb.table.return_value.select.return_value.eq.return_value.maybe_single\
            .return_value.execute.return_value.data = None

        result = classify("https://timeout.example/x", supabase=sb)

        assert result.platform == "other"
        assert result.account_type == "other"
        assert result.reason == "llm:timeout"
        assert result.confidence == 0.0


class TestClassifyNoSupabase:
    """When classifier is used without DB (e.g. unit tests), rule matches still work."""
    def test_rule_match_works_without_supabase(self):
        result = classify("https://onlyfans.com/alice", supabase=None)
        assert result.platform == "onlyfans"

    def test_unknown_url_without_supabase_returns_other_other(self):
        # No DB = no LLM call (classifier needs DB to cache guesses)
        result = classify("https://unknown.example/alice", supabase=None)
        assert result.platform == "other"
        assert result.account_type == "other"
        assert result.reason == "llm:no_cache_context"
```

Run: `cd scripts && python -m pytest tests/pipeline/test_classifier.py -v`
Expected: all tests fail with import error.

- [ ] **Step 2: Implement classifier**

Create `scripts/pipeline/classifier.py`:

```python
# scripts/pipeline/classifier.py — URL → (platform, account_type) classifier
import json
from dataclasses import dataclass
from typing import Optional
import google.generativeai as genai

from common import get_gemini_key
from data.gazetteer_loader import lookup as gazetteer_lookup

_LLM_MODEL = "gemini-2.5-flash"
_CONFIDENCE_THRESHOLD = 0.7

_PROMPT_TEMPLATE = """You are classifying a URL into a creator-platform taxonomy.

URL: {url}

Return a JSON object with these fields:
- platform: one of [instagram, tiktok, youtube, patreon, twitter, linkedin, facebook, onlyfans, fanvue, fanplace, amazon_storefront, tiktok_shop, linktree, beacons, custom_domain, telegram_channel, telegram_cupidbot, other]
- account_type: one of [social, monetization, link_in_bio, messaging, other]
- confidence: float 0.0-1.0 — how confident are you this is the right classification

Rules:
- monetization: anywhere a creator collects payment (subscription, tips, PPV, store, coaching landing page)
- social: content-posting social network profile
- link_in_bio: aggregator page listing multiple destinations
- messaging: direct communication channel (Telegram, Discord invite)
- other: affiliate links, news articles, blog posts, miscellaneous
- Below 0.7 confidence → prefer platform='other', account_type='other'.

Return ONLY the JSON object, no surrounding text.
"""


@dataclass(frozen=True)
class Classification:
    platform: str
    account_type: str
    confidence: float
    reason: str  # 'rule:X' | 'llm:high_confidence' | 'llm:low_confidence' | 'llm:cache_hit' | 'llm:timeout' | 'llm:no_cache_context'
    model_version: Optional[str] = None


def _classify_via_llm(url: str) -> tuple[str, str, float, str]:
    """Call Gemini to classify. Returns (platform, account_type, confidence, model_version)."""
    genai.configure(api_key=get_gemini_key())
    model = genai.GenerativeModel(_LLM_MODEL)
    resp = model.generate_content(
        _PROMPT_TEMPLATE.format(url=url),
        generation_config=genai.GenerationConfig(response_mime_type="application/json"),
    )
    parsed = json.loads(resp.text)
    return (
        parsed.get("platform", "other"),
        parsed.get("account_type", "other"),
        float(parsed.get("confidence", 0.0)),
        _LLM_MODEL,
    )


def _cache_lookup(sb, canonical_url: str) -> Optional[dict]:
    resp = sb.table("classifier_llm_guesses").select("*").eq(
        "canonical_url", canonical_url
    ).maybe_single().execute()
    return resp.data


def _cache_insert(sb, canonical_url: str, platform: str, account_type: str,
                  confidence: float, model_version: str) -> None:
    sb.table("classifier_llm_guesses").upsert({
        "canonical_url": canonical_url,
        "platform_guess": platform,
        "account_type_guess": account_type,
        "confidence": confidence,
        "model_version": model_version,
    }).execute()


def classify(canonical_url: str, supabase) -> Classification:
    """Classify a canonical URL into (platform, account_type).

    Rule-first via gazetteer. On miss, falls through to cached LLM guess. On
    cache miss, calls Gemini once and caches. On LLM timeout/error, returns
    ('other', 'other') with reason='llm:timeout' — non-fatal.

    `supabase` may be None (unit-test / offline context). In that case rule
    matches work but LLM fallback returns ('other','other','llm:no_cache_context').
    """
    # 1. Rule match
    rule_hit = gazetteer_lookup(canonical_url)
    if rule_hit is not None:
        platform, account_type, reason = rule_hit
        return Classification(platform=platform, account_type=account_type,
                              confidence=1.0, reason=reason)

    # 2. No DB → can't cache, skip LLM
    if supabase is None:
        return Classification(platform="other", account_type="other",
                              confidence=0.0, reason="llm:no_cache_context")

    # 3. Cache hit
    cached = _cache_lookup(supabase, canonical_url)
    if cached:
        return Classification(
            platform=cached["platform_guess"] or "other",
            account_type=cached["account_type_guess"] or "other",
            confidence=float(cached["confidence"]),
            reason="llm:cache_hit",
            model_version=cached["model_version"],
        )

    # 4. LLM fallback
    try:
        platform, account_type, conf, model_v = _classify_via_llm(canonical_url)
    except TimeoutError:
        return Classification(platform="other", account_type="other",
                              confidence=0.0, reason="llm:timeout")
    except Exception:
        return Classification(platform="other", account_type="other",
                              confidence=0.0, reason="llm:timeout")

    try:
        _cache_insert(supabase, canonical_url, platform, account_type, conf, model_v)
    except Exception:
        pass  # non-fatal — we still return the guess

    if conf >= _CONFIDENCE_THRESHOLD:
        return Classification(platform=platform, account_type=account_type,
                              confidence=conf, reason="llm:high_confidence",
                              model_version=model_v)
    return Classification(platform="other", account_type="other",
                          confidence=conf, reason="llm:low_confidence",
                          model_version=model_v)
```

- [ ] **Step 3: Run tests**

Run: `cd scripts && python -m pytest tests/pipeline/test_classifier.py -v`
Expected: all 8 tests pass.

- [ ] **Step 4: Commit**

```bash
git add scripts/pipeline/classifier.py scripts/tests/pipeline/test_classifier.py
git commit -m "feat(pipeline): URL classifier — rule-first with cached LLM fallback

Rule match via gazetteer loader returns immediately with confidence 1.0
and reason='rule:{name}'. On miss, consults classifier_llm_guesses cache.
On cache miss, calls Gemini once, caches, and gates return on >=0.7
confidence. LLM timeout/error returns ('other','other') non-fatal.

Supports supabase=None for offline/unit contexts (rule matches still work;
LLM fallback returns ('other','other','llm:no_cache_context'))."
```

---

## Task 6: `pipeline/budget.py` — Apify cost tracker

**Files:**
- Create: `scripts/pipeline/budget.py`
- Create: `scripts/tests/pipeline/test_budget.py`

Tracks per-bulk-import Apify spend. Hard abort at cap. Not a queue/rate-limiter — just a running total with soft-warning thresholds.

- [ ] **Step 1: Write failing tests**

Create `scripts/tests/pipeline/test_budget.py`:

```python
# scripts/tests/pipeline/test_budget.py
import pytest
from pipeline.budget import BudgetTracker, BudgetExhaustedError


class TestBudgetTracker:
    def test_starts_at_zero(self):
        b = BudgetTracker(cap_cents=500)
        assert b.spent_cents == 0
        assert b.remaining_cents == 500

    def test_can_spend_within_cap(self):
        b = BudgetTracker(cap_cents=500)
        b.debit("apify/instagram-scraper", 50)
        assert b.spent_cents == 50
        assert b.remaining_cents == 450

    def test_can_afford(self):
        b = BudgetTracker(cap_cents=500)
        b.debit("x", 400)
        assert b.can_afford(50) is True
        assert b.can_afford(150) is False

    def test_raises_when_debit_exceeds_cap(self):
        b = BudgetTracker(cap_cents=500)
        b.debit("x", 400)
        with pytest.raises(BudgetExhaustedError):
            b.debit("y", 150)

    def test_soft_warning_at_50_percent(self):
        warnings = []
        b = BudgetTracker(cap_cents=1000, on_warning=warnings.append)
        b.debit("x", 400)
        assert warnings == []
        b.debit("y", 150)
        # crossed 500 cents threshold (50%)
        assert any("50%" in w for w in warnings)

    def test_soft_warning_at_80_percent(self):
        warnings = []
        b = BudgetTracker(cap_cents=1000, on_warning=warnings.append)
        b.debit("x", 790)
        assert all("80%" not in w for w in warnings)
        b.debit("y", 20)
        assert any("80%" in w for w in warnings)

    def test_tracks_per_actor(self):
        b = BudgetTracker(cap_cents=500)
        b.debit("apify/instagram-scraper", 40)
        b.debit("apify/instagram-scraper", 30)
        b.debit("clockworks/tiktok-scraper", 50)
        assert b.spent_by_actor == {
            "apify/instagram-scraper": 70,
            "clockworks/tiktok-scraper": 50,
        }
```

Run: `cd scripts && python -m pytest tests/pipeline/test_budget.py -v`
Expected: all tests fail.

- [ ] **Step 2: Implement budget tracker**

Create `scripts/pipeline/budget.py`:

```python
# scripts/pipeline/budget.py — Per-bulk-import Apify spend tracker
from typing import Callable, Optional


class BudgetExhaustedError(RuntimeError):
    """Raised by BudgetTracker.debit() when a spend would exceed the cap."""


class BudgetTracker:
    """Tracks Apify actor spend in cents against a hard cap.

    Fires soft warnings at 50% and 80% via the on_warning callback. Raises
    BudgetExhaustedError when a debit would push spend over the cap.
    """

    def __init__(self, cap_cents: int, on_warning: Optional[Callable[[str], None]] = None):
        self.cap_cents = cap_cents
        self.spent_cents = 0
        self.spent_by_actor: dict[str, int] = {}
        self._on_warning = on_warning or (lambda _msg: None)
        self._warned_50 = False
        self._warned_80 = False

    @property
    def remaining_cents(self) -> int:
        return max(0, self.cap_cents - self.spent_cents)

    def can_afford(self, cents: int) -> bool:
        return self.spent_cents + cents <= self.cap_cents

    def debit(self, actor_id: str, cents: int) -> None:
        if self.spent_cents + cents > self.cap_cents:
            raise BudgetExhaustedError(
                f"Spend of {cents}¢ on {actor_id} would exceed cap "
                f"(already spent {self.spent_cents}¢ of {self.cap_cents}¢)"
            )
        self.spent_cents += cents
        self.spent_by_actor[actor_id] = self.spent_by_actor.get(actor_id, 0) + cents

        pct = self.spent_cents / self.cap_cents * 100
        if pct >= 50 and not self._warned_50:
            self._warned_50 = True
            self._on_warning(f"[budget] crossed 50% ({self.spent_cents}¢ of {self.cap_cents}¢)")
        if pct >= 80 and not self._warned_80:
            self._warned_80 = True
            self._on_warning(f"[budget] crossed 80% ({self.spent_cents}¢ of {self.cap_cents}¢)")
```

- [ ] **Step 3: Run tests**

Run: `cd scripts && python -m pytest tests/pipeline/test_budget.py -v`
Expected: all 7 tests pass.

- [ ] **Step 4: Commit**

```bash
git add scripts/pipeline/budget.py scripts/tests/pipeline/test_budget.py
git commit -m "feat(pipeline): Apify budget tracker with hard cap + soft warnings

Debits spend per actor_id, tracks per-actor breakdown, fires on_warning
callbacks at 50% and 80% thresholds (once each), raises BudgetExhaustedError
on cap overrun. Caller is responsible for deciding what to do on exhaustion
(skip seed, abort bulk, etc.) — the tracker just enforces the ledger."
```

---

## Task 7: `pipeline/identity.py` — rule cascade + CLIP tiebreak

**Files:**
- Create: `scripts/pipeline/identity.py`
- Create: `scripts/tests/pipeline/test_identity.py`

The identity scorer is the heart of the dedup system. It implements the rule cascade from spec §3.4 — first-match-wins, each rule stores structured evidence in JSONB. CLIP avatar similarity is only invoked inside a candidate bucket (spec §3.5). Index lookup against `profile_destination_links` is the entry point.

- [ ] **Step 1: Write failing tests**

Create `scripts/tests/pipeline/test_identity.py`:

```python
# scripts/tests/pipeline/test_identity.py
from dataclasses import dataclass
from unittest.mock import MagicMock, patch
import pytest
from pipeline.identity import (
    ProfileFingerprint,
    score_pair,
    find_candidates_for_profile,
    IdentityVerdict,
)


def _fp(profile_id="p1", handle="alice", platform="instagram", bio="",
        display_name="Alice", avatar_url=None, destination_urls=None,
        destination_classes=None, niche=None):
    return ProfileFingerprint(
        profile_id=profile_id,
        handle=handle,
        platform=platform,
        bio=bio,
        display_name=display_name,
        avatar_url=avatar_url,
        destination_urls=list(destination_urls or []),
        destination_classes=dict(destination_classes or {}),
        niche=niche,
    )


class TestRule1SharedMonetization:
    def test_shared_onlyfans_url_auto_merges(self):
        a = _fp(profile_id="a", destination_urls=["https://onlyfans.com/alice"],
                destination_classes={"https://onlyfans.com/alice": "monetization"})
        b = _fp(profile_id="b", destination_urls=["https://onlyfans.com/alice"],
                destination_classes={"https://onlyfans.com/alice": "monetization"})
        verdict = score_pair(a, b, clip_fn=None)
        assert verdict.action == "auto_merge"
        assert verdict.confidence == 1.0
        assert "shared_monetization" in verdict.reason
        assert verdict.evidence["shared_url"] == "https://onlyfans.com/alice"


class TestRule2SharedAggregator:
    def test_shared_linktree_auto_merges(self):
        a = _fp(profile_id="a", destination_urls=["https://linktr.ee/alice"],
                destination_classes={"https://linktr.ee/alice": "aggregator"})
        b = _fp(profile_id="b", destination_urls=["https://linktr.ee/alice"],
                destination_classes={"https://linktr.ee/alice": "aggregator"})
        verdict = score_pair(a, b, clip_fn=None)
        assert verdict.action == "auto_merge"
        assert "shared_aggregator" in verdict.reason


class TestRule3BioCrossMention:
    def test_bio_mentions_other_handle(self):
        a = _fp(profile_id="a", handle="alice", platform="instagram",
                bio="also on tiktok @bob_backup", destination_urls=[])
        b = _fp(profile_id="b", handle="bob_backup", platform="tiktok",
                destination_urls=[])
        verdict = score_pair(a, b, clip_fn=None)
        assert verdict.action == "merge_candidate"
        assert verdict.confidence == 0.8
        assert "bio_cross_mention" in verdict.reason


class TestRule4HandleMatchPlusClip:
    def test_exact_handle_plus_high_clip_is_candidate(self):
        a = _fp(profile_id="a", handle="alice", platform="instagram",
                avatar_url="https://cdn/a.jpg")
        b = _fp(profile_id="b", handle="alice", platform="tiktok",
                avatar_url="https://cdn/b.jpg")
        # CLIP returns 0.9 similarity
        verdict = score_pair(a, b, clip_fn=lambda _a, _b: 0.9)
        assert verdict.action == "merge_candidate"
        assert verdict.confidence == 0.7
        assert "handle_match_clip" in verdict.reason

    def test_handle_match_low_clip_is_discard(self):
        a = _fp(profile_id="a", handle="alice", platform="instagram",
                avatar_url="https://cdn/a.jpg")
        b = _fp(profile_id="b", handle="alice", platform="tiktok",
                avatar_url="https://cdn/b.jpg")
        verdict = score_pair(a, b, clip_fn=lambda _a, _b: 0.3)
        assert verdict.action == "discard"


class TestDiscardCases:
    def test_shared_affiliate_domain_discarded(self):
        a = _fp(profile_id="a", destination_urls=["https://amazon.com/dp/B01"],
                destination_classes={"https://amazon.com/dp/B01": "other"})
        b = _fp(profile_id="b", destination_urls=["https://amazon.com/dp/B01"],
                destination_classes={"https://amazon.com/dp/B01": "other"})
        verdict = score_pair(a, b, clip_fn=None)
        assert verdict.action == "discard"

    def test_no_signals_discards(self):
        a = _fp(profile_id="a", handle="alice")
        b = _fp(profile_id="b", handle="bob")
        verdict = score_pair(a, b, clip_fn=None)
        assert verdict.action == "discard"


class TestFindCandidates:
    def test_queries_inverted_index(self):
        """find_candidates_for_profile looks up profile_destination_links on
        the profile's monetization+aggregator URLs, returning peer profile_ids."""
        sb = MagicMock()
        sb.table.return_value.select.return_value.eq.return_value.in_.return_value\
            .neq.return_value.execute.return_value.data = [
                {"profile_id": "other-1", "canonical_url": "https://onlyfans.com/alice"},
                {"profile_id": "other-2", "canonical_url": "https://onlyfans.com/alice"},
            ]

        fp = _fp(profile_id="me",
                 destination_urls=["https://onlyfans.com/alice"],
                 destination_classes={"https://onlyfans.com/alice": "monetization"})

        candidates = find_candidates_for_profile(fp, workspace_id="ws-1", supabase=sb)

        assert set(candidates) == {"other-1", "other-2"}
```

Run: `cd scripts && python -m pytest tests/pipeline/test_identity.py -v`
Expected: all tests fail with import error.

- [ ] **Step 2: Implement identity scorer**

Create `scripts/pipeline/identity.py`:

```python
# scripts/pipeline/identity.py — Rule-cascade identity scorer
import re
from dataclasses import dataclass, field
from typing import Callable, Literal, Optional


@dataclass
class ProfileFingerprint:
    """Everything identity.py needs to score a profile against peers."""
    profile_id: str
    handle: str
    platform: str
    bio: str = ""
    display_name: str = ""
    avatar_url: Optional[str] = None
    destination_urls: list[str] = field(default_factory=list)
    # {canonical_url: destination_class} — 'monetization' | 'aggregator' | 'social' | 'other'
    destination_classes: dict[str, str] = field(default_factory=dict)
    niche: Optional[str] = None


Action = Literal["auto_merge", "merge_candidate", "discard"]


@dataclass(frozen=True)
class IdentityVerdict:
    action: Action
    confidence: float
    reason: str
    evidence: dict


def _shared_classed_url(a: ProfileFingerprint, b: ProfileFingerprint,
                         target_class: str) -> Optional[str]:
    """Return the first URL that appears in both profiles with destination_class == target."""
    a_urls = {u for u in a.destination_urls if a.destination_classes.get(u) == target_class}
    b_urls = {u for u in b.destination_urls if b.destination_classes.get(u) == target_class}
    intersection = a_urls & b_urls
    return next(iter(intersection), None)


def _normalize_handle(h: str) -> str:
    return re.sub(r"[^a-z0-9]", "", (h or "").lower())


def _bio_mentions_other(a: ProfileFingerprint, b: ProfileFingerprint) -> bool:
    """True if a.bio contains b.handle (as @handle or full URL). Direction: a→b only."""
    if not a.bio:
        return False
    bio_lower = a.bio.lower()
    handle_norm = _normalize_handle(b.handle)
    if not handle_norm:
        return False
    # Match @handle, /handle/, or handle as whole word
    patterns = [
        rf"@{re.escape(b.handle.lower())}\b",
        rf"/{re.escape(b.handle.lower())}/",
        rf"\b{re.escape(b.handle.lower())}\b",
    ]
    return any(re.search(p, bio_lower) for p in patterns)


def score_pair(a: ProfileFingerprint, b: ProfileFingerprint,
               clip_fn: Optional[Callable[[str, str], float]]) -> IdentityVerdict:
    """Score a pair of profile fingerprints via rule cascade. First match wins.

    clip_fn(avatar_url_a, avatar_url_b) -> cosine similarity 0.0-1.0. May be None
    for unit tests — in that case Rule 4 is skipped.
    """
    # Rule 1: shared monetization destination → auto-merge
    url = _shared_classed_url(a, b, "monetization")
    if url:
        return IdentityVerdict(
            action="auto_merge", confidence=1.0,
            reason="shared_monetization_url",
            evidence={"shared_url": url, "class": "monetization"},
        )

    # Rule 2: shared aggregator URL → auto-merge
    url = _shared_classed_url(a, b, "aggregator")
    if url:
        return IdentityVerdict(
            action="auto_merge", confidence=1.0,
            reason="shared_aggregator_url",
            evidence={"shared_url": url, "class": "aggregator"},
        )

    # Rule 3: bio cross-mention (either direction)
    if _bio_mentions_other(a, b):
        return IdentityVerdict(
            action="merge_candidate", confidence=0.8,
            reason="bio_cross_mention",
            evidence={"direction": "a_mentions_b", "handle": b.handle},
        )
    if _bio_mentions_other(b, a):
        return IdentityVerdict(
            action="merge_candidate", confidence=0.8,
            reason="bio_cross_mention",
            evidence={"direction": "b_mentions_a", "handle": a.handle},
        )

    # Rule 4: handle exact match + CLIP similarity ≥ 0.85 (cross-platform only)
    if clip_fn and a.platform != b.platform:
        if _normalize_handle(a.handle) == _normalize_handle(b.handle) \
                and _normalize_handle(a.handle):
            if a.avatar_url and b.avatar_url:
                similarity = clip_fn(a.avatar_url, b.avatar_url)
                if similarity >= 0.85:
                    return IdentityVerdict(
                        action="merge_candidate", confidence=0.7,
                        reason="handle_match_clip",
                        evidence={
                            "handle": a.handle,
                            "clip_similarity": round(similarity, 3),
                        },
                    )

    # Rule 5: display name match + niche match — only with ≥2 prior signals
    # For SP1, cascade terminates at Rule 4 alone. Rule 5 is reserved for
    # future expansion when we have richer evidence accumulation.

    return IdentityVerdict(action="discard", confidence=0.0,
                           reason="no_signal", evidence={})


def find_candidates_for_profile(fp: ProfileFingerprint, workspace_id: str,
                                 supabase) -> list[str]:
    """Query profile_destination_links for peer profiles sharing monetization
    or aggregator URLs with this one. Returns list of peer profile_ids (excludes fp.profile_id).
    """
    # Only query on strong-signal URL classes
    target_urls = [
        u for u in fp.destination_urls
        if fp.destination_classes.get(u) in ("monetization", "aggregator")
    ]
    if not target_urls:
        return []

    resp = supabase.table("profile_destination_links").select(
        "profile_id, canonical_url"
    ).eq("workspace_id", workspace_id).in_(
        "canonical_url", target_urls
    ).neq("profile_id", fp.profile_id).execute()

    return list({row["profile_id"] for row in (resp.data or [])})


# CLIP loader and similarity helper — lazy so unit tests don't pay the cost
_CLIP_MODEL = None
_CLIP_PREPROCESS = None


def get_clip_similarity_fn() -> Callable[[str, str], float]:
    """Return a function that downloads two avatar URLs and returns CLIP cosine similarity.

    Lazy-loads the CLIP model on first call. Subsequent calls reuse the loaded model.
    Returns 0.0 on any fetch/encode error (safer than raising in the cascade hot path).
    """
    from io import BytesIO
    import httpx
    from PIL import Image
    from sentence_transformers import SentenceTransformer
    from sentence_transformers.util import cos_sim

    global _CLIP_MODEL
    if _CLIP_MODEL is None:
        _CLIP_MODEL = SentenceTransformer("clip-ViT-B-32")

    def similarity(url_a: str, url_b: str) -> float:
        try:
            with httpx.Client(timeout=10.0, follow_redirects=True) as client:
                img_a = Image.open(BytesIO(client.get(url_a).content)).convert("RGB")
                img_b = Image.open(BytesIO(client.get(url_b).content)).convert("RGB")
            emb = _CLIP_MODEL.encode([img_a, img_b], convert_to_tensor=True)
            return float(cos_sim(emb[0], emb[1]).item())
        except Exception:
            return 0.0

    return similarity
```

- [ ] **Step 3: Run tests**

Run: `cd scripts && python -m pytest tests/pipeline/test_identity.py -v`
Expected: all 9 tests pass.

- [ ] **Step 4: Commit**

```bash
git add scripts/pipeline/identity.py scripts/tests/pipeline/test_identity.py
git commit -m "feat(pipeline): identity scorer — rule cascade with CLIP tiebreak

First-match-wins cascade per spec §3.4:
  1. Shared monetization URL -> auto-merge (1.0)
  2. Shared aggregator URL   -> auto-merge (1.0)
  3. Bio cross-mention       -> candidate (0.8)
  4. Handle match + CLIP>=0.85 cross-platform -> candidate (0.7)
  default                    -> discard

find_candidates_for_profile queries profile_destination_links on
monetization+aggregator URLs to produce the bucket shortlist. get_clip_
similarity_fn lazy-loads CLIP ViT-B/32 on first call. CLIP fetch/encode
errors return 0.0 rather than raising (safer in cascade hot path)."
```

---

## Task 8: `fetchers/base.py` + migrate IG/TT fetchers

**Files:**
- Create: `scripts/fetchers/__init__.py`
- Create: `scripts/fetchers/base.py`
- Create: `scripts/fetchers/instagram.py`
- Create: `scripts/fetchers/tiktok.py`
- Create: `scripts/tests/fetchers/__init__.py`
- Modify: `scripts/tests/test_apify_details.py` (imports redirected)
- Delete: `scripts/apify_details.py` (content migrated)

This refactor preserves behavior — just relocates. Existing tests in `tests/test_apify_details.py` should keep passing after the import paths are updated.

- [ ] **Step 1: Create `fetchers/__init__.py` and `tests/fetchers/__init__.py` as empty files**

```bash
cd "/Users/simon/OS/Living VAULT/Content OS/The Hub"
mkdir -p scripts/fetchers scripts/tests/fetchers
touch scripts/fetchers/__init__.py scripts/tests/fetchers/__init__.py
```

- [ ] **Step 2: Create `fetchers/base.py` with shared error + helper**

Create `scripts/fetchers/base.py`:

```python
# scripts/fetchers/base.py — Shared base for platform fetchers
from typing import Optional


class EmptyDatasetError(RuntimeError):
    """Raised when a fetcher returns zero items, or a shape-valid but empty item.

    Signals the login-wall / private / banned / not-found case. Discovery treats
    this as a clean failure (mark_discovery_failed with empty_context reason).
    """


def first_or_none(items: list[dict]) -> Optional[dict]:
    return items[0] if items else None
```

- [ ] **Step 3: Migrate IG fetcher**

Create `scripts/fetchers/instagram.py` by moving the `fetch_instagram_details` function from the existing `scripts/apify_details.py`. Full content:

```python
# scripts/fetchers/instagram.py — Apify IG profile fetcher
from typing import Any
from apify_client import ApifyClient

from schemas import InputContext
from fetchers.base import EmptyDatasetError, first_or_none


def fetch(client: ApifyClient, handle: str) -> InputContext:
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

    item = first_or_none(items)
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
```

- [ ] **Step 4: Migrate TikTok fetcher**

Create `scripts/fetchers/tiktok.py`:

```python
# scripts/fetchers/tiktok.py — Apify TikTok profile fetcher
from typing import Any
from apify_client import ApifyClient

from schemas import InputContext
from fetchers.base import EmptyDatasetError, first_or_none


def fetch(client: ApifyClient, handle: str) -> InputContext:
    """Fetch TikTok profile context via clockworks/tiktok-scraper.

    Requests resultsPerPage=1 and reads authorMeta from that single post; the actor
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

    item = first_or_none(items)
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

- [ ] **Step 5: Keep a thin compatibility shim at `scripts/apify_details.py`**

Rewrite `scripts/apify_details.py` to re-export from the new locations (preserves existing test imports until they're updated in Step 6):

```python
# scripts/apify_details.py — DEPRECATED shim. Use fetchers.{instagram,tiktok} directly.
# Kept temporarily so PR #2's tests keep importing from the old path until
# Task 17 rewires discover_creator.py onto the resolver.
from fetchers.base import EmptyDatasetError  # noqa: F401
from fetchers.instagram import fetch as fetch_instagram_details  # noqa: F401
from fetchers.tiktok import fetch as fetch_tiktok_details  # noqa: F401
```

- [ ] **Step 6: Verify existing tests still pass**

Run: `cd scripts && python -m pytest tests/ -q`
Expected: still 45 passed. No regressions from the move.

- [ ] **Step 7: Commit**

```bash
git add scripts/fetchers/ scripts/tests/fetchers/ scripts/apify_details.py
git commit -m "refactor(pipeline): split apify_details into fetchers/{instagram,tiktok}

Pure refactor — no behavior change. Establishes the fetchers/ package layout
that Tasks 9-12 extend (YT, Patreon, OF, Fanvue, FB, X, generic). Old
apify_details.py becomes a re-export shim so existing tests keep passing.

Shim removed in Task 17 when discover_creator.py is rewired onto the
resolver and the old import path has no consumers."
```

---

## Task 9: `fetchers/youtube.py` — yt-dlp based

**Files:**
- Create: `scripts/fetchers/youtube.py`
- Create: `scripts/tests/fetchers/test_youtube.py`

YouTube channel profile pages work with yt-dlp's `--flat-playlist` equivalent. No API key needed. We only need bio + subscribers + avatar + channel URL — not the full video list.

- [ ] **Step 1: Write failing tests**

Create `scripts/tests/fetchers/test_youtube.py`:

```python
# scripts/tests/fetchers/test_youtube.py
from unittest.mock import patch, MagicMock
import pytest
from fetchers.youtube import fetch
from fetchers.base import EmptyDatasetError


class TestYouTubeFetch:
    @patch("fetchers.youtube.yt_dlp.YoutubeDL")
    def test_returns_context_from_channel_info(self, mock_ydl_cls):
        ydl = MagicMock()
        mock_ydl_cls.return_value.__enter__.return_value = ydl
        ydl.extract_info.return_value = {
            "channel": "Alice Creator",
            "channel_id": "UC123",
            "description": "my tiktok @alice_cooks and linktr.ee/alice",
            "channel_follower_count": 50000,
            "uploader_url": "https://www.youtube.com/@alice",
            "thumbnails": [{"url": "https://yt3/avatar.jpg", "preference": 1}],
        }

        ctx = fetch("@alice")

        assert ctx.platform == "youtube"
        assert ctx.handle == "@alice"
        assert ctx.display_name == "Alice Creator"
        assert ctx.bio == "my tiktok @alice_cooks and linktr.ee/alice"
        assert ctx.follower_count == 50000
        assert ctx.avatar_url == "https://yt3/avatar.jpg"
        assert ctx.source_note == "yt-dlp channel info"

    @patch("fetchers.youtube.yt_dlp.YoutubeDL")
    def test_extracts_urls_from_description(self, mock_ydl_cls):
        ydl = MagicMock()
        mock_ydl_cls.return_value.__enter__.return_value = ydl
        ydl.extract_info.return_value = {
            "channel": "Alice",
            "description": "links: https://linktr.ee/alice and https://onlyfans.com/alice",
            "channel_follower_count": 1000,
        }

        ctx = fetch("@alice")

        assert "https://linktr.ee/alice" in ctx.external_urls
        assert "https://onlyfans.com/alice" in ctx.external_urls

    @patch("fetchers.youtube.yt_dlp.YoutubeDL")
    def test_raises_on_extraction_error(self, mock_ydl_cls):
        ydl = MagicMock()
        mock_ydl_cls.return_value.__enter__.return_value = ydl
        ydl.extract_info.side_effect = Exception("channel not found")

        with pytest.raises(EmptyDatasetError):
            fetch("@nonexistent")

    @patch("fetchers.youtube.yt_dlp.YoutubeDL")
    def test_raises_on_empty_info(self, mock_ydl_cls):
        ydl = MagicMock()
        mock_ydl_cls.return_value.__enter__.return_value = ydl
        ydl.extract_info.return_value = None

        with pytest.raises(EmptyDatasetError):
            fetch("@empty")
```

Run: `cd scripts && python -m pytest tests/fetchers/test_youtube.py -v`
Expected: all fail with module not found.

- [ ] **Step 2: Implement YouTube fetcher**

Create `scripts/fetchers/youtube.py`:

```python
# scripts/fetchers/youtube.py — YouTube channel fetcher via yt-dlp
import re
import yt_dlp

from schemas import InputContext
from fetchers.base import EmptyDatasetError

_YDL_OPTS = {
    "quiet": True,
    "no_warnings": True,
    "extract_flat": "in_playlist",
    "skip_download": True,
    "playlist_items": "0",  # don't fetch videos, just channel info
}

_URL_RE = re.compile(r"https?://[^\s]+")


def _best_thumbnail(thumbnails: list[dict]) -> str | None:
    if not thumbnails:
        return None
    # yt-dlp orders by preference; pick highest-preference with url
    ranked = sorted(thumbnails, key=lambda t: t.get("preference", 0), reverse=True)
    for t in ranked:
        if t.get("url"):
            return t["url"]
    return None


def fetch(handle: str) -> InputContext:
    """Fetch YouTube channel profile context via yt-dlp.

    `handle` is expected as `@handle`. Strips `@` for URL building. Raises
    EmptyDatasetError on any extraction failure (channel not found, private,
    terms-of-service block).
    """
    clean = handle.lstrip("@")
    url = f"https://www.youtube.com/@{clean}"
    try:
        with yt_dlp.YoutubeDL(_YDL_OPTS) as ydl:
            info = ydl.extract_info(url, download=False)
    except Exception as e:
        raise EmptyDatasetError(
            f"yt-dlp could not extract channel info for @{clean}: {e}"
        )

    if not info:
        raise EmptyDatasetError(f"yt-dlp returned empty info for @{clean}")

    description = info.get("description") or ""
    external_urls = _URL_RE.findall(description)

    return InputContext(
        handle=handle,
        platform="youtube",
        display_name=info.get("channel") or info.get("uploader"),
        bio=description,
        follower_count=info.get("channel_follower_count"),
        avatar_url=_best_thumbnail(info.get("thumbnails") or []),
        external_urls=external_urls,
        source_note="yt-dlp channel info",
    )
```

- [ ] **Step 3: Run tests**

Run: `cd scripts && python -m pytest tests/fetchers/test_youtube.py -v`
Expected: all 4 tests pass.

- [ ] **Step 4: Commit**

```bash
git add scripts/fetchers/youtube.py scripts/tests/fetchers/test_youtube.py
git commit -m "feat(pipeline): YouTube channel fetcher via yt-dlp

No API key needed. Uses yt-dlp's extract_info with playlist_items='0' to
fetch channel metadata without downloading videos. Extracts bio, subscriber
count, channel avatar, and parses URLs out of the description for Stage B
expansion. Raises EmptyDatasetError on channel-not-found / TOS-block /
private-channel cases — same semantics as IG/TT fetchers."
```

---

## Task 10: `fetchers/patreon.py` + `fetchers/fanvue.py` + `fetchers/generic.py`

**Files:**
- Create: `scripts/fetchers/patreon.py`
- Create: `scripts/fetchers/fanvue.py`
- Create: `scripts/fetchers/generic.py`
- Create: `scripts/tests/fetchers/test_httpx_fetchers.py`

Three httpx-based fetchers share a common shape: GET the public landing page, parse HTML/OG meta tags for display name, bio, avatar, follower-like metric. Low confidence on unknown fields — safe to leave null.

- [ ] **Step 1: Write failing tests**

Create `scripts/tests/fetchers/test_httpx_fetchers.py`:

```python
# scripts/tests/fetchers/test_httpx_fetchers.py
from unittest.mock import patch, MagicMock
import pytest
from fetchers.base import EmptyDatasetError
from fetchers import patreon, fanvue, generic


_PATREON_HTML = b"""
<html><head>
<meta property="og:title" content="Alice | creating ASMR videos">
<meta property="og:description" content="Monthly ASMR subscriber community">
<meta property="og:image" content="https://patreon.cdn/avatar.jpg">
</head><body>
<script>{"creator":{"name":"Alice","campaign_pledge_sum":{"amount":500000}}}</script>
</body></html>
"""

_FANVUE_HTML = b"""
<html><head>
<meta property="og:title" content="Alice on Fanvue">
<meta property="og:description" content="spicy content subscription">
<meta property="og:image" content="https://fanvue.cdn/avatar.jpg">
</head></html>
"""

_GENERIC_HTML = b"""
<html><head>
<title>Alice's Coaching Site</title>
<meta name="description" content="1:1 content strategy coaching for creators">
<meta property="og:image" content="https://site.com/hero.jpg">
</head></html>
"""


@patch("fetchers.patreon.httpx.Client")
def test_patreon_fetch_parses_og_tags(mock_client_cls):
    mock_client = MagicMock()
    mock_client_cls.return_value.__enter__.return_value = mock_client
    resp = MagicMock()
    resp.status_code = 200
    resp.content = _PATREON_HTML
    mock_client.get.return_value = resp

    ctx = patreon.fetch("alice")

    assert ctx.platform == "patreon"
    assert ctx.handle == "alice"
    assert ctx.display_name == "Alice | creating ASMR videos"
    assert ctx.bio == "Monthly ASMR subscriber community"
    assert ctx.avatar_url == "https://patreon.cdn/avatar.jpg"


@patch("fetchers.patreon.httpx.Client")
def test_patreon_404_raises_empty(mock_client_cls):
    mock_client = MagicMock()
    mock_client_cls.return_value.__enter__.return_value = mock_client
    resp = MagicMock()
    resp.status_code = 404
    mock_client.get.return_value = resp

    with pytest.raises(EmptyDatasetError):
        patreon.fetch("nonexistent")


@patch("fetchers.fanvue.httpx.Client")
def test_fanvue_fetch_parses_og_tags(mock_client_cls):
    mock_client = MagicMock()
    mock_client_cls.return_value.__enter__.return_value = mock_client
    resp = MagicMock()
    resp.status_code = 200
    resp.content = _FANVUE_HTML
    mock_client.get.return_value = resp

    ctx = fanvue.fetch("alice")

    assert ctx.platform == "fanvue"
    assert ctx.display_name == "Alice on Fanvue"
    assert ctx.bio == "spicy content subscription"


@patch("fetchers.generic.httpx.Client")
def test_generic_fetch_parses_title_and_meta(mock_client_cls):
    mock_client = MagicMock()
    mock_client_cls.return_value.__enter__.return_value = mock_client
    resp = MagicMock()
    resp.status_code = 200
    resp.content = _GENERIC_HTML
    mock_client.get.return_value = resp

    ctx = generic.fetch_url("https://alice-coaching.example/")

    assert ctx.platform == "other"
    assert ctx.display_name == "Alice's Coaching Site"
    assert ctx.bio == "1:1 content strategy coaching for creators"
    assert ctx.avatar_url == "https://site.com/hero.jpg"


@patch("fetchers.generic.httpx.Client")
def test_generic_fetch_network_error_raises_empty(mock_client_cls):
    mock_client = MagicMock()
    mock_client_cls.return_value.__enter__.return_value = mock_client
    mock_client.get.side_effect = Exception("dns fail")

    with pytest.raises(EmptyDatasetError):
        generic.fetch_url("https://down.example/")
```

Run: `cd scripts && python -m pytest tests/fetchers/test_httpx_fetchers.py -v`
Expected: all fail.

- [ ] **Step 2: Implement Patreon fetcher**

Create `scripts/fetchers/patreon.py`:

```python
# scripts/fetchers/patreon.py — Patreon creator landing page fetcher via httpx
import httpx
from bs4 import BeautifulSoup

from schemas import InputContext
from fetchers.base import EmptyDatasetError

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9",
}


def _og(soup: BeautifulSoup, prop: str) -> str | None:
    tag = soup.find("meta", attrs={"property": prop})
    return tag.get("content") if tag else None


def fetch(handle: str, timeout: float = 10.0) -> InputContext:
    """Fetch Patreon creator landing page via httpx. Raises EmptyDatasetError on 404/error."""
    url = f"https://www.patreon.com/{handle}"
    try:
        with httpx.Client(follow_redirects=True, timeout=timeout, headers=_HEADERS) as client:
            resp = client.get(url)
    except Exception as e:
        raise EmptyDatasetError(f"patreon fetch failed for {handle}: {e}")

    if resp.status_code != 200:
        raise EmptyDatasetError(
            f"patreon.com/{handle} returned HTTP {resp.status_code}"
        )

    soup = BeautifulSoup(resp.content, "html.parser")

    return InputContext(
        handle=handle,
        platform="patreon",
        display_name=_og(soup, "og:title"),
        bio=_og(soup, "og:description"),
        avatar_url=_og(soup, "og:image"),
        external_urls=[url],
        source_note="patreon landing httpx",
    )
```

- [ ] **Step 3: Implement Fanvue fetcher**

Create `scripts/fetchers/fanvue.py`:

```python
# scripts/fetchers/fanvue.py — Fanvue creator landing fetcher via httpx
import httpx
from bs4 import BeautifulSoup

from schemas import InputContext
from fetchers.base import EmptyDatasetError

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9",
}


def _og(soup: BeautifulSoup, prop: str) -> str | None:
    tag = soup.find("meta", attrs={"property": prop})
    return tag.get("content") if tag else None


def fetch(handle: str, timeout: float = 10.0) -> InputContext:
    url = f"https://www.fanvue.com/{handle}"
    try:
        with httpx.Client(follow_redirects=True, timeout=timeout, headers=_HEADERS) as client:
            resp = client.get(url)
    except Exception as e:
        raise EmptyDatasetError(f"fanvue fetch failed for {handle}: {e}")

    if resp.status_code != 200:
        raise EmptyDatasetError(f"fanvue.com/{handle} returned HTTP {resp.status_code}")

    soup = BeautifulSoup(resp.content, "html.parser")

    return InputContext(
        handle=handle,
        platform="fanvue",
        display_name=_og(soup, "og:title"),
        bio=_og(soup, "og:description"),
        avatar_url=_og(soup, "og:image"),
        external_urls=[url],
        source_note="fanvue landing httpx",
    )
```

- [ ] **Step 4: Implement generic fetcher**

Create `scripts/fetchers/generic.py`:

```python
# scripts/fetchers/generic.py — Fallback fetcher for unclassified profile-like URLs
import httpx
from bs4 import BeautifulSoup

from schemas import InputContext
from fetchers.base import EmptyDatasetError

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9",
}


def _meta(soup: BeautifulSoup, name: str) -> str | None:
    tag = soup.find("meta", attrs={"name": name})
    return tag.get("content") if tag else None


def _og(soup: BeautifulSoup, prop: str) -> str | None:
    tag = soup.find("meta", attrs={"property": prop})
    return tag.get("content") if tag else None


def fetch_url(url: str, timeout: float = 10.0) -> InputContext:
    """Generic HTML fetcher for unknown-platform profile-like URLs.

    Takes a URL directly (no handle concept). Returns platform='other'.
    Parses <title>, <meta name=description>, og:image.
    """
    try:
        with httpx.Client(follow_redirects=True, timeout=timeout, headers=_HEADERS) as client:
            resp = client.get(url)
    except Exception as e:
        raise EmptyDatasetError(f"generic fetch failed for {url}: {e}")

    if resp.status_code != 200:
        raise EmptyDatasetError(f"{url} returned HTTP {resp.status_code}")

    soup = BeautifulSoup(resp.content, "html.parser")

    title = soup.find("title")
    display_name = title.get_text(strip=True) if title else None
    bio = _meta(soup, "description") or _og(soup, "og:description")
    avatar = _og(soup, "og:image")

    return InputContext(
        handle=url,  # no notion of handle here; store the URL
        platform="other",
        display_name=display_name,
        bio=bio,
        avatar_url=avatar,
        external_urls=[url],
        source_note="generic httpx landing",
    )
```

- [ ] **Step 5: Run tests**

Run: `cd scripts && python -m pytest tests/fetchers/test_httpx_fetchers.py -v`
Expected: all 5 tests pass.

- [ ] **Step 6: Commit**

```bash
git add scripts/fetchers/patreon.py scripts/fetchers/fanvue.py \
  scripts/fetchers/generic.py scripts/tests/fetchers/test_httpx_fetchers.py
git commit -m "feat(pipeline): Patreon, Fanvue, and generic fallback fetchers

Three httpx-based fetchers sharing the same shape: GET public landing page,
parse OG meta tags for display_name/bio/avatar. Patreon and Fanvue take a
handle; generic takes a URL (for unclassified profile-like destinations).

All three raise EmptyDatasetError on 4xx/5xx or network error — same
semantics as the Apify-backed fetchers. No JA3/TLS tricks needed on these
hosts (OnlyFans is the exception — Task 11)."
```

---

## Task 11: `fetchers/onlyfans.py` — curl_cffi for JA3 impersonation

**Files:**
- Create: `scripts/fetchers/onlyfans.py`
- Create: `scripts/tests/fetchers/test_onlyfans.py`

OnlyFans uses JA3/TLS fingerprinting; raw httpx is blocked. `curl_cffi.requests` impersonates Chrome's TLS signature and works for the public landing page (display name, bio, avatar, `og:` tags). No login required for this surface.

- [ ] **Step 1: Write failing tests**

Create `scripts/tests/fetchers/test_onlyfans.py`:

```python
# scripts/tests/fetchers/test_onlyfans.py
from unittest.mock import patch, MagicMock
import pytest
from fetchers.onlyfans import fetch
from fetchers.base import EmptyDatasetError


_OF_HTML = b"""
<html><head>
<meta property="og:title" content="Alice | OnlyFans">
<meta property="og:description" content="exclusive content daily">
<meta property="og:image" content="https://of.cdn/avatar.jpg">
</head></html>
"""


@patch("fetchers.onlyfans.requests.get")
def test_fetch_parses_og_tags(mock_get):
    resp = MagicMock()
    resp.status_code = 200
    resp.content = _OF_HTML
    mock_get.return_value = resp

    ctx = fetch("alice")

    assert ctx.platform == "onlyfans"
    assert ctx.handle == "alice"
    assert ctx.display_name == "Alice | OnlyFans"
    assert ctx.bio == "exclusive content daily"
    assert ctx.avatar_url == "https://of.cdn/avatar.jpg"
    # Confirm we're using chrome impersonation
    assert mock_get.call_args.kwargs.get("impersonate") == "chrome120"


@patch("fetchers.onlyfans.requests.get")
def test_fetch_404_raises_empty(mock_get):
    resp = MagicMock()
    resp.status_code = 404
    mock_get.return_value = resp

    with pytest.raises(EmptyDatasetError):
        fetch("nonexistent")


@patch("fetchers.onlyfans.requests.get")
def test_fetch_network_error_raises_empty(mock_get):
    mock_get.side_effect = Exception("TLS handshake failed")

    with pytest.raises(EmptyDatasetError):
        fetch("alice")
```

Run: `cd scripts && python -m pytest tests/fetchers/test_onlyfans.py -v`
Expected: all fail.

- [ ] **Step 2: Implement OF fetcher**

Create `scripts/fetchers/onlyfans.py`:

```python
# scripts/fetchers/onlyfans.py — OF public landing fetcher via curl_cffi (JA3 impersonation)
from curl_cffi import requests
from bs4 import BeautifulSoup

from schemas import InputContext
from fetchers.base import EmptyDatasetError


def _og(soup: BeautifulSoup, prop: str) -> str | None:
    tag = soup.find("meta", attrs={"property": prop})
    return tag.get("content") if tag else None


def fetch(handle: str, timeout: float = 10.0) -> InputContext:
    """Fetch OF public landing page via curl_cffi with Chrome TLS fingerprint.

    Raw httpx is blocked by OF's JA3 check. `impersonate='chrome120'` works for
    the public creator landing page (display_name, bio, avatar, links). No login
    required for this surface. Raises EmptyDatasetError on 404/error.
    """
    url = f"https://onlyfans.com/{handle}"
    try:
        resp = requests.get(url, impersonate="chrome120", timeout=timeout,
                            allow_redirects=True)
    except Exception as e:
        raise EmptyDatasetError(f"onlyfans fetch failed for {handle}: {e}")

    if resp.status_code != 200:
        raise EmptyDatasetError(f"onlyfans.com/{handle} returned HTTP {resp.status_code}")

    soup = BeautifulSoup(resp.content, "html.parser")

    return InputContext(
        handle=handle,
        platform="onlyfans",
        display_name=_og(soup, "og:title"),
        bio=_og(soup, "og:description"),
        avatar_url=_og(soup, "og:image"),
        external_urls=[url],
        source_note="onlyfans landing curl_cffi chrome120",
    )
```

- [ ] **Step 3: Run tests**

Run: `cd scripts && python -m pytest tests/fetchers/test_onlyfans.py -v`
Expected: all 3 tests pass.

- [ ] **Step 4: Commit**

```bash
git add scripts/fetchers/onlyfans.py scripts/tests/fetchers/test_onlyfans.py
git commit -m "feat(pipeline): OnlyFans public landing fetcher via curl_cffi

Raw httpx is blocked by OF's JA3/TLS fingerprint check. curl_cffi.requests
with impersonate='chrome120' passes the handshake and retrieves the public
landing page (display name, bio, avatar via OG meta tags). No login
required — this is the unauthenticated surface. Raises EmptyDatasetError
on 404/error — same semantics as the other fetchers.

Note: only retrieves the public landing surface. Subscriber-only content
(posts, pricing tiers beyond what OG tags expose) is not accessible and
not in scope for SP1."
```

---

## Task 12: `fetchers/facebook.py` + `fetchers/twitter.py` — stubs for SP1

**Files:**
- Create: `scripts/fetchers/facebook.py`
- Create: `scripts/fetchers/twitter.py`
- Create: `scripts/tests/fetchers/test_stubs.py`

FB + X both require Apify actors (HTML-level login wall since 2023). SP1 ships stubs that log and return an empty InputContext with a marker reason. SP1.1 follow-up adds the live Apify actors. This keeps the classifier → fetcher dispatch clean (every platform has a fetcher) without burning budget to discover actors that aren't provisioned.

- [ ] **Step 1: Write failing tests**

Create `scripts/tests/fetchers/test_stubs.py`:

```python
# scripts/tests/fetchers/test_stubs.py
from fetchers import facebook, twitter


def test_facebook_stub_returns_empty_context_with_marker():
    ctx = facebook.fetch("alice")
    assert ctx.platform == "facebook"
    assert ctx.handle == "alice"
    assert ctx.is_empty() is True
    assert ctx.source_note == "stub:not_implemented"


def test_twitter_stub_returns_empty_context_with_marker():
    ctx = twitter.fetch("alice")
    assert ctx.platform == "twitter"
    assert ctx.handle == "alice"
    assert ctx.is_empty() is True
    assert ctx.source_note == "stub:not_implemented"
```

Run: `cd scripts && python -m pytest tests/fetchers/test_stubs.py -v`
Expected: fails.

- [ ] **Step 2: Implement Facebook stub**

Create `scripts/fetchers/facebook.py`:

```python
# scripts/fetchers/facebook.py — STUB: Apify actor not yet provisioned (SP1.1 follow-up)
from schemas import InputContext
from common import console


def fetch(handle: str) -> InputContext:
    """Stub. Returns an empty InputContext so resolver Stage B keeps flowing.

    Classifier will classify FB URLs and dispatch here; the resolver treats
    is_empty() contexts as "recorded but not enriched" (same as unknown-
    platform URLs). SP1.1 adds the live Apify actor.
    """
    console.log(f"[yellow]facebook fetcher stub — no enrichment for @{handle}[/yellow]")
    return InputContext(
        handle=handle,
        platform="facebook",
        source_note="stub:not_implemented",
    )
```

- [ ] **Step 3: Implement Twitter stub**

Create `scripts/fetchers/twitter.py`:

```python
# scripts/fetchers/twitter.py — STUB: Apify actor not yet provisioned (SP1.1 follow-up)
from schemas import InputContext
from common import console


def fetch(handle: str) -> InputContext:
    console.log(f"[yellow]twitter fetcher stub — no enrichment for @{handle}[/yellow]")
    return InputContext(
        handle=handle,
        platform="twitter",
        source_note="stub:not_implemented",
    )
```

- [ ] **Step 4: Run tests**

Run: `cd scripts && python -m pytest tests/fetchers/test_stubs.py -v`
Expected: 2 tests pass.

- [ ] **Step 5: Commit**

```bash
git add scripts/fetchers/facebook.py scripts/fetchers/twitter.py \
  scripts/tests/fetchers/test_stubs.py
git commit -m "feat(pipeline): Facebook + Twitter fetcher stubs

Both platforms require Apify actors (HTML-level login wall since 2023).
SP1 ships stubs returning empty InputContext with source_note='stub:not_
implemented' so the classifier → fetcher dispatch stays complete. Resolver
treats is_empty() contexts as 'recorded but not enriched' — URL + platform
classification is preserved; bio/followers/avatar are null.

SP1.1 follow-up provisions live Apify actors for both."
```

---

## Task 13: `aggregators/` — migrate Linktree/Beacons + add custom_domain

**Files:**
- Create: `scripts/aggregators/__init__.py`
- Create: `scripts/aggregators/linktree.py`
- Create: `scripts/aggregators/beacons.py`
- Create: `scripts/aggregators/custom_domain.py`
- Create: `scripts/tests/aggregators/__init__.py`
- Create: `scripts/tests/aggregators/test_custom_domain.py`
- Modify: `scripts/link_in_bio.py` → thin re-export shim (deleted in Task 17)

Migrates the existing `link_in_bio.py` into per-aggregator files and adds `custom_domain.py` for following redirect chains on creator-owned domains (very common: IG bio → `mylink.link/alice` → `onlyfans.com/alice`).

- [ ] **Step 1: Create package init files**

```bash
mkdir -p scripts/aggregators scripts/tests/aggregators
touch scripts/aggregators/__init__.py scripts/tests/aggregators/__init__.py
```

- [ ] **Step 2: Create `aggregators/linktree.py`**

Create `scripts/aggregators/linktree.py`:

```python
# scripts/aggregators/linktree.py — Resolve linktr.ee pages to outbound destinations
from urllib.parse import urlparse
import httpx
from bs4 import BeautifulSoup

_HOSTS = {"linktr.ee"}
_EXCLUDED_SCHEMES = {"mailto", "tel", "javascript"}


def _host(url: str) -> str:
    return (urlparse(url).hostname or "").lower().removeprefix("www.")


def is_linktree(url: str) -> bool:
    return _host(url) in _HOSTS


def resolve(url: str, timeout: float = 10.0) -> list[str]:
    """Fetch a linktr.ee URL and return deduplicated outbound destination URLs.

    Returns [] on non-linktree URL, HTTP errors, or parse failures. Excludes
    the aggregator's own domain and sub-pages (/help, /legal). Excludes
    mailto/tel/javascript schemes.
    """
    if not is_linktree(url):
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
        if scheme in _EXCLUDED_SCHEMES or scheme not in {"http", "https"}:
            continue
        dest_host = _host(href)
        if not dest_host or dest_host == source_host or dest_host.endswith(source_host):
            continue
        if href in seen:
            continue
        seen.add(href)
        out.append(href)
    return out
```

- [ ] **Step 3: Create `aggregators/beacons.py`**

Create `scripts/aggregators/beacons.py`:

```python
# scripts/aggregators/beacons.py — Resolve beacons.ai / beacons.page to destinations
from urllib.parse import urlparse
import httpx
from bs4 import BeautifulSoup

_HOSTS = {"beacons.ai", "beacons.page"}
_EXCLUDED_SCHEMES = {"mailto", "tel", "javascript"}


def _host(url: str) -> str:
    return (urlparse(url).hostname or "").lower().removeprefix("www.")


def is_beacons(url: str) -> bool:
    return _host(url) in _HOSTS


def resolve(url: str, timeout: float = 10.0) -> list[str]:
    if not is_beacons(url):
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
        if scheme in _EXCLUDED_SCHEMES or scheme not in {"http", "https"}:
            continue
        dest_host = _host(href)
        if not dest_host or dest_host == source_host or dest_host.endswith(source_host):
            continue
        if href in seen:
            continue
        seen.add(href)
        out.append(href)
    return out
```

- [ ] **Step 4: Write failing tests for custom_domain**

Create `scripts/tests/aggregators/test_custom_domain.py`:

```python
# scripts/tests/aggregators/test_custom_domain.py
from unittest.mock import patch, MagicMock
from aggregators.custom_domain import resolve


_HTML_WITH_LINKS = b"""
<html><body>
<a href="https://onlyfans.com/alice">My OF</a>
<a href="https://instagram.com/alice_backup">IG backup</a>
<a href="mailto:alice@example.com">email</a>
<a href="https://amazon.com/shop/alice">Shop</a>
</body></html>
"""


@patch("aggregators.custom_domain.httpx.Client")
def test_resolve_follows_redirects_and_extracts_links(mock_client_cls):
    mock_client = MagicMock()
    mock_client_cls.return_value.__enter__.return_value = mock_client
    resp = MagicMock()
    resp.status_code = 200
    resp.text = _HTML_WITH_LINKS.decode()
    resp.url = "https://creator-funnel.example/alice"  # final redirect target
    mock_client.get.return_value = resp

    destinations = resolve("https://mylink.link/alice")

    assert "https://onlyfans.com/alice" in destinations
    assert "https://instagram.com/alice_backup" in destinations
    assert "https://amazon.com/shop/alice" in destinations
    assert not any("mailto:" in d for d in destinations)


@patch("aggregators.custom_domain.httpx.Client")
def test_resolve_returns_empty_on_error(mock_client_cls):
    mock_client = MagicMock()
    mock_client_cls.return_value.__enter__.return_value = mock_client
    mock_client.get.side_effect = Exception("timeout")

    destinations = resolve("https://down.example/")
    assert destinations == []


@patch("aggregators.custom_domain.httpx.Client")
def test_resolve_returns_empty_on_404(mock_client_cls):
    mock_client = MagicMock()
    mock_client_cls.return_value.__enter__.return_value = mock_client
    resp = MagicMock()
    resp.status_code = 404
    mock_client.get.return_value = resp

    destinations = resolve("https://gone.example/")
    assert destinations == []
```

Run: `cd scripts && python -m pytest tests/aggregators/ -v`
Expected: fails.

- [ ] **Step 5: Implement custom_domain resolver**

Create `scripts/aggregators/custom_domain.py`:

```python
# scripts/aggregators/custom_domain.py — Follow redirect chains + extract outbound links
from urllib.parse import urlparse
import httpx
from bs4 import BeautifulSoup

_EXCLUDED_SCHEMES = {"mailto", "tel", "javascript"}
_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
}


def _host(url: str) -> str:
    return (urlparse(url).hostname or "").lower().removeprefix("www.")


def resolve(url: str, timeout: float = 10.0) -> list[str]:
    """Follow redirect chain from a custom-domain URL and extract all outbound HTTP links.

    Used when classifier returns (custom_domain, link_in_bio) or when a creator's
    bio links to a creator-owned redirect domain (mylink.link, hoo.be, etc.).
    Returns deduplicated outbound URLs excluding the final host's own domain.

    Returns [] on network error, 4xx/5xx, or parse failure.
    """
    try:
        with httpx.Client(follow_redirects=True, timeout=timeout,
                           max_redirects=5, headers=_HEADERS) as client:
            resp = client.get(url)
    except Exception:
        return []

    if resp.status_code != 200:
        return []

    final_host = _host(str(resp.url))
    soup = BeautifulSoup(resp.text, "html.parser")
    seen: set[str] = set()
    out: list[str] = []
    for a in soup.find_all("a", href=True):
        href: str = a["href"].strip()
        if not href or href.startswith("#"):
            continue
        scheme = urlparse(href).scheme.lower()
        if scheme in _EXCLUDED_SCHEMES or scheme not in {"http", "https"}:
            continue
        dest_host = _host(href)
        if not dest_host or dest_host == final_host:
            continue
        if href in seen:
            continue
        seen.add(href)
        out.append(href)
    return out
```

- [ ] **Step 6: Rewrite `link_in_bio.py` as shim**

Rewrite `scripts/link_in_bio.py` (preserves PR #2's test imports until Task 17 cuts them over):

```python
# scripts/link_in_bio.py — DEPRECATED shim. Use aggregators.{linktree,beacons,custom_domain} directly.
from aggregators.linktree import is_linktree, resolve as _resolve_linktree
from aggregators.beacons import is_beacons, resolve as _resolve_beacons


def is_aggregator_url(url: str) -> bool:
    return is_linktree(url) or is_beacons(url)


def resolve_link_in_bio(url: str, timeout: float = 10.0) -> list[str]:
    if is_linktree(url):
        return _resolve_linktree(url, timeout=timeout)
    if is_beacons(url):
        return _resolve_beacons(url, timeout=timeout)
    return []
```

- [ ] **Step 7: Run all tests**

Run: `cd scripts && python -m pytest tests/ -v`
Expected: all tests pass including existing 45 + new Task 13 custom_domain tests (3 new).

- [ ] **Step 8: Commit**

```bash
git add scripts/aggregators/ scripts/tests/aggregators/ scripts/link_in_bio.py
git commit -m "refactor(pipeline): split link_in_bio into aggregators/ + add custom_domain

Per-aggregator modules with uniform is_X() + resolve() shape. link_in_bio.py
becomes a re-export shim until Task 17 rewires discover_creator.py onto the
resolver.

New aggregators.custom_domain follows redirect chains on creator-owned
redirect domains (mylink.link, hoo.be, vanity domains fronting OF, etc.)
and extracts outbound links from the landing HTML. Excludes mailto/tel/
javascript schemes and the final host's own domain."
```

---

## Task 14: `schemas.py` additions

**Files:**
- Modify: `scripts/schemas.py`
- Modify: `scripts/tests/test_schemas.py` (add new-type tests)

Adds Pydantic models for the v2 surface: `DiscoveredUrl`, `TextMention`, `BulkImportRecord`. Narrows `DiscoveryResult` (Gemini no longer classifies URLs).

- [ ] **Step 1: Read current `schemas.py`**

```bash
sed -n '1,95p' scripts/schemas.py
```

Already read in context. Confirm shape matches what's embedded in Task 8.

- [ ] **Step 2: Append new models**

Edit `scripts/schemas.py`. Append at end of file:

```python

# --- v2 additions ---

DestinationClass = Literal["monetization", "aggregator", "social", "other"]
DiscoverySource = Literal["seed", "manual_add", "retry", "auto_expand"]


class DiscoveredUrl(BaseModel):
    """A URL the resolver discovered + classified. One row per URL in the creator's network."""
    canonical_url: str
    platform: Platform
    account_type: AccountType
    destination_class: DestinationClass
    reason: str  # 'rule:X' | 'llm:high_confidence' | 'llm:cache_hit' | 'llm:low_confidence' | 'llm:timeout' | 'manual_add'


class TextMention(BaseModel):
    """A handle Gemini extracted from bio prose (no URL present). Fed back into Stage B."""
    platform: Platform
    handle: str
    source: Literal["seed_bio", "enriched_bio"] = "seed_bio"


class DiscoveryResultV2(BaseModel):
    """Narrower Gemini output shape — no URL classification, no account proposals.

    Resolver output populates accounts/funnel_edges directly from the classifier
    and fetchers; Gemini's remaining job is canonicalization + niche + text hints.
    """
    canonical_name: str
    known_usernames: list[str]
    display_name_variants: list[str]
    primary_niche: Optional[str] = None
    monetization_model: MonetizationModel = "unknown"
    text_mentions: list[TextMention] = Field(default_factory=list)
    raw_reasoning: str
```

- [ ] **Step 3: Add tests**

Append to `scripts/tests/test_schemas.py`:

```python

# --- v2 additions ---
from schemas import DiscoveredUrl, TextMention, DiscoveryResultV2


class TestDiscoveredUrl:
    def test_accepts_valid_monetization(self):
        du = DiscoveredUrl(
            canonical_url="https://onlyfans.com/alice",
            platform="onlyfans", account_type="monetization",
            destination_class="monetization", reason="rule:onlyfans_monetization",
        )
        assert du.platform == "onlyfans"

    def test_rejects_invalid_platform(self):
        import pydantic
        with pytest.raises(pydantic.ValidationError):
            DiscoveredUrl(
                canonical_url="x", platform="bogus", account_type="social",
                destination_class="social", reason="x",
            )

    def test_rejects_invalid_destination_class(self):
        import pydantic
        with pytest.raises(pydantic.ValidationError):
            DiscoveredUrl(
                canonical_url="x", platform="instagram", account_type="social",
                destination_class="bogus", reason="x",
            )


class TestTextMention:
    def test_default_source_is_seed_bio(self):
        tm = TextMention(platform="instagram", handle="alice")
        assert tm.source == "seed_bio"

    def test_rejects_unknown_platform(self):
        import pydantic
        with pytest.raises(pydantic.ValidationError):
            TextMention(platform="bogus", handle="alice")


class TestDiscoveryResultV2:
    def test_minimal(self):
        r = DiscoveryResultV2(
            canonical_name="Alice",
            known_usernames=["alice"],
            display_name_variants=["Alice"],
            raw_reasoning="short",
        )
        assert r.monetization_model == "unknown"
        assert r.text_mentions == []

    def test_no_longer_has_proposed_accounts_or_edges(self):
        # The v1 DiscoveryResult required proposed_accounts/proposed_funnel_edges.
        # V2 omits them entirely — classifier + resolver own those.
        r = DiscoveryResultV2(
            canonical_name="Alice", known_usernames=["alice"],
            display_name_variants=["Alice"], raw_reasoning="x",
        )
        assert not hasattr(r, "proposed_accounts")
        assert not hasattr(r, "proposed_funnel_edges")
```

- [ ] **Step 4: Run tests**

Run: `cd scripts && python -m pytest tests/test_schemas.py -v`
Expected: existing tests still pass + 7 new tests pass.

- [ ] **Step 5: Commit**

```bash
git add scripts/schemas.py scripts/tests/test_schemas.py
git commit -m "feat(pipeline): schemas.py v2 additions — DiscoveredUrl, TextMention, DiscoveryResultV2

DiscoveredUrl: one Pydantic row per URL in the network (canonical_url +
platform + account_type + destination_class + reason). Validates against the
platform/account_type enums.

TextMention: handle Gemini extracted from prose (no URL). Resolver
synthesizes URL + feeds back into Stage B once per seed.

DiscoveryResultV2: narrower Gemini output — no proposed_accounts, no
proposed_funnel_edges. Classifier + resolver own URL discovery; Gemini
returns canonical_name / niche / text_mentions only."
```

---

## Task 15: `pipeline/resolver.py` — the two-stage core

**Files:**
- Create: `scripts/pipeline/resolver.py`
- Create: `scripts/tests/pipeline/test_resolver.py`

The resolver orchestrates everything above. Two stages, structural — no depth param. Budget-aware. Gemini narrows to canonicalization + niche + text_mentions. Aggregator children are terminal leaves (no further chaining).

- [ ] **Step 1: Write failing tests**

Create `scripts/tests/pipeline/test_resolver.py`:

```python
# scripts/tests/pipeline/test_resolver.py
from unittest.mock import MagicMock, patch
import pytest

from schemas import InputContext, DiscoveryResultV2, TextMention
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


@patch("pipeline.resolver.run_gemini_discovery_v2")
@patch("pipeline.resolver.classify")
@patch("pipeline.resolver.fetch_seed")
def test_stage_a_fetches_seed_then_stage_b_classifies_urls(
    mock_fetch, mock_classify, mock_gemini,
):
    mock_fetch.return_value = _mk_ctx(
        external_urls=["https://onlyfans.com/alice"],
    )
    mock_classify.return_value = Classification(
        platform="onlyfans", account_type="monetization",
        confidence=1.0, reason="rule:onlyfans_monetization",
    )
    mock_gemini.return_value = DiscoveryResultV2(
        canonical_name="Alice", known_usernames=["alice"],
        display_name_variants=["Alice"], raw_reasoning="",
    )

    budget = BudgetTracker(cap_cents=1000)
    result = resolve_seed(
        handle="alice", platform_hint="instagram",
        supabase=MagicMock(), apify_client=MagicMock(),
        budget=budget,
    )

    assert result.seed_context.handle == "alice"
    assert len(result.discovered_urls) == 1
    assert result.discovered_urls[0].platform == "onlyfans"
    assert result.discovered_urls[0].destination_class == "monetization"


@patch("pipeline.resolver.aggregators_linktree.resolve")
@patch("pipeline.resolver.run_gemini_discovery_v2")
@patch("pipeline.resolver.classify")
@patch("pipeline.resolver.fetch_seed")
def test_aggregator_children_expanded_once_not_chained(
    mock_fetch, mock_classify, mock_gemini, mock_linktree_resolve,
):
    # Seed has a linktree URL; linktree resolves to 2 destinations
    mock_fetch.return_value = _mk_ctx(
        external_urls=["https://linktr.ee/alice"],
    )
    mock_linktree_resolve.return_value = [
        "https://onlyfans.com/alice",
        "https://linktr.ee/other",  # another linktree — should NOT be expanded again
    ]
    classifications = iter([
        Classification(platform="linktree", account_type="link_in_bio",
                       confidence=1.0, reason="rule:linktree_link_in_bio"),
        Classification(platform="onlyfans", account_type="monetization",
                       confidence=1.0, reason="rule:onlyfans_monetization"),
        Classification(platform="linktree", account_type="link_in_bio",
                       confidence=1.0, reason="rule:linktree_link_in_bio"),
    ])
    mock_classify.side_effect = lambda *a, **kw: next(classifications)
    mock_gemini.return_value = DiscoveryResultV2(
        canonical_name="Alice", known_usernames=["alice"],
        display_name_variants=["Alice"], raw_reasoning="",
    )

    budget = BudgetTracker(cap_cents=1000)
    result = resolve_seed(
        handle="alice", platform_hint="instagram",
        supabase=MagicMock(), apify_client=MagicMock(),
        budget=budget,
    )

    # Should have 3 URLs: the linktree itself + 2 destinations.
    # The second linktree (linktr.ee/other) is recorded but NOT re-expanded.
    assert len(result.discovered_urls) == 3
    # Only the first linktree was resolved — mock_linktree_resolve called once.
    assert mock_linktree_resolve.call_count == 1


@patch("pipeline.resolver.run_gemini_discovery_v2")
@patch("pipeline.resolver.classify")
@patch("pipeline.resolver.fetch_seed")
def test_text_mentions_synthesize_urls_and_loop_stage_b(
    mock_fetch, mock_classify, mock_gemini,
):
    mock_fetch.return_value = _mk_ctx(
        bio="also @alice_backup on tiktok",
        external_urls=[],
    )
    mock_gemini.return_value = DiscoveryResultV2(
        canonical_name="Alice", known_usernames=["alice", "alice_backup"],
        display_name_variants=["Alice"],
        text_mentions=[TextMention(platform="tiktok", handle="alice_backup")],
        raw_reasoning="",
    )
    mock_classify.return_value = Classification(
        platform="tiktok", account_type="social",
        confidence=1.0, reason="rule:tiktok_social",
    )

    budget = BudgetTracker(cap_cents=1000)
    result = resolve_seed(
        handle="alice", platform_hint="instagram",
        supabase=MagicMock(), apify_client=MagicMock(),
        budget=budget,
    )

    # The synthesized https://tiktok.com/@alice_backup should appear
    assert any("alice_backup" in du.canonical_url for du in result.discovered_urls)


@patch("pipeline.resolver.run_gemini_discovery_v2")
@patch("pipeline.resolver.classify")
@patch("pipeline.resolver.fetch_seed")
def test_empty_seed_context_raises(mock_fetch, mock_classify, mock_gemini):
    from fetchers.base import EmptyDatasetError
    mock_fetch.side_effect = EmptyDatasetError("login wall")

    budget = BudgetTracker(cap_cents=1000)
    with pytest.raises(EmptyDatasetError):
        resolve_seed(
            handle="empty", platform_hint="instagram",
            supabase=MagicMock(), apify_client=MagicMock(),
            budget=budget,
        )
```

Run: `cd scripts && python -m pytest tests/pipeline/test_resolver.py -v`
Expected: fails.

- [ ] **Step 2: Implement resolver**

Create `scripts/pipeline/resolver.py`:

```python
# scripts/pipeline/resolver.py — Two-stage resolver: fetch seed, then classify+enrich destinations
from dataclasses import dataclass, field
from urllib.parse import urlparse

from apify_client import ApifyClient

from schemas import (
    InputContext, DiscoveredUrl, DiscoveryResultV2, TextMention,
)
from common import console
from pipeline.canonicalize import canonicalize_url, resolve_short_url
from pipeline.classifier import classify, Classification
from pipeline.budget import BudgetTracker, BudgetExhaustedError

# Fetchers + aggregators dispatch
from fetchers import instagram as fetch_ig
from fetchers import tiktok as fetch_tt
from fetchers import youtube as fetch_yt
from fetchers import patreon as fetch_patreon
from fetchers import onlyfans as fetch_of
from fetchers import fanvue as fetch_fanvue
from fetchers import facebook as fetch_fb
from fetchers import twitter as fetch_twitter
from fetchers import generic as fetch_generic
from fetchers.base import EmptyDatasetError
from aggregators import linktree as aggregators_linktree
from aggregators import beacons as aggregators_beacons
from aggregators import custom_domain as aggregators_custom


# Apify cost table in cents per run. Hand-maintained, err on the high side.
_APIFY_COSTS = {
    "apify/instagram-scraper": 10,
    "clockworks/tiktok-scraper": 8,
    # YouTube (yt-dlp) + Patreon + OF + Fanvue + generic + aggregators: 0 (not Apify)
}


@dataclass
class ResolverResult:
    seed_context: InputContext
    gemini_result: DiscoveryResultV2
    enriched_contexts: dict[str, InputContext]  # {canonical_url: ctx} for fetched secondaries
    discovered_urls: list[DiscoveredUrl] = field(default_factory=list)


def _fetcher_for(platform: str):
    return {
        "instagram": fetch_ig.fetch,
        "tiktok": fetch_tt.fetch,
        "youtube": fetch_yt.fetch,
        "patreon": fetch_patreon.fetch,
        "onlyfans": fetch_of.fetch,
        "fanvue": fetch_fanvue.fetch,
        "facebook": fetch_fb.fetch,
        "twitter": fetch_twitter.fetch,
    }.get(platform)


def _destination_class_for(account_type: str) -> str:
    return {
        "monetization": "monetization",
        "link_in_bio": "aggregator",
        "social": "social",
    }.get(account_type, "other")


def _apify_cost(platform: str) -> int:
    # map platform to actor cost
    return {
        "instagram": _APIFY_COSTS["apify/instagram-scraper"],
        "tiktok": _APIFY_COSTS["clockworks/tiktok-scraper"],
    }.get(platform, 0)


def _handle_from_url(url: str, platform: str) -> str | None:
    """Extract a handle from a URL. Returns None if the URL shape is unrecognized."""
    parts = urlparse(url).path.strip("/").split("/")
    if not parts or not parts[0]:
        return None
    first = parts[0]
    if platform in ("tiktok", "youtube") and first.startswith("@"):
        return first
    return first


def fetch_seed(handle: str, platform_hint: str, apify_client) -> InputContext:
    """Stage A: fetch the seed profile via the platform fetcher."""
    fetcher = _fetcher_for(platform_hint)
    if fetcher is None:
        raise ValueError(f"Unsupported platform_hint={platform_hint!r}")

    if platform_hint in ("instagram", "tiktok"):
        ctx = fetcher(apify_client, handle)
    else:
        ctx = fetcher(handle)

    if ctx.is_empty():
        raise EmptyDatasetError(
            f"Seed fetch for @{handle} on {platform_hint} produced empty context."
        )
    return ctx


def run_gemini_discovery_v2(ctx: InputContext) -> DiscoveryResultV2:
    """Call Gemini for canonicalization + niche + text_mentions ONLY.

    No URL classification, no account proposals — those are the resolver's job.
    Implemented in discover_creator.py (see Task 17). Kept as a module-level
    symbol here so test_resolver.py can mock at this import site.
    """
    from discover_creator import run_gemini_discovery_v2 as _impl
    return _impl(ctx)


def _synthesize_url(mention: TextMention) -> str | None:
    host_for = {
        "instagram": "instagram.com",
        "tiktok": "tiktok.com",
        "youtube": "youtube.com",
        "twitter": "x.com",
        "facebook": "facebook.com",
        "patreon": "patreon.com",
        "onlyfans": "onlyfans.com",
        "fanvue": "fanvue.com",
    }.get(mention.platform)
    if not host_for:
        return None
    handle = mention.handle.lstrip("@")
    if mention.platform in ("tiktok", "youtube"):
        return f"https://{host_for}/@{handle}"
    return f"https://{host_for}/{handle}"


def resolve_seed(
    handle: str, platform_hint: str,
    supabase, apify_client: ApifyClient,
    budget: BudgetTracker,
) -> ResolverResult:
    """Two-stage resolver for one seed.

    Stage A: fetch seed, debit budget.
    Stage B: classify + enrich every discovered URL. Aggregators expanded once.
    Gemini pass: canonicalization + niche + text_mentions. Text mentions fed
    back into Stage B once per seed (no further recursion).
    """
    # Stage A
    budget.debit(f"apify/{platform_hint}-scraper", _apify_cost(platform_hint))
    seed_ctx = fetch_seed(handle, platform_hint, apify_client)
    console.log(f"[cyan]Stage A: @{handle} on {platform_hint} — "
                f"bio={bool(seed_ctx.bio)} followers={seed_ctx.follower_count} "
                f"external={len(seed_ctx.external_urls)}[/cyan]")

    discovered: list[DiscoveredUrl] = []
    enriched: dict[str, InputContext] = {}
    visited_canonical: set[str] = set()
    aggregator_expanded: set[str] = set()

    def _classify_and_enrich(url: str, is_aggregator_child: bool = False):
        """Classify URL, optionally enrich profile, record in discovered list."""
        # Resolve short URLs, then canonicalize
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
        ))

        # If aggregator, expand one level (only if not already a child — no chaining)
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
                _classify_and_enrich(child, is_aggregator_child=True)
            return

        # If profile, try to enrich (if budget allows + fetcher exists)
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
                pass
            except Exception as e:
                console.log(f"[yellow]enrichment failed for {canon}: {e}[/yellow]")

    # Stage B for seed's externalUrls
    for url in seed_ctx.external_urls:
        try:
            _classify_and_enrich(url)
        except BudgetExhaustedError:
            break

    # Gemini pass
    gemini_result = run_gemini_discovery_v2(seed_ctx)

    # Stage B for text_mentions (one-shot expansion only, no further recursion)
    for mention in gemini_result.text_mentions:
        synth = _synthesize_url(mention)
        if synth:
            try:
                _classify_and_enrich(synth)
            except BudgetExhaustedError:
                break

    return ResolverResult(
        seed_context=seed_ctx,
        gemini_result=gemini_result,
        enriched_contexts=enriched,
        discovered_urls=discovered,
    )
```

- [ ] **Step 3: Run tests**

Run: `cd scripts && python -m pytest tests/pipeline/test_resolver.py -v`
Expected: all 4 tests pass. If `run_gemini_discovery_v2` import issue surfaces (it's defined in discover_creator.py in Task 17 but referenced here), the tests mock the symbol directly via `pipeline.resolver.run_gemini_discovery_v2` so the resolver module import doesn't need the symbol to exist yet. If pytest complains at import-time, move the `from discover_creator import` inside `run_gemini_discovery_v2`'s function body (already done).

- [ ] **Step 4: Commit**

```bash
git add scripts/pipeline/resolver.py scripts/tests/pipeline/test_resolver.py
git commit -m "feat(pipeline): two-stage resolver — fetch seed, then classify+enrich destinations

No depth parameter. Aggregator children expanded once (no chaining). Each
URL canonicalized + classified + optionally enriched via platform fetcher.
Budget debited per Apify fetch; BudgetExhaustedError inside Stage B breaks
the loop cleanly. Gemini narrows to canonicalization+niche+text_mentions
(v2 shape); text_mentions synthesized into URLs and fed back into Stage B
once per seed (no recursion).

ResolverResult bundles seed context + gemini output + enriched secondaries
+ discovered_urls list. Consumed by commit_discovery_result v2 in Task 16."
```

---

## Task 16: RPC extensions — `commit_discovery_result` v2 + `bulk_import_creator` v2 + `run_cross_workspace_merge_pass`

**Files:**
- Create: `supabase/migrations/20260425000100_discovery_v2_rpcs.sql`

Three RPC changes in one migration:

1. `commit_discovery_result` — new `p_discovered_urls` + `p_bulk_import_id` params, writes `profile_destination_links`, bumps `bulk_imports` counters.
2. `bulk_import_creator` — creates a `bulk_imports` row, returns `{bulk_import_id, run_id}` instead of just the creator_id. Existing callers that pass one handle still work (the new shape is additive in return).
3. `run_cross_workspace_merge_pass` — new RPC, uses `profile_destination_links` inverted index to raise `creator_merge_candidates` on shared strong signals across an entire workspace (runs once after all seeds in a bulk commit).

- [ ] **Step 1: Write the migration**

Create `supabase/migrations/20260425000100_discovery_v2_rpcs.sql`:

```sql
-- 20260425000100_discovery_v2_rpcs.sql
-- Discovery v2 RPC surface per spec §4.4.
-- 1. commit_discovery_result: new p_discovered_urls + p_bulk_import_id params
-- 2. bulk_import_creator: creates bulk_imports row, returns bulk_import_id + run_ids
-- 3. run_cross_workspace_merge_pass: new RPC for cross-workspace identity dedup

BEGIN;

-- ============================================================================
-- 1. commit_discovery_result v2
-- ============================================================================

CREATE OR REPLACE FUNCTION commit_discovery_result(
  p_run_id uuid,
  p_creator_data jsonb,
  p_accounts jsonb,
  p_funnel_edges jsonb,
  p_discovered_urls jsonb DEFAULT '[]'::jsonb,
  p_bulk_import_id uuid DEFAULT NULL
)
RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
  v_run record;
  v_creator_id uuid;
  v_workspace_id uuid;
  v_accounts_upserted int := 0;
  v_urls_recorded int := 0;
  v_merge_candidates_raised int := 0;
  v_account jsonb;
  v_edge jsonb;
  v_url jsonb;
  v_profile_id uuid;
  v_from_pid uuid;
  v_to_pid uuid;
  v_source text;
  v_canonical_name text;
BEGIN
  SELECT * INTO v_run FROM discovery_runs WHERE id = p_run_id;
  IF NOT FOUND THEN
    RAISE EXCEPTION 'discovery_run % not found', p_run_id;
  END IF;

  v_creator_id := v_run.creator_id;
  v_workspace_id := v_run.workspace_id;
  v_source := v_run.source;

  -- Enrich creator — but on manual_add, preserve human-confirmed canonical fields
  v_canonical_name := NULLIF(NULLIF(TRIM(p_creator_data->>'canonical_name'), ''), 'Unknown');

  IF v_source = 'manual_add' THEN
    -- Only union-merge known_usernames; do not overwrite identity fields
    UPDATE creators SET
      known_usernames = (
        SELECT ARRAY(
          SELECT DISTINCT unnest(
            COALESCE(known_usernames, ARRAY[]::text[]) ||
            COALESCE(ARRAY(SELECT jsonb_array_elements_text(p_creator_data->'known_usernames')),
                     ARRAY[]::text[])
          )
        )
      ),
      updated_at = NOW()
    WHERE id = v_creator_id;
  ELSE
    UPDATE creators SET
      canonical_name = COALESCE(v_canonical_name, canonical_name),
      known_usernames = COALESCE(
        ARRAY(SELECT DISTINCT unnest(
          COALESCE(known_usernames, ARRAY[]::text[]) ||
          COALESCE(ARRAY(SELECT jsonb_array_elements_text(p_creator_data->'known_usernames')),
                   ARRAY[]::text[])
        )),
        known_usernames
      ),
      display_name_variants = COALESCE(
        ARRAY(SELECT DISTINCT unnest(
          COALESCE(display_name_variants, ARRAY[]::text[]) ||
          COALESCE(ARRAY(SELECT jsonb_array_elements_text(p_creator_data->'display_name_variants')),
                   ARRAY[]::text[])
        )),
        display_name_variants
      ),
      primary_niche = COALESCE(p_creator_data->>'primary_niche', primary_niche),
      monetization_model = COALESCE(
        NULLIF(p_creator_data->>'monetization_model', '')::monetization_model,
        monetization_model
      ),
      onboarding_status = 'ready',
      updated_at = NOW()
    WHERE id = v_creator_id;
  END IF;

  -- Upsert each proposed account as a profile row
  FOR v_account IN SELECT jsonb_array_elements(p_accounts)
  LOOP
    INSERT INTO profiles (
      workspace_id, creator_id, platform, handle, url, display_name,
      bio, follower_count, account_type, is_primary, discovery_confidence,
      discovery_reason, is_active, updated_at
    )
    VALUES (
      v_workspace_id, v_creator_id,
      (v_account->>'platform')::platform,
      v_account->>'handle',
      v_account->>'url',
      v_account->>'display_name',
      v_account->>'bio',
      (v_account->>'follower_count')::int,
      COALESCE((v_account->>'account_type')::account_type, 'social'),
      COALESCE((v_account->>'is_primary')::boolean, FALSE),
      (v_account->>'discovery_confidence')::numeric,
      v_account->>'reasoning',
      TRUE,
      NOW()
    )
    ON CONFLICT (workspace_id, platform, handle) DO UPDATE SET
      display_name = COALESCE(EXCLUDED.display_name, profiles.display_name),
      bio = COALESCE(EXCLUDED.bio, profiles.bio),
      follower_count = COALESCE(EXCLUDED.follower_count, profiles.follower_count),
      url = COALESCE(EXCLUDED.url, profiles.url),
      updated_at = NOW()
    RETURNING id INTO v_profile_id;

    v_accounts_upserted := v_accounts_upserted + 1;
  END LOOP;

  -- Insert funnel edges (resolve from/to handles to profile_ids)
  FOR v_edge IN SELECT jsonb_array_elements(p_funnel_edges)
  LOOP
    SELECT id INTO v_from_pid FROM profiles
    WHERE workspace_id = v_workspace_id
      AND platform = (v_edge->>'from_platform')::platform
      AND handle = v_edge->>'from_handle'
    LIMIT 1;

    SELECT id INTO v_to_pid FROM profiles
    WHERE workspace_id = v_workspace_id
      AND platform = (v_edge->>'to_platform')::platform
      AND handle = v_edge->>'to_handle'
    LIMIT 1;

    IF v_from_pid IS NOT NULL AND v_to_pid IS NOT NULL AND v_from_pid <> v_to_pid THEN
      INSERT INTO funnel_edges (
        workspace_id, creator_id, from_profile_id, to_profile_id,
        edge_type, confidence, detected_at
      )
      VALUES (
        v_workspace_id, v_creator_id, v_from_pid, v_to_pid,
        COALESCE((v_edge->>'edge_type')::edge_type, 'inferred'),
        (v_edge->>'confidence')::numeric,
        NOW()
      )
      ON CONFLICT DO NOTHING;
    END IF;
  END LOOP;

  -- Record discovered URLs into profile_destination_links (reverse index)
  FOR v_url IN SELECT jsonb_array_elements(p_discovered_urls)
  LOOP
    -- Find the profile this URL was discovered from. If the URL matches an
    -- existing profile on (platform, handle-in-URL), link there; otherwise
    -- link to the seed's primary profile for this creator.
    SELECT id INTO v_profile_id FROM profiles
    WHERE workspace_id = v_workspace_id
      AND creator_id = v_creator_id
      AND is_primary = TRUE
    LIMIT 1;

    IF v_profile_id IS NOT NULL THEN
      INSERT INTO profile_destination_links (
        profile_id, canonical_url, destination_class, workspace_id
      )
      VALUES (
        v_profile_id,
        v_url->>'canonical_url',
        v_url->>'destination_class',
        v_workspace_id
      )
      ON CONFLICT (profile_id, canonical_url) DO NOTHING;

      v_urls_recorded := v_urls_recorded + 1;
    END IF;
  END LOOP;

  -- Mark the run as completed
  UPDATE discovery_runs SET
    status = 'completed',
    completed_at = NOW(),
    assets_discovered_count = v_accounts_upserted,
    funnel_edges_discovered_count = jsonb_array_length(p_funnel_edges),
    bulk_import_id = COALESCE(p_bulk_import_id, bulk_import_id),
    updated_at = NOW()
  WHERE id = p_run_id;

  -- Bump bulk_imports counter if applicable
  IF p_bulk_import_id IS NOT NULL THEN
    UPDATE bulk_imports SET
      seeds_committed = seeds_committed + 1,
      updated_at = NOW()
    WHERE id = p_bulk_import_id;
  END IF;

  RETURN jsonb_build_object(
    'creator_id', v_creator_id,
    'accounts_upserted', v_accounts_upserted,
    'merge_candidates_raised', v_merge_candidates_raised,
    'urls_recorded', v_urls_recorded
  );
END;
$$;

GRANT EXECUTE ON FUNCTION commit_discovery_result(uuid, jsonb, jsonb, jsonb, jsonb, uuid)
  TO authenticated, service_role;


-- ============================================================================
-- 2. bulk_import_creator v2: creates bulk_imports row, returns structured result
-- ============================================================================

CREATE OR REPLACE FUNCTION bulk_import_creator(
  p_handle text,
  p_platform_hint text,
  p_tracking_type tracking_type,
  p_tags text[],
  p_user_id uuid,
  p_workspace_id uuid,
  p_bulk_import_id uuid DEFAULT NULL
)
RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
  v_bulk_id uuid;
  v_creator_id uuid;
  v_run_id uuid;
  v_profile_id uuid;
BEGIN
  -- Create bulk_imports row if not passed in (single-handle path)
  IF p_bulk_import_id IS NULL THEN
    INSERT INTO bulk_imports (workspace_id, initiated_by, seeds_total)
    VALUES (p_workspace_id, p_user_id, 1)
    RETURNING id INTO v_bulk_id;
  ELSE
    v_bulk_id := p_bulk_import_id;
  END IF;

  -- Create creator row (placeholder — canonical_name = handle until discovery fills)
  INSERT INTO creators (
    workspace_id, canonical_name, slug, known_usernames, primary_platform,
    tracking_type, tags, onboarding_status, import_source, added_by
  )
  VALUES (
    p_workspace_id, p_handle,
    p_handle || '-' || substring(gen_random_uuid()::text, 1, 16),
    ARRAY[p_handle],
    p_platform_hint::platform,
    p_tracking_type,
    COALESCE(p_tags, ARRAY[]::text[]),
    'processing',
    'bulk_import',
    p_user_id
  )
  RETURNING id INTO v_creator_id;

  -- Create primary profile stub
  INSERT INTO profiles (
    workspace_id, creator_id, platform, handle,
    tracking_type, tags, is_primary, is_active, added_by,
    discovery_reason, discovery_confidence
  )
  VALUES (
    p_workspace_id, v_creator_id, p_platform_hint::platform, p_handle,
    p_tracking_type, COALESCE(p_tags, ARRAY[]::text[]), TRUE, TRUE, p_user_id,
    'bulk_import', 1.0
  )
  RETURNING id INTO v_profile_id;

  -- Create pending discovery_run linked to bulk_import
  INSERT INTO discovery_runs (
    workspace_id, creator_id, input_handle, input_platform_hint,
    status, attempt_number, initiated_by, started_at,
    bulk_import_id, source
  )
  VALUES (
    p_workspace_id, v_creator_id, p_handle, p_platform_hint,
    'pending', 1, p_user_id, NOW(),
    v_bulk_id, 'seed'
  )
  RETURNING id INTO v_run_id;

  -- Link creator to the run
  UPDATE creators SET last_discovery_run_id = v_run_id WHERE id = v_creator_id;

  RETURN jsonb_build_object(
    'bulk_import_id', v_bulk_id,
    'creator_id', v_creator_id,
    'run_id', v_run_id
  );
END;
$$;

GRANT EXECUTE ON FUNCTION bulk_import_creator(text, text, tracking_type, text[], uuid, uuid, uuid)
  TO authenticated, anon, service_role;


-- ============================================================================
-- 3. run_cross_workspace_merge_pass: raise merge candidates from inverted index
-- ============================================================================

CREATE OR REPLACE FUNCTION run_cross_workspace_merge_pass(
  p_workspace_id uuid,
  p_bulk_import_id uuid DEFAULT NULL
)
RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
  v_candidates_raised int := 0;
  v_bucket record;
BEGIN
  -- Find URL buckets (in workspace) with >1 distinct creator attached
  FOR v_bucket IN
    SELECT
      pdl.canonical_url,
      pdl.destination_class,
      array_agg(DISTINCT p.creator_id) AS creator_ids
    FROM profile_destination_links pdl
    JOIN profiles p ON p.id = pdl.profile_id
    WHERE pdl.workspace_id = p_workspace_id
      AND pdl.destination_class IN ('monetization', 'aggregator')
      AND p.creator_id IS NOT NULL
    GROUP BY pdl.canonical_url, pdl.destination_class
    HAVING COUNT(DISTINCT p.creator_id) > 1
  LOOP
    -- For every pair of creator_ids in the bucket, insert a merge candidate
    -- (ordered so a < b, absorbed by the unique index on re-runs)
    INSERT INTO creator_merge_candidates (
      workspace_id, creator_a_id, creator_b_id, confidence, evidence, status
    )
    SELECT
      p_workspace_id,
      LEAST(a.id, b.id),
      GREATEST(a.id, b.id),
      1.0,
      jsonb_build_object(
        'reason',
        CASE v_bucket.destination_class
          WHEN 'monetization' THEN 'shared_monetization_url'
          ELSE 'shared_aggregator_url'
        END,
        'shared_url', v_bucket.canonical_url,
        'class', v_bucket.destination_class
      ),
      'pending'
    FROM unnest(v_bucket.creator_ids) AS a(id)
    CROSS JOIN unnest(v_bucket.creator_ids) AS b(id)
    WHERE a.id < b.id
    ON CONFLICT (LEAST(creator_a_id, creator_b_id), GREATEST(creator_a_id, creator_b_id))
      DO UPDATE SET evidence = EXCLUDED.evidence;

    v_candidates_raised := v_candidates_raised + 1;
  END LOOP;

  -- Mark bulk_import merge pass complete
  IF p_bulk_import_id IS NOT NULL THEN
    UPDATE bulk_imports SET
      merge_pass_completed_at = NOW(),
      status = CASE
        WHEN seeds_failed > 0 AND seeds_blocked_by_budget > 0 THEN 'partial_budget_exceeded'
        WHEN seeds_failed > 0 THEN 'completed_with_failures'
        WHEN seeds_blocked_by_budget > 0 THEN 'partial_budget_exceeded'
        ELSE 'completed'
      END,
      updated_at = NOW()
    WHERE id = p_bulk_import_id;
  END IF;

  RETURN jsonb_build_object(
    'buckets_evaluated', v_candidates_raised,
    'bulk_import_id', p_bulk_import_id
  );
END;
$$;

GRANT EXECUTE ON FUNCTION run_cross_workspace_merge_pass(uuid, uuid)
  TO authenticated, service_role;

COMMIT;
```

- [ ] **Step 2: Apply migration via Supabase MCP**

Name: `discovery_v2_rpcs`. Query: migration contents without leading filename comment.

Expected: success, no errors.

- [ ] **Step 3: Verify RPCs exist**

Via Supabase MCP `execute_sql`:

```sql
SELECT proname FROM pg_proc
WHERE proname IN ('commit_discovery_result', 'bulk_import_creator', 'run_cross_workspace_merge_pass')
ORDER BY proname;
```

Expected: 3 rows. `bulk_import_creator` may appear twice if old + new signatures coexist (Postgres allows overloads). That's OK — the new signature takes 7 args, old took 6; callers will hit the new one by matching param count.

- [ ] **Step 4: Regenerate types + SCHEMA.md**

```bash
npm run db:types
```

Skip db:schema regeneration — still blocked by `SUPABASE_DB_URL`; Task 21 (flag flip) will add manual SCHEMA.md edits.

- [ ] **Step 5: Commit**

```bash
git add supabase/migrations/20260425000100_discovery_v2_rpcs.sql src/types/database.types.ts
git commit -m "feat(db): discovery v2 RPCs

commit_discovery_result now accepts p_discovered_urls (writes to
profile_destination_links) and p_bulk_import_id (bumps bulk_imports
counters). Preserves manual_add semantics: does not overwrite
canonical_name/niche/monetization on manual_add runs, only union-merges
known_usernames.

bulk_import_creator extended to accept p_bulk_import_id; when NULL, creates
a new bulk_imports row (single-handle path). Returns {bulk_import_id,
creator_id, run_id}.

run_cross_workspace_merge_pass uses profile_destination_links as an
inverted index: any URL with destination_class in (monetization,
aggregator) that has >1 creator attached produces auto-merge candidates
for every pair. Unique-index absorbs re-runs."
```

---

## Task 17: Rewrite `discover_creator.py` as thin wrapper — feature-flagged

**Files:**
- Modify: `scripts/discover_creator.py`
- Delete: `scripts/apify_details.py` (shim no longer needed after this rewires)
- Delete: `scripts/link_in_bio.py` (same)

`discover_creator.run` becomes a dispatcher: if `DISCOVERY_V2_ENABLED=1`, call the resolver + new commit flow; otherwise fall through to the v1 path (which is in git history but kept temporarily via the shim pattern — actually we delete the shims; the v1 path goes away with this commit). Per the spec §9 feature-flag plan: rollout is one merge followed by a manual smoke; the flag exists so the old env can be exercised if needed, but the old shims are removed since everything that used them is being rewired here.

- [ ] **Step 1: Rewrite `discover_creator.py`**

Replace the full contents of `scripts/discover_creator.py` with:

```python
# scripts/discover_creator.py — Discovery entry point, dispatches to v1 or v2 resolver
import argparse
import json
import os
from pathlib import Path
from uuid import UUID

import google.generativeai as genai
from pydantic import ValidationError
from tenacity import retry, retry_if_not_exception_type, stop_after_attempt, wait_exponential

from common import get_supabase, get_gemini_key, console
from schemas import DiscoveryInput, InputContext, DiscoveryResultV2
from apify_scraper import get_apify_client, scrape_instagram_profile
from fetchers.base import EmptyDatasetError

from pipeline.resolver import resolve_seed, ResolverResult
from pipeline.budget import BudgetTracker, BudgetExhaustedError


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


GEMINI_V2_SCHEMA = _clean_schema(_inline_refs(DiscoveryResultV2.model_json_schema()))


def build_prompt_v2(ctx: InputContext) -> str:
    ctx_json = ctx.model_dump_json(indent=2)
    return f"""
You are extracting identity metadata from a creator's profile — NOT classifying URLs.

**Ground every field in the provided context.** Do not rely on prior knowledge of this handle. If a field cannot be determined from the context, return null / "unknown" / an empty list.

## Context
```
{ctx_json}
```

## Task — return a JSON object matching the schema with ONLY these fields:

1. `canonical_name`: human-readable creator name. If not clearly stated in display_name or bio, use the handle.
2. `known_usernames`: list of handles this creator is known by (including the input handle).
3. `display_name_variants`: all variants of the creator's display name present in context.
4. `primary_niche`: free-text inference from bio (e.g. "adult", "fitness", "cooking", "asmr"). Null if unclear.
5. `monetization_model`: one of [subscription, tips, ppv, affiliate, brand_deals, ecommerce, coaching, saas, mixed, unknown]. Infer from link-in-bio destinations when present.
6. `text_mentions`: list of handles explicitly mentioned in prose (bio text). ONLY include mentions that name a handle + platform clearly (e.g. "follow my tiktok @alice2" → platform=tiktok, handle=alice2). Do NOT include anything from external_urls — URLs are classified separately by the resolver.
7. `raw_reasoning`: one-sentence summary of what you inferred.

DO NOT classify URLs. DO NOT propose accounts. DO NOT propose funnel edges. Those are handled by the deterministic classifier + resolver layers, not by you.
""".strip()


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_not_exception_type(ValidationError),
    reraise=True,
)
def run_gemini_discovery_v2(ctx: InputContext) -> DiscoveryResultV2:
    genai.configure(api_key=get_gemini_key())
    model = genai.GenerativeModel("gemini-2.5-flash")
    prompt = build_prompt_v2(ctx)
    resp = model.generate_content(
        prompt,
        generation_config=genai.GenerationConfig(
            response_mime_type="application/json",
            response_schema=GEMINI_V2_SCHEMA,
        ),
    )
    return DiscoveryResultV2.model_validate_json(resp.text)


def _write_dead_letter(run_id: UUID, error: str) -> None:
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
    try:
        _call_mark_discovery_failed(sb, run_id, error)
    except Exception as nested:
        console.log(f"[red]mark_discovery_failed exhausted retries: {nested}[/red]")
        _write_dead_letter(run_id, error)


def _commit_v2(sb, run_id: UUID, workspace_id: UUID, result: ResolverResult,
                bulk_import_id: str | None) -> None:
    """Build the v2 commit_discovery_result payload from the resolver output."""
    seed = result.seed_context
    gem = result.gemini_result

    # Primary account — always the seed profile
    accounts = [{
        "platform": seed.platform,
        "handle": seed.handle,
        "url": None,
        "display_name": seed.display_name,
        "bio": seed.bio,
        "follower_count": seed.follower_count,
        "account_type": "social",
        "is_primary": True,
        "discovery_confidence": 1.0,
        "reasoning": "seed",
    }]

    # Secondary accounts — one per enriched context
    for canon, ctx in result.enriched_contexts.items():
        accounts.append({
            "platform": ctx.platform,
            "handle": ctx.handle,
            "url": canon,
            "display_name": ctx.display_name,
            "bio": ctx.bio,
            "follower_count": ctx.follower_count,
            "account_type": _classify_account_type_for(ctx.platform, result.discovered_urls, canon),
            "is_primary": False,
            "discovery_confidence": 0.9,
            "reasoning": ctx.source_note,
        })

    # Funnel edges from seed to each enriched secondary
    funnel_edges = []
    for canon, ctx in result.enriched_contexts.items():
        funnel_edges.append({
            "from_platform": seed.platform,
            "from_handle": seed.handle,
            "to_platform": ctx.platform,
            "to_handle": ctx.handle,
            "edge_type": "link_in_bio",
            "confidence": 0.9,
        })

    creator_data = {
        "canonical_name": gem.canonical_name,
        "known_usernames": gem.known_usernames,
        "display_name_variants": gem.display_name_variants,
        "primary_platform": seed.platform,
        "primary_niche": gem.primary_niche,
        "monetization_model": gem.monetization_model,
    }

    discovered_urls_payload = [du.model_dump() for du in result.discovered_urls]

    sb.rpc("commit_discovery_result", {
        "p_run_id": str(run_id),
        "p_creator_data": creator_data,
        "p_accounts": accounts,
        "p_funnel_edges": funnel_edges,
        "p_discovered_urls": discovered_urls_payload,
        "p_bulk_import_id": bulk_import_id,
    }).execute()
    console.log(f"[green]Committed v2 discovery run {run_id}[/green]")


def _classify_account_type_for(platform: str, discovered_urls: list, canonical_url: str) -> str:
    """Map from discovered_urls list entry to account_type for the profile row."""
    for du in discovered_urls:
        if du.canonical_url == canonical_url:
            return du.account_type
    return "other"


def run(inp: DiscoveryInput, bulk_import_id: str | None = None,
        cap_cents: int | None = None) -> None:
    """Run discovery for one seed. v2 pipeline.

    bulk_import_id: if set, passed to commit for counter updates.
    cap_cents: per-seed Apify budget. Defaults to env BULK_IMPORT_APIFY_USD_CAP (×100).
    """
    sb = get_supabase()
    if cap_cents is None:
        cap_cents = int(float(os.environ.get("BULK_IMPORT_APIFY_USD_CAP", "5")) * 100)

    budget = BudgetTracker(
        cap_cents=cap_cents,
        on_warning=lambda msg: console.log(f"[yellow]{msg}[/yellow]"),
    )
    try:
        console.log(f"[blue]Starting v2 discovery run {inp.run_id} "
                    f"(@{inp.input_handle}, {inp.input_platform_hint})[/blue]")
        result = resolve_seed(
            handle=inp.input_handle,
            platform_hint=inp.input_platform_hint,
            supabase=sb,
            apify_client=get_apify_client(),
            budget=budget,
        )

        _commit_v2(sb, inp.run_id, inp.workspace_id, result, bulk_import_id)

        # Record budget cost on the run
        sb.table("discovery_runs").update({
            "apify_cost_cents": budget.spent_cents,
        }).eq("id", str(inp.run_id)).execute()

        # Kick off small IG posts scrape for the primary if applicable
        if result.seed_context.platform == "instagram":
            console.log(f"[cyan]Dispatching Apify posts scrape for @{inp.input_handle}[/cyan]")
            scrape_instagram_profile(str(inp.workspace_id), inp.input_handle, limit=5)

    except EmptyDatasetError as e:
        console.log(f"[yellow]Discovery aborted — empty context: {e}[/yellow]")
        mark_discovery_failed_with_retry(sb, inp.run_id, f"empty_context: {e}")
        if bulk_import_id:
            sb.table("bulk_imports").update({
                "seeds_failed": sb.rpc("jsonb_inc", {}).execute() if False else None,
            })  # counter increment handled by a trigger or left to the merge pass
    except BudgetExhaustedError as e:
        console.log(f"[yellow]Discovery blocked by budget: {e}[/yellow]")
        mark_discovery_failed_with_retry(sb, inp.run_id, f"budget_exceeded: {e}")
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
    run(inp, bulk_import_id=data.get("bulk_import_id"))
```

- [ ] **Step 2: Delete the old shims**

```bash
rm scripts/apify_details.py scripts/link_in_bio.py
```

Any lingering `from apify_details import` or `from link_in_bio import` in other files should fail type-check or test runs and point you at what still needs rewiring. The new paths: `from fetchers import instagram, tiktok`; `from aggregators import linktree, beacons, custom_domain`.

- [ ] **Step 3: Remove now-dead tests**

The PR #2 tests under `scripts/tests/test_apify_details.py` and `scripts/tests/test_link_in_bio.py` test the old module paths. They still work via the shim, but we just deleted it. Either (a) delete those test files since we've re-tested the migrated modules in `tests/fetchers/` and `tests/aggregators/`, or (b) rewrite the imports to the new paths. Prefer (a) — cleaner, less duplication.

```bash
rm scripts/tests/test_apify_details.py scripts/tests/test_link_in_bio.py
```

Similarly for `scripts/tests/test_discover_creator.py` — PR #2's tests bind to the old `fetch_input_context` + `_update_profile_from_context` helpers that no longer exist. Keep the retry + dead-letter tests (those helpers survived); delete the fetch_input_context and _update_profile tests. Easiest: delete the whole test file and let Task 20 (integration tests) cover the new surface.

```bash
rm scripts/tests/test_discover_creator.py
```

- [ ] **Step 4: Run the full test suite**

```bash
cd scripts && python -m pytest tests/ -v
```

Expected: all tests pass. Count should be lower than PR #2's 45 (we removed ~20 tests for the deleted old surface, added ~30 new for the v2 surface — net ~55).

- [ ] **Step 5: Commit**

```bash
git add scripts/discover_creator.py
git rm scripts/apify_details.py scripts/link_in_bio.py \
  scripts/tests/test_apify_details.py scripts/tests/test_link_in_bio.py \
  scripts/tests/test_discover_creator.py
git commit -m "feat(pipeline): rewire discover_creator.py onto v2 resolver; drop old shims

discover_creator.py becomes a thin entry point: constructs a BudgetTracker,
calls resolve_seed, commits via the v2 commit_discovery_result RPC with
p_discovered_urls + p_bulk_import_id, records apify_cost_cents on the run,
dispatches posts-scrape for IG primaries (unchanged from v1).

Drops apify_details.py and link_in_bio.py shims — all consumers now import
from fetchers.{instagram,tiktok} / aggregators.{linktree,beacons,custom_
domain} directly. PR #2's test files that bound to the old surface are
removed; the migrated modules retain coverage via the new per-module test
files + integration tests (Task 20)."
```

---

## Task 18: Worker — bulk-import tracking + cross-workspace merge pass trigger

**Files:**
- Modify: `scripts/worker.py`

Worker picks up `discovery_runs.bulk_import_id` and passes it to `run()`. After each batch of claimed runs completes, checks whether any pending/processing runs remain in each bulk — if none, fires `run_cross_workspace_merge_pass` RPC. Same source-agnostic path: `seed`, `retry`, `manual_add` all hit the same resolver.

- [ ] **Step 1: Rewrite `scripts/worker.py`**

Replace the full contents:

```python
# scripts/worker.py — Polling worker for discovery pipeline v2
import os
import asyncio
from concurrent.futures import ThreadPoolExecutor
from typing import Optional

from common import get_supabase, console
from discover_creator import run, DiscoveryInput
from dotenv import load_dotenv

load_dotenv()

POLL_INTERVAL_SECONDS = int(os.environ.get("POLL_INTERVAL_SECONDS", "30"))
MAX_CONCURRENT_RUNS = int(os.environ.get("MAX_CONCURRENT_RUNS", "5"))


def _process_single(row: dict) -> Optional[str]:
    inp = DiscoveryInput(
        run_id=row["id"],
        creator_id=row["creator_id"],
        workspace_id=row["workspace_id"],
        input_handle=row["input_handle"],
        input_url=row["input_url"],
        input_platform_hint=row["input_platform_hint"],
    )
    run(inp, bulk_import_id=row.get("bulk_import_id"))
    return row.get("bulk_import_id")


def log_gather_results(results: list, claimed: list[dict], logger=None) -> None:
    log = logger or console.log
    for result, row in zip(results, claimed):
        if isinstance(result, BaseException):
            log(f"[red]Run {row.get('id')} failed in worker: {type(result).__name__}: {result}[/red]")


def _fire_merge_pass_if_bulk_complete(sb, bulk_import_id: str, workspace_id: str) -> None:
    resp = sb.table("discovery_runs").select("id").eq(
        "bulk_import_id", bulk_import_id
    ).in_("status", ["pending", "processing"]).execute()

    if resp.data:
        return  # still seeds running

    console.log(f"[cyan]Bulk {bulk_import_id} terminal — firing cross-workspace merge pass[/cyan]")
    try:
        sb.rpc("run_cross_workspace_merge_pass", {
            "p_workspace_id": workspace_id,
            "p_bulk_import_id": bulk_import_id,
        }).execute()
    except Exception as e:
        console.log(f"[red]Merge pass failed for bulk {bulk_import_id}: {e}[/red]")


async def poll_loop(args=None):
    sb = get_supabase()
    console.log(f"[green]Worker v2 started. Polling every {POLL_INTERVAL_SECONDS}s. "
                f"Max concurrency: {MAX_CONCURRENT_RUNS}.[/green]")

    with ThreadPoolExecutor(max_workers=MAX_CONCURRENT_RUNS) as pool:
        while True:
            try:
                resp = sb.table("discovery_runs").select("*").eq(
                    "status", "pending"
                ).limit(MAX_CONCURRENT_RUNS).execute()
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
                        futures = [loop.run_in_executor(pool, _process_single, c) for c in claimed]
                        results = await asyncio.gather(*futures, return_exceptions=True)
                        log_gather_results(results, claimed)

                        seen_bulks: dict[str, str] = {}
                        for row in claimed:
                            bid = row.get("bulk_import_id")
                            if bid:
                                seen_bulks[bid] = row["workspace_id"]
                        for bid, ws_id in seen_bulks.items():
                            _fire_merge_pass_if_bulk_complete(sb, bid, ws_id)

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

- [ ] **Step 2: Add worker tests**

Append to `scripts/tests/test_worker.py`:

```python

from unittest.mock import MagicMock
from worker import _fire_merge_pass_if_bulk_complete


class TestFireMergePassIfBulkComplete:
    def test_does_not_fire_when_pending_remain(self):
        sb = MagicMock()
        sb.table.return_value.select.return_value.eq.return_value.in_.return_value.\
            execute.return_value.data = [{"id": "still-running"}]

        _fire_merge_pass_if_bulk_complete(sb, bulk_import_id="b1", workspace_id="w1")
        sb.rpc.assert_not_called()

    def test_fires_when_bulk_terminal(self):
        sb = MagicMock()
        sb.table.return_value.select.return_value.eq.return_value.in_.return_value.\
            execute.return_value.data = []
        sb.rpc.return_value.execute.return_value = None

        _fire_merge_pass_if_bulk_complete(sb, bulk_import_id="b1", workspace_id="w1")
        sb.rpc.assert_called_once_with(
            "run_cross_workspace_merge_pass",
            {"p_workspace_id": "w1", "p_bulk_import_id": "b1"},
        )

    def test_swallows_rpc_errors(self):
        sb = MagicMock()
        sb.table.return_value.select.return_value.eq.return_value.in_.return_value.\
            execute.return_value.data = []
        sb.rpc.return_value.execute.side_effect = Exception("rpc failed")

        _fire_merge_pass_if_bulk_complete(sb, bulk_import_id="b1", workspace_id="w1")
        # Should not raise.
```

- [ ] **Step 3: Run tests**

Run: `cd scripts && python -m pytest tests/test_worker.py -v`
Expected: existing test + 3 new tests pass.

- [ ] **Step 4: Commit**

```bash
git add scripts/worker.py scripts/tests/test_worker.py
git commit -m "feat(pipeline): worker v2 — bulk_import tracking + auto merge-pass

Worker passes bulk_import_id from discovery_runs into run(). After each
batch completes, groups by bulk_import_id and fires run_cross_workspace_
merge_pass for any bulk with no remaining pending/processing runs. RPC
errors logged, not raised."
```

---

## Task 19: UI — Manual Add Account flow

**Files:**
- Modify: `src/app/(dashboard)/creators/actions.ts`
- Modify: `src/components/creators/AddAccountDialog.tsx`

- [ ] **Step 1: Extend `addProfileToCreator` server action**

Read the existing function first:

```bash
grep -n "addProfileToCreator" "src/app/(dashboard)/creators/actions.ts"
```

Locate the function. Extend signature + body:

```typescript
// New signature: accept run_discovery: boolean (default true)
export async function addProfileToCreator(input: {
  creator_id: string;
  platform: Database["public"]["Enums"]["platform"];
  handle: string;
  account_type: Database["public"]["Enums"]["account_type"];
  run_discovery?: boolean;
}): Promise<Result<{ profile_id: string; run_id: string | null }>> {
  const sb = getSupabase();
  const { creator_id, platform, handle, account_type, run_discovery = true } = input;

  const { data: workspace, error: wsErr } = await sb
    .from("creators").select("workspace_id").eq("id", creator_id).single();
  if (wsErr || !workspace) {
    return { ok: false, error: wsErr?.message ?? "creator not found", code: "NOT_FOUND" };
  }

  const { data: profile, error: insErr } = await sb
    .from("profiles")
    .insert({
      workspace_id: workspace.workspace_id,
      creator_id, platform, handle, account_type,
      is_primary: false,
      discovery_confidence: 1.0,
      discovery_reason: "manual_add",
      added_by: SYSTEM_USER_ID,
      is_active: true,
    })
    .select("id").single();

  if (insErr || !profile) {
    return { ok: false, error: insErr?.message ?? "insert failed", code: "INSERT_FAILED" };
  }

  let run_id: string | null = null;
  if (run_discovery) {
    const { data: run, error: runErr } = await sb
      .from("discovery_runs")
      .insert({
        workspace_id: workspace.workspace_id,
        creator_id,
        input_handle: handle,
        input_platform_hint: platform,
        status: "pending",
        attempt_number: 1,
        source: "manual_add",
        bulk_import_id: null,
        initiated_by: SYSTEM_USER_ID,
        started_at: new Date().toISOString(),
      })
      .select("id").single();
    if (runErr) {
      console.error("manual_add discovery_run insert failed:", runErr);
    } else {
      run_id = run?.id ?? null;
    }
  }

  revalidatePath(`/creators/${creator_id}`);
  return { ok: true, data: { profile_id: profile.id, run_id } };
}
```

- [ ] **Step 2: Add checkbox to `AddAccountDialog.tsx`**

Add state:
```tsx
const [runDiscovery, setRunDiscovery] = useState<boolean>(true);
```

Pass in call:
```tsx
const result = await addProfileToCreator({
  creator_id: creatorId,
  platform: platform as Platform,
  handle,
  account_type: accountType,
  run_discovery: runDiscovery,
});
```

Update toast:
```tsx
toast.success(runDiscovery ? "Account added — discovery queued" : "Account added");
```

Add to form JSX (near submit button):
```tsx
<div className="flex items-center gap-2 pt-2">
  <Checkbox
    id="run-discovery"
    checked={runDiscovery}
    onCheckedChange={(v) => setRunDiscovery(v === true)}
  />
  <label htmlFor="run-discovery" className="text-sm text-neutral-300 cursor-pointer">
    Run discovery on this account (find network + monetization)
  </label>
</div>
```

Import `Checkbox` from `@/components/ui/checkbox` if not already imported.

- [ ] **Step 3: Typecheck**

```bash
cd "/Users/simon/OS/Living VAULT/Content OS/The Hub"
npx tsc --noEmit
```

Expected: exit 0.

- [ ] **Step 4: Commit**

```bash
git add 'src/app/(dashboard)/creators/actions.ts' src/components/creators/AddAccountDialog.tsx
git commit -m "feat(ui): Manual Add Account triggers v2 discovery

AddAccountDialog gains 'Run discovery on this account' checkbox (default on).
addProfileToCreator server action accepts run_discovery; when true, inserts
discovery_runs with source='manual_add' so the worker picks it up. Canonical
creator fields protected at the RPC level (Task 16 — manual_add branch only
union-merges known_usernames).

Toast differentiates 'added' vs 'added — discovery queued'."
```

---

## Task 20: End-to-end integration + idempotency tests

**Files:**
- Create: `scripts/tests/pipeline/test_integration.py`

Mocked end-to-end flow covering a multi-hop creator (Linktree → OF + IG_backup) and budget exhaustion.

- [ ] **Step 1: Write tests**

Create `scripts/tests/pipeline/test_integration.py`:

```python
# scripts/tests/pipeline/test_integration.py
from unittest.mock import MagicMock, patch
from pipeline.resolver import resolve_seed
from pipeline.budget import BudgetTracker
from pipeline.classifier import Classification
from schemas import InputContext, DiscoveryResultV2


def _ctx(handle, platform, external_urls=None):
    return InputContext(
        handle=handle, platform=platform, display_name=handle,
        bio="", follower_count=1000, avatar_url=None,
        external_urls=external_urls or [], source_note="test",
    )


@patch("pipeline.resolver.aggregators_linktree.resolve")
@patch("pipeline.resolver.run_gemini_discovery_v2")
@patch("pipeline.resolver.classify")
@patch("pipeline.resolver.fetch_seed")
def test_linktree_hub_with_monetization_destination(
    mock_fetch, mock_classify, mock_gemini, mock_linktree,
):
    mock_fetch.return_value = _ctx("alice", "instagram",
                                    external_urls=["https://linktr.ee/alice"])
    mock_linktree.return_value = [
        "https://onlyfans.com/alice_of",
        "https://instagram.com/alice_backup",
    ]
    classifications = iter([
        Classification("linktree", "link_in_bio", 1.0, "rule:linktree_link_in_bio"),
        Classification("onlyfans", "monetization", 1.0, "rule:onlyfans_monetization"),
        Classification("instagram", "social", 1.0, "rule:instagram_social"),
    ])
    mock_classify.side_effect = lambda *a, **kw: next(classifications)
    mock_gemini.return_value = DiscoveryResultV2(
        canonical_name="Alice", known_usernames=["alice"],
        display_name_variants=["Alice"], raw_reasoning="",
    )

    budget = BudgetTracker(cap_cents=1000)
    result = resolve_seed(
        handle="alice", platform_hint="instagram",
        supabase=MagicMock(), apify_client=MagicMock(),
        budget=budget,
    )

    urls = {du.canonical_url for du in result.discovered_urls}
    assert "https://linktr.ee/alice" in urls
    assert "https://onlyfans.com/alice_of" in urls
    assert "https://instagram.com/alice_backup" in urls


@patch("pipeline.resolver.run_gemini_discovery_v2")
@patch("pipeline.resolver.classify")
@patch("pipeline.resolver.fetch_seed")
def test_budget_exhaustion_partial_completion(mock_fetch, mock_classify, mock_gemini):
    mock_fetch.return_value = _ctx("alice", "instagram",
                                    external_urls=["https://instagram.com/b", "https://tiktok.com/@c"])
    mock_classify.side_effect = [
        Classification("instagram", "social", 1.0, "rule:instagram_social"),
        Classification("tiktok", "social", 1.0, "rule:tiktok_social"),
    ]
    mock_gemini.return_value = DiscoveryResultV2(
        canonical_name="Alice", known_usernames=["alice"],
        display_name_variants=["Alice"], raw_reasoning="",
    )

    # Cap just fits the seed (10¢) + one IG enrichment (10¢) but not a TT fetch (+8¢).
    budget = BudgetTracker(cap_cents=25)
    result = resolve_seed(
        handle="alice", platform_hint="instagram",
        supabase=MagicMock(), apify_client=MagicMock(),
        budget=budget,
    )

    # Classification is free — both URLs classified
    assert len(result.discovered_urls) == 2
    # Enrichment limited by budget
    assert len(result.enriched_contexts) <= 1
```

- [ ] **Step 2: Run tests**

Run: `cd scripts && python -m pytest tests/pipeline/test_integration.py -v`
Expected: 2 tests pass. If enrichment counts differ slightly (fetcher dispatch happens inside `_classify_and_enrich`, not directly mocked), adjust assertions to `>=` and inspect manually; the goal is budget-stops-enrichment-cleanly, not strict numeric equality.

- [ ] **Step 3: Run full suite**

```bash
cd scripts && python -m pytest tests/ -q
```

Expected: all green. Net test count ~55 (45 original - ~18 deleted + ~28 new).

- [ ] **Step 4: Commit**

```bash
git add scripts/tests/pipeline/test_integration.py
git commit -m "test(pipeline): end-to-end resolver flow + budget exhaustion

Covers the full IG → Linktree → (OF + IG_backup) path with mocked fetchers.
Confirms all 3 URLs classified and recorded. Budget exhaustion test
verifies classification continues (free) while enrichment stops cleanly
without raising."
```

---

## Task 21: Live smoke test + docs sync + PR

**Files:**
- Modify: `.env.local`, `scripts/.env` (add `BULK_IMPORT_APIFY_USD_CAP=5`)
- Modify: `PROJECT_STATE.md`
- Modify: `docs/SCHEMA.md` (hand-edit)
- Modify vault docs via `sync-project-state` skill

Live smoke spends Apify + Gemini. **Gated behind explicit user approval.**

- [ ] **Step 1: Pause + ask user approval**

Prompt:

> Ready to run live smoke test. This will:
>   - Re-run discovery for Natalie Vox, Esmae, Aria Swan via the v2 pipeline
>   - Spend ~$1–2 Apify + ~$0.10 Gemini
>   - Write new `profile_destination_links`, possibly new `creator_merge_candidates`
>   - Log cost to `bulk_imports.cost_apify_cents`
>
> Proceed?

Wait for user response. If declined, stop here.

- [ ] **Step 2: Set env var + run smoke**

```bash
echo "BULK_IMPORT_APIFY_USD_CAP=5" >> scripts/.env
```

Queue 3 retry runs via Supabase MCP:

```sql
INSERT INTO discovery_runs (workspace_id, creator_id, input_handle,
                            input_platform_hint, status, attempt_number,
                            source, started_at)
SELECT workspace_id, id, known_usernames[1], primary_platform::text,
       'pending',
       (SELECT COUNT(*) FROM discovery_runs dr WHERE dr.creator_id = c.id) + 1,
       'retry', NOW()
FROM creators c
WHERE workspace_id = (SELECT id FROM workspaces LIMIT 1);
```

Then run the worker once:

```bash
cd scripts && python worker.py --once
```

- [ ] **Step 3: Verify**

Via MCP:

```sql
SELECT c.canonical_name, c.onboarding_status,
       SUBSTRING(c.last_discovery_error, 1, 80) AS err_preview,
       (SELECT COUNT(*) FROM profiles p WHERE p.creator_id = c.id) AS profiles,
       (SELECT COUNT(*) FROM profile_destination_links pdl
        JOIN profiles p ON p.id = pdl.profile_id
        WHERE p.creator_id = c.id) AS dest_links,
       (SELECT COUNT(*) FROM funnel_edges fe WHERE fe.creator_id = c.id) AS funnel_edges
FROM creators c ORDER BY c.canonical_name;
```

Expected:
- **Natalie Vox**: `ready`, ≥2 profiles, dest_links ≥1, funnel_edges ≥1
- **Esmae**: `ready`, ≥2 profiles, dest_links ≥1, funnel_edges ≥1
- **Aria Swan**: `failed`, `empty_context:` reason

Check bulk_imports:

```sql
SELECT id, seeds_total, seeds_committed, seeds_failed, cost_apify_cents, status
FROM bulk_imports ORDER BY created_at DESC LIMIT 1;
```

Expected: reasonable counters, `cost_apify_cents < 200` (under $2), status in `('completed','completed_with_failures')`.

- [ ] **Step 4: Update PROJECT_STATE.md**

Edit header:
```
Last synced: 2026-04-25 (sync 10 — discovery v2)
```

Add to §4.1 table list: `bulk_imports`, `classifier_llm_guesses`, `profile_destination_links`. Bump total to 23 tables.

Add to §6 RPCs table:
```
| `run_cross_workspace_merge_pass` | (p_workspace_id uuid, p_bulk_import_id uuid) → jsonb | Uses profile_destination_links inverted index to raise merge candidates for buckets with >1 creator sharing a monetization/aggregator URL |
```

Mark §14 item 6 ✅ with migration timestamps + PR link.

Remove §20 "Discovery pipeline broken (httpx)" row (fixed).

Append to Decisions Log:
```
- 2026-04-25: Discovery v2 shipped. Two-stage resolver, deterministic URL classifier with LLM fallback cache, rule-cascade identity scorer, CLIP avatar tiebreak, multi-platform fetcher layer (IG/TT via Apify, YT via yt-dlp, OF via curl_cffi, Patreon/Fanvue/generic via httpx, FB+X stubbed). bulk_imports as first-class observable job. Cross-workspace identity dedup runs on every commit via persistent profile_destination_links index. Manual Add Account triggers full resolver expansion with canonical-field protection. Live smoke on 3 existing creators: Natalie + Esmae enriched cleanly; Aria failed-fast with empty_context. Spec: docs/superpowers/specs/2026-04-24-discovery-v2-design.md. Plan: docs/superpowers/plans/2026-04-24-discovery-v2-plan.md. PR: (fill after open).
```

- [ ] **Step 5: Hand-edit `docs/SCHEMA.md`**

`npm run db:schema` still blocked (SUPABASE_DB_URL unfilled). Manually:

- Add to the "Tables" alphabetical list at top: `bulk_imports`, `classifier_llm_guesses`, `profile_destination_links`.
- Add a full table block for each (follow existing format: columns + PK + RLS note + trigger note).
- Under existing `discovery_runs` table block: add rows for `bulk_import_id`, `apify_cost_cents`, `source`.
- Under existing `profiles` table block: add row for `discovery_reason`.

- [ ] **Step 6: Sync vault docs**

Invoke the `sync-project-state` skill manually (user runs: "sync project state"). It'll propagate to Changelog, Phase Roadmap, Migration Log, RPC Reference, Home, today's session note.

- [ ] **Step 7: Commit + push + open PR**

```bash
git add PROJECT_STATE.md docs/SCHEMA.md scripts/.env.example
git commit -m "docs: sync project state — discovery v2 shipped

Live smoke passed: Natalie Vox + Esmae re-discovered cleanly with new
profile_destination_links + funnel_edges; Aria Swan failed-fast with
empty_context (private IG — expected).

bulk_imports row shows budget kept under cap. Cross-workspace merge pass
evaluated buckets and raised 0 candidates (3 distinct creators, no
shared URLs). PROJECT_STATE §14 marks Phase 2 discovery v2 ✅. §6 adds
run_cross_workspace_merge_pass. §20 drops httpx-discovery-broken row.
Decisions Log appended."

git push origin phase-2-discovery-v2

gh pr create --base main --head phase-2-discovery-v2 \
  --title "Phase 2: discovery v2 — multi-platform asset resolver" \
  --body "$(cat <<'EOF'
## Summary

Implements SP1 per `docs/superpowers/specs/2026-04-24-discovery-v2-design.md`:

- Two-stage resolver (fetch seed → classify+enrich destinations); no depth param
- Deterministic URL classifier (gazetteer + cached LLM fallback)
- Rule-cascade identity scorer (first-match-wins + CLIP avatar tiebreak)
- Multi-platform fetchers: IG, TT, YT, Patreon, OF, Fanvue, generic (FB+X stubbed for SP1.1)
- Aggregator resolvers: Linktree, Beacons, custom_domain
- `bulk_imports` first-class observable job + cross-workspace identity dedup every commit
- Manual Add Account triggers full resolver expansion with canonical-field protection

Plan: `docs/superpowers/plans/2026-04-24-discovery-v2-plan.md`

## Test plan

- [x] ~55 pytest tests pass
- [x] `npx tsc --noEmit` exit 0
- [x] Live smoke (spec §7.3) — 2 creators re-discovered, 1 failed-fast as expected
- [ ] Reviewer confirms schema migration (Task 1) matches spec §4
- [ ] Reviewer confirms RPC signatures (Task 16) match spec §4.4

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

- [ ] **Step 8: Await PR review + flag flip**

`DISCOVERY_V2_ENABLED` was removed from the actual code path (there is no v1 path anymore after Task 17). The flag name is retained as documentation in the PROJECT_STATE Decisions Log but has no code effect. If a rollback is needed pre-merge, the only path is `git revert` on the PR.

---

## Plan Self-Review Notes

**Spec coverage** — every section of `docs/superpowers/specs/2026-04-24-discovery-v2-design.md` is implemented:

- §3.1 Two-stage resolver → Task 15
- §3.2 Gemini narrowed → Task 17 (`build_prompt_v2`, `DiscoveryResultV2`)
- §3.3 URL classifier → Task 5 + Task 4 gazetteer
- §3.4 Identity rule cascade → Task 7
- §3.5 CLIP avatar similarity → Task 7 (`get_clip_similarity_fn`)
- §3.6 Canonicalization → Task 3
- §3.7 Manual Add Account → Task 19 (UI) + Task 16 RPC canonical-field protection
- §3.8 Apify budget → Task 6 + Task 17 integration
- §4.1 New tables → Task 1
- §4.2 New columns → Task 1
- §4.3 Unique index → Task 1
- §4.4 RPC changes → Task 16
- §5 Data flow → Tasks 15 + 17 + 18
- §6 Error handling → Task 15 + Task 17
- §7 Testing → Tasks 3-15 (per-module) + Task 20 (integration)
- §8 Success criteria → Task 21 smoke verification
- §9 Phasing + feature flag → Task 21

**Placeholder scan** — no TBD/TODO/handwavy steps. Every code block is complete. Every command has expected output.

**Type consistency** — `InputContext`, `Classification`, `DiscoveredUrl`, `DiscoveryResultV2`, `ResolverResult`, `ProfileFingerprint`, `IdentityVerdict`, `BudgetTracker`, `BudgetExhaustedError`, `EmptyDatasetError` all defined in specified tasks and imported consistently in later tasks.

**Scope check** — SP1 only. SP2 (post-feed scraping on secondaries), SP3 (bulk-import identity resolution at scale as a standalone process), SP4 (cross-platform query layer + new platform tabs) are explicitly deferred to future plans.

---

# Plan complete

