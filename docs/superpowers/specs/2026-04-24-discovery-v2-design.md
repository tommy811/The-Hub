# Discovery v2 — Multi-Platform Asset Resolver

**Status:** Design
**Date:** 2026-04-24
**Scope:** SP1 of the Discovery Rebuild series
**Successor to:** `docs/superpowers/plans/2026-04-24-discovery-pipeline-rebuild.md` (PR #2, now merged)
**Depends on:** Phase 2 schema migration (PR #3, merged — `trends`, `creator_label_assignments`, `archetype`/`vibe` on creators, `edge_type` enum)

---

## 1. Goal

Given one social handle, produce a full map of the creator's digital footprint — every owned account, every monetization destination, every aggregator page, every funnel edge between them — and write it to the database with a confidence-scored identity graph.

Given a bulk import of N seeds, dedup the discovered assets across seeds so creators who own multiple platforms show up as one creator, not N.

Current pipeline (post PR #2) does single-hop Apify fetch + Gemini classification. That's a narrow subset of what's needed. This spec replaces it with a two-stage resolver + deterministic classifier + rule-cascade identity scorer + multi-platform fetcher layer.

## 2. Non-goals

SP1 does **not** cover:

- Scraping post feeds on discovered profiles (that's SP2 — secondary profile enrichment). SP1 enriches with bio + follower_count + avatar + external_urls only.
- Cross-platform creator queries in the UI ("show me all creators with FB in their funnel") — that's SP4.
- The funnel flow chart UI — that's Phase 4 per PROJECT_STATE §14.
- Face embeddings, posting-time correlation as identity signals.
- Paid Twitter API fallback.
- Retry/replay UI for failed bulk imports (the API layer supports it; UI is deferred).

## 3. Architecture

```
pipeline/
  resolver.py       -- two-stage expansion (fetch seed → classify + enrich destinations)
  classifier.py     -- URL → (platform, account_type), rule-first with LLM fallback
  identity.py       -- rule cascade + index-inverted dedup + CLIP tiebreak
  canonicalize.py   -- URL canonicalization (strip utm, resolve short URLs, etc.)
  budget.py         -- per-bulk-import Apify cost tracker with hard cap

fetchers/            -- platform-specific profile fetchers, uniform InputContext shape
  base.py           -- abstract fetcher + InputContext dataclass
  instagram.py      -- Apify (apify/instagram-scraper, details mode) — migrated from apify_details.py
  tiktok.py         -- Apify (clockworks/tiktok-scraper) — migrated from apify_details.py
  youtube.py        -- yt-dlp --flat-playlist (no API key needed)
  patreon.py        -- httpx (public landing page)
  onlyfans.py       -- curl_cffi (JA3/TLS-impersonation; raw httpx blocked)
  fanvue.py         -- httpx
  facebook.py       -- stub in SP1 (logs + returns empty; Apify actor added in SP1.1)
  twitter.py        -- stub in SP1 (same)
  generic.py        -- httpx fallback for unclassified profiles (bio via <meta> scrape)

aggregators/         -- link-in-bio resolvers (split from existing link_in_bio.py)
  linktree.py
  beacons.py
  custom_domain.py  -- redirect chain follower + outbound link extraction

tests/               -- mirrors structure above; fixtures under tests/fixtures/
```

### 3.1 Two-stage resolver

Not a BFS. Not depth-parametric. It is structurally two stages and always exactly two stages:

- **Stage A** — fetch the seed via the appropriate platform fetcher. Produces `InputContext(bio, follower_count, avatar_url, display_name, external_urls[], posts_peek[])`.
- **Stage B** — for each URL in `external_urls`: canonicalize, classify, and branch:
  - **Aggregator** (Linktree / Beacons / custom_domain) → fetch the aggregator page, extract outbound links, classify each, enrich any that are profiles. Aggregator children are "free" — they do not count against a budget that caps at the URL level. They do count against the Apify $ budget when enrichment fires.
  - **Profile** (IG / TT / YT / Patreon / OF / Fanvue) → enrich via the platform fetcher. Produces a second-level `InputContext`.
  - **Monetization non-profile** (TikTok Shop, Amazon storefront, custom_domain monetization) → record URL + classification. No enrichment (nothing profile-shaped to enrich).
  - **Unknown** → fall through to LLM classifier, record in `classifier_llm_guesses`, no enrichment.

There is no Stage C. Aggregator destinations do not chain into further aggregator expansions — if a Linktree page links to another Linktree page, the second page is recorded but not expanded. This is a structural rule that prevents the "depth 3 via aggregator chaining" trap the external research flagged.

### 3.2 Gemini's role (narrowed)

Gemini is stripped of URL classification. Its new job is:

- **Canonicalization**: `canonical_name`, `known_usernames[]`, `display_name_variants[]`
- **Niche inference**: `primary_niche` (free text)
- **Monetization model inference**: `monetization_model` enum
- **Text-only handle mentions**: extract `text_mentions: [{platform, handle}]` from the seed's bio — accounts named in prose without a URL (e.g., "follow my backup at @esmae2"). Each text mention is constructed into a URL (`https://{platform}.com/{handle}`) and fed back into Stage B exactly once per seed (no further recursion from text mentions).

Gemini no longer touches `edge_type`, `account_type`, or `platform`. Those are classifier territory.

### 3.3 URL classifier (rule-first)

Pure function: `canonical_url → (platform, account_type, reason) | None`.

- **Gazetteer** seeded from [WhatsMyName](https://github.com/WebBreacher/WhatsMyName) (community-maintained JSON, ~600 sites with category tags) + hand-curated `monetization_overlay.yaml` marking our specific monetization set (OF, Fanvue, Fanplace, Patreon, amazon.com/shop, tiktok.com/@.../shop, gumroad.com, stan.store, coaching.{com|co}, etc.).
- **~15 primary rules** for the platforms we actively support, each returning `(platform, account_type, reason='rule:{name}')`.
- **LLM fallback** only when no rule matches. Returns `(platform, account_type, confidence)` and writes to `classifier_llm_guesses(canonical_url, platform_guess, account_type_guess, confidence, model_version)`. The classifier function returns the guess only if `confidence >= 0.7`; otherwise returns `(platform='other', account_type='other', reason='llm:low_confidence')`.
- **Cache**: LLM guesses are cached on the canonicalized URL forever (unlikely to re-classify a URL into a different category). Rules always win over cache — rule changes take precedence.

### 3.4 Identity scorer — rule cascade, not weighted sum

Runs at three points:
- **(a) intra-seed**: within one seed's discovered profiles (catches internal inconsistencies — rare but possible if Gemini's `text_mentions` duplicates a URL the resolver already found).
- **(b) within-bulk**: across all seeds in a single bulk import, after they commit.
- **(c) cross-workspace (every commit)**: whenever a new profile is committed to the workspace — whether from a seed, a bulk import, a manual Add Account, or a re-run — the scorer checks the new profile's `profile_destination_links` against the workspace's full existing index. This is the "late-arriving evidence" case: Creator A was imported last week with a partial footprint; Creator B is imported today and their Linktree shares a destination with A; the system raises a merge candidate (or auto-merges on strong signals) linking the new profile into A's existing creator record. The `profile_destination_links` index is a **persistent, per-workspace query structure** — it doesn't exist only during a bulk import.

Rules evaluated in strict order; first match wins:

| # | Rule | Signal | Action | Reason stored |
|---|---|---|---|---|
| 1 | Shared monetization destination | Both profiles point to the same `onlyfans.com/X`, `patreon.com/X`, `fanvue.com/X`, `gumroad.com/X` | **Auto-merge** | `shared_monetization_handle: X on {platform}` |
| 2 | Shared aggregator page URL | Both point to same `linktr.ee/X`, `beacons.ai/X`, same custom-domain with identical destination list | **Auto-merge** | `shared_aggregator_url: X` |
| 3 | Bio cross-mention | Profile A's bio contains Profile B's canonical handle or URL, OR vice versa (regex-matched, normalized) | **Raise merge candidate (0.8)** | `bio_cross_mention: {direction}` |
| 4 | Handle exact match + CLIP similarity ≥ 0.85 | Same normalized handle on different platforms AND CLIP avatar cosine ≥ 0.85 | **Raise merge candidate (0.7)** | `handle_match + clip_similarity: X` |
| 5 | Display name normalized equality + same primary_niche | Normalized display names match + Gemini niche output matches | **Raise merge candidate (0.5)** — only if `>= 2` other signals fire in pairing evidence | `display_name + niche_match` |
| — | Handle exact match alone | Cross-platform handle match with no other signal | **Discard** (too noisy — "@alex" is not rare) | not stored |
| — | Shared affiliate domain | Both profiles link to `amazon.com` root, `gymshark.com`, similar | **Discard** (not evidence — affiliate links are shared by thousands) | not stored |

Each merge/candidate records `evidence` JSONB with the reason string and the raw signal values, so humans reviewing can see exactly why.

**Index-inverted dedup** works the same way for all three contexts. `profile_destination_links` is a materialized index (see §4.1). When a new profile is committed:

1. Its canonical destination URLs are written to `profile_destination_links`.
2. A `SELECT` on each URL returns all other `profile_id`s that share it.
3. Any URL with ≥1 prior profile forms a candidate bucket (with the new profile + prior matches).
4. Rule cascade fires per bucket; expensive per-pair work (CLIP similarity, name fuzzy match) runs only inside buckets.

Result: intra-seed, within-bulk, and cross-workspace dedup all use the same machinery. O(1) index lookup per URL per new profile. Pairwise work stays bounded by bucket size (empirically k ≤ 3 for real creators).

**Merge action semantics** when a strong-signal match fires:

- **Both profiles are newly discovered (within a bulk import)** → the cascade raises a `creator_merge_candidate(a, b)` (ordered so `a < b`). Auto-merge at confidence 1.0 calls `merge_creators(keep=a, merge=b)` internally.
- **New profile matches an existing creator** (cross-workspace case) → cascade raises `creator_merge_candidate(existing_creator, new_creator)`. Auto-merge at confidence 1.0 calls `merge_creators(keep=existing_creator, merge=new_creator)` — preserves the older canonical creator, migrates the new profile + any new funnel_edges + new `known_usernames[]` onto it, archives the transient new creator row.
- **Below 1.0** → the candidate surfaces in the existing merge-review UI for human confirmation. No silent merges on weak signals.

### 3.5 CLIP avatar similarity

- Model: `sentence-transformers/clip-ViT-B-32` (~150MB, CPU).
- Distance: cosine similarity on embeddings of the 224×224 center-cropped avatar.
- Threshold: 0.85 (empirically strong — not published for creator avatars specifically, so tune after first batch of labeled merges).
- Only invoked as a tiebreak inside a candidate bucket, so per-bulk-import CLIP calls stay in the tens, not thousands.

### 3.6 Canonicalization

Every URL entering the pipeline is canonicalized first:

- Lowercase the host
- Strip `utm_*`, `fbclid`, `gclid`, `igshid`, `ref`, `ref_src` query params
- Strip trailing `/`, `/about`, `/home` for known-platform hosts
- Resolve short URLs via `HEAD` redirect chain (bit.ly, geni.us, smart.link, lnk.to, tinyurl, t.co, goo.gl, ow.ly). Cap at 5 redirects.
- Normalize `www.` prefix (drop)
- Protocol coerced to `https://`

Canonicalization is idempotent and its output is the key for both the classifier cache and the identity indices. If we canonicalize incorrectly, we build duplicates. Tested with ~30 fixture URLs covering each rule.

### 3.7 Manual Add Account flow

A creator's full footprint will never be fully automated on the first pass. The team needs a way to add a known account manually when they spot one (e.g., a new OF URL in a DM, a backup IG the creator mentioned) — and the system should treat that manual addition exactly like a mini-discovery seed so the rest of the newly visible network (whatever that account's bio and link-in-bio reveal) gets picked up too.

**UI**: The existing `AddAccountDialog.tsx` (Phase 1) stays in place. It adds one field:

- `[x] Run discovery on this account after adding` — default on. When checked, the server action enqueues enrichment + resolver expansion. When unchecked, it inserts a URL-only stub (same as today's behavior).

**Server action**: `addProfileToCreator(creator_id, platform, handle, account_type, run_discovery: boolean)` does:

1. Inserts a `profiles` row with `creator_id = <existing>`, `discovery_confidence = 1.0` (human-confirmed), `discovery_reason = 'manual_add'`.
2. If `run_discovery`: creates a `discovery_runs` row with `creator_id = <existing>`, `source = 'manual_add'`, `bulk_import_id = NULL`. Returns immediately. Worker picks it up.

**Worker behavior on `source = 'manual_add'`**: the resolver runs normally — Stage A fetches the new handle, Stage B expands its externalUrls, Gemini does canonicalization but the existing creator's `canonical_name` / `primary_niche` / `monetization_model` are **not overwritten** (the human already classified this creator in a prior session). Only additive fields update: new `known_usernames[]` entries are union-merged, new profile rows are inserted, new funnel_edges are added.

**Cross-workspace dedup still runs**: if the manually added handle turns out to share a monetization URL with a *different* existing creator, the rule cascade will raise a merge candidate — the human will see "hey, you just added this to Creator A but it also matches Creator B." Surface in the merge review UI; no silent merge. This is the safety net against a user accidentally attaching the wrong account.

**Why this matters for data completeness**: today, if discovery misses an asset and we later manually add it, we just get the stub. With v2, manual-add triggers the same resolver expansion — so adding "@esmae_backup" doesn't just create one profile row, it can reveal Esmae's additional monetization links, its own link-in-bio, etc. The manual add becomes a *recovery seed* for the partial footprint.

### 3.8 Apify budget

Each bulk import gets a dollar cap (env var `BULK_IMPORT_APIFY_USD_CAP`, default `$5`). `budget.py` tracks per-actor cost (Apify per-actor cost table, hand-maintained) and debits as fetches fire. Soft warning logs at 50% and 80%. Hard abort at 100% — remaining seeds marked `blocked_by_budget` in `discovery_runs`, bulk import status becomes `partial_budget_exceeded`.

## 4. Schema changes

### 4.1 New tables

```sql
CREATE TABLE bulk_imports (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  workspace_id uuid NOT NULL REFERENCES workspaces(id),
  initiated_by uuid,
  seeds_total int NOT NULL,
  seeds_committed int DEFAULT 0,
  seeds_failed int DEFAULT 0,
  seeds_blocked_by_budget int DEFAULT 0,
  merge_pass_completed_at timestamptz,
  cost_apify_cents int DEFAULT 0,
  status text NOT NULL DEFAULT 'running'
    CHECK (status IN ('running','completed','completed_with_failures','partial_budget_exceeded','cancelled')),
  created_at timestamptz DEFAULT NOW(),
  updated_at timestamptz DEFAULT NOW()
);

CREATE TABLE classifier_llm_guesses (
  canonical_url text PRIMARY KEY,
  platform_guess platform,
  account_type_guess account_type,
  confidence numeric(3,2) NOT NULL,
  model_version text NOT NULL,
  classified_at timestamptz DEFAULT NOW()
);

-- Reverse index for cross-seed dedup (maintained by commit_discovery_result).
CREATE TABLE profile_destination_links (
  profile_id uuid NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
  canonical_url text NOT NULL,
  destination_class text NOT NULL CHECK (destination_class IN ('monetization','aggregator','social','other')),
  PRIMARY KEY (profile_id, canonical_url)
);
CREATE INDEX profile_destination_links_url_idx ON profile_destination_links(canonical_url);
CREATE INDEX profile_destination_links_class_idx ON profile_destination_links(destination_class) WHERE destination_class IN ('monetization','aggregator');
```

### 4.2 New columns on existing tables

- `discovery_runs.bulk_import_id uuid REFERENCES bulk_imports(id) ON DELETE SET NULL` (nullable — single-handle discovery, retries, and manual adds have no bulk_import)
- `discovery_runs.apify_cost_cents int DEFAULT 0`
- `discovery_runs.source text NOT NULL DEFAULT 'seed' CHECK (source IN ('seed','manual_add','retry','auto_expand'))` — audit trail for how the run was triggered. `seed` = bulk or single-handle import. `manual_add` = user added a profile to an existing creator via UI and opted into discovery. `retry` = Re-run Discovery button. `auto_expand` = reserved for a future case where the cross-workspace merge pass decides to kick off discovery on a newly-surfaced secondary.
- `profiles.discovery_reason text` — which classifier rule, LLM guess, or human action classified this profile (`rule:instagram_social`, `llm:high_confidence`, `manual_add`, etc.).

### 4.3 New constraints

```sql
-- Idempotency for merge candidates (prevents dupe rows on seed re-run)
CREATE UNIQUE INDEX creator_merge_candidates_pair_uniq
  ON creator_merge_candidates (
    LEAST(creator_a_id, creator_b_id),
    GREATEST(creator_a_id, creator_b_id)
  );
```

### 4.4 RPC changes

- **`commit_discovery_result`** extended signature:
  - New param `p_discovered_urls jsonb` — array of `{canonical_url, platform, account_type, destination_class, reason}`. Records to `profile_destination_links`.
  - New param `p_bulk_import_id uuid` (nullable). Updates the bulk_imports row's counters.
  - Returns existing shape plus `urls_recorded int`.
- **`bulk_import_creator`** extended:
  - Creates bulk_imports row.
  - Returns `{bulk_import_id, run_ids[]}` instead of a single creator_id — the worker loops the runs.
- **New: `run_cross_seed_merge_pass(p_bulk_import_id uuid)`** — reads `profile_destination_links` inverted index, raises `creator_merge_candidates` per rule cascade, sets `bulk_imports.merge_pass_completed_at`. Called by the worker after all seeds in a bulk import reach a terminal state.

## 5. Data flow (one seed end to end)

```
bulk_import_creator(handles[])
  ↓
  bulk_imports row created (status=running)
  ↓ (one discovery_run per handle, all linked via bulk_import_id)
worker picks up pending runs
  ↓
  resolver.discover(run_id, handle, platform_hint)
    ├── Stage A: fetchers.{platform}.fetch(handle) → InputContext
    ├── Gemini pass: canonicalization + niche + text_mentions
    │   → synthesize URLs from text_mentions, push into Stage B queue
    └── Stage B (per URL):
         canonicalize.run(url)
         classifier.classify(canonical_url)
         if aggregator:  aggregators.{type}.resolve → Stage B per child (no recursion beyond)
         elif profile:   fetchers.{platform}.fetch → second-level InputContext
         elif monetization/other: record URL + classification only
    ↓
  identity.score_within_seed(discovered_profiles) → propose intra-seed merges
    ↓
  commit_discovery_result(
    p_run_id, p_creator_data, p_accounts, p_funnel_edges,
    p_discovered_urls, p_bulk_import_id
  )
    ↓
  bulk_imports.seeds_committed ++

(after all seeds terminal)
worker calls run_cross_seed_merge_pass(bulk_import_id)
  ↓
  builds inverted index from profile_destination_links
  ↓
  rule-cascade over each bucket → creator_merge_candidates inserts
  ↓
  bulk_imports.merge_pass_completed_at = NOW(), status = completed
```

## 6. Error handling

- **Apify empty dataset** → existing `EmptyDatasetError` path: `mark_discovery_failed` with `empty_context:` reason, dead-letter for replay. Bulk import counters still increment (`seeds_failed++`).
- **Apify rate limit (429)** → tenacity retry with exponential backoff inside the fetcher; if exhausted, raise `RateLimitError`, run marked failed, dead-lettered.
- **Budget exhausted mid-seed** → remaining URLs in that seed's Stage B are skipped (recorded as `blocked_by_budget` in `profile_destination_links`). The seed still commits what it has. Subsequent seeds skipped entirely with `seeds_blocked_by_budget++`.
- **Classifier LLM timeout** → URL recorded with `(platform='other', account_type='other', reason='llm:timeout')`. Non-fatal.
- **Aggregator fetch failure** (httpx 4xx/5xx) → aggregator recorded as `discovered but not resolved`; its destination list is empty; the run continues.
- **Idempotency** — re-running a seed writes the same `creator_merge_candidates` rows which are absorbed by the unique index; `profile_destination_links` upserts; `bulk_imports` counters are updated in the RPC (not by the worker) so double-invocation is safe.

## 7. Testing

### 7.1 Unit tests (existing structure + new)

- `test_canonicalize.py` — ~30 fixture URLs covering every rule: UTM stripping, short URL resolution (mocked), trailing slash, www prefix, protocol coercion.
- `test_classifier.py` — every primary rule + LLM fallback (mocked Gemini) + cache hit/miss + unknown URL path. Target >95% branch coverage on the classifier module — it's the foundation.
- `test_identity.py` — every cascade rule, bucket algorithm, CLIP tiebreak (mocked embedder).
- `test_resolver.py` — full Stage A + B flow with mocked fetchers + mocked aggregators. Covers: aggregator child no-recursion rule, text_mention synthesis, budget exhaustion mid-seed.
- `test_budget.py` — cost accrual, soft warnings at 50/80%, hard abort at 100%.
- Per-fetcher tests already scaffolded in PR #2 for IG + TT; add the same shape for YT, Patreon, OF, Fanvue.

### 7.2 Integration tests

- `test_discover_creator_v2.py` — one synthetic bulk import of 5 mocked seeds. Verifies commit RPC called 5× with correct args, cross-seed merge pass produces expected candidates, bulk_imports counters correct.
- `test_idempotency.py` — run the same seed twice; second run produces no new merge_candidates, upserts destination_links.

### 7.3 Live smoke test (gated, Apify $ cost)

Re-run discovery for existing 3 creators (Natalie Vox, Esmae, Aria Swan — the latter still expected to fail with `empty_context`). Expected deltas:
- Natalie gains enriched `@natalievox` secondary (Linktree destination) with its own bio/follower_count/avatar.
- Esmae's `esmaecursed` custom_domain is followed; if it has outbound monetization links, they become recorded URLs + funnel_edges.
- Each creator produces `profile_destination_links` rows.
- No new merge candidates (only 3 seeds, all distinct).
- `bulk_imports.cost_apify_cents` logged and under $2.

Smoke test is gated behind an explicit user "run smoke" approval — does not run in CI.

## 8. Success criteria

Measurable on a labeled 20-seed bulk import (to be curated before implementation):

1. **Coverage**: ≥80% of non-private seeds produce at least one enriched secondary profile OR at least one recorded monetization URL.
2. **Classification accuracy**: ≥95% of discovered URLs land in a rule-based classification (LLM fallback should be rare). Sampled manually on first 50 classifications.
3. **Identity correctness**: zero false-positive auto-merges on the labeled set. Merge candidates on the labeled set ranked by evidence quality — at least the top 3 candidates must be correct matches.
4. **Idempotency**: re-running the same bulk import produces zero new database rows (only upserts).
5. **Cost**: bulk import of 20 seeds stays under $10 Apify (half of default cap).
6. **Regressions**: all existing 45 pytest tests continue passing; `npx tsc --noEmit` exit 0.

## 9. Phasing

SP1 ships as one PR against main. Feature-flagged behind `DISCOVERY_V2_ENABLED` env var initially — the old `discover_creator.py` path stays alive until the smoke test passes on v2, then the flag flips and the old code is removed in a follow-up cleanup commit.

Platform fetchers FB + X are stubbed (fetcher class exists, returns empty InputContext with `discovery_reason='stub:not_implemented'`). SP1.1 follow-up adds the live Apify actors for both.

## 10. Open questions (for implementation plan, not this spec)

- Specific Apify actor cost table values (need to query Apify dashboard for current pricing per actor).
- CLIP threshold of 0.85 is a starting value — first 20 labeled merges calibrate it.
- Per-platform rate limit values for the `budget.py` token bucket (empirical, tuned after first live bulk import).
- Whether `run_cross_seed_merge_pass` runs synchronously in the worker or as a separate job (lean toward sync for n ≤ 50 seeds; revisit if bulk imports scale).

---

## Appendix A — File changes summary

**Created** (new):
- `scripts/pipeline/{__init__,resolver,classifier,identity,canonicalize,budget}.py`
- `scripts/fetchers/{__init__,base,instagram,tiktok,youtube,patreon,onlyfans,fanvue,facebook,twitter,generic}.py`
- `scripts/aggregators/{__init__,linktree,beacons,custom_domain}.py`
- `scripts/data/gazetteer_whatsmyname.json` (checked in)
- `scripts/data/monetization_overlay.yaml` (checked in)
- `scripts/tests/pipeline/*.py`
- `scripts/tests/fetchers/*.py`
- `scripts/tests/aggregators/*.py`
- `supabase/migrations/{ts}_discovery_v2_schema.sql`

**Modified**:
- `scripts/discover_creator.py` → becomes a thin entry point that calls `pipeline.resolver`; the Gemini prompt narrows to canonicalization+niche+text_mentions; respects `source = 'manual_add'` by not overwriting existing creator canonical fields.
- `scripts/worker.py` → supports `run_cross_seed_merge_pass` invocation after seeds in a bulk terminate; routes all `discovery_runs.source` values through the same resolver.
- `scripts/schemas.py` → adds `DiscoveredUrl`, `BulkImportRecord`, narrows `DiscoveryResult` shape.
- `scripts/requirements.txt` → adds `curl_cffi`, `yt-dlp`, `sentence-transformers`, `Pillow`.
- `src/app/(dashboard)/creators/actions.ts` → `addProfileToCreator` extended to accept `run_discovery: boolean` and create a `discovery_runs` row with `source = 'manual_add'` when true.
- `src/components/creators/AddAccountDialog.tsx` → new "Run discovery on this account after adding" checkbox (default checked).

**Deleted** (after flag flip, separate commit):
- `scripts/apify_details.py` (content migrated to `fetchers/instagram.py` + `fetchers/tiktok.py`).
- `scripts/link_in_bio.py` (content migrated to `aggregators/linktree.py` + `aggregators/beacons.py`).

## Appendix B — Decisions locked in this spec

- **Two-stage resolver, not BFS.** No depth parameter, no asset cap. Budget is Apify $, not URL count.
- **Aggregator children are terminal leaves.** No recursion beyond them.
- **URL classifier owns `(platform, account_type)`.** Gemini owns canonicalization + niche + text mentions only.
- **WhatsMyName gazetteer + hand-curated monetization overlay** as classifier seed data.
- **Rule cascade for identity resolution, not weighted sum.** Each merge has a stored reason in `evidence`.
- **Index-inverted dedup runs at every commit, cross-workspace.** The `profile_destination_links` index is persistent, not per-batch — every new profile (seed, bulk, manual add, retry) is checked against the workspace's full existing history. Late-arriving evidence merges into existing creators.
- **Manual Add Account triggers resolver expansion.** Adding an account via the UI creates a `discovery_runs` row with `source = 'manual_add'` and runs the full resolver (with canonical fields protected). Manual add becomes a *recovery seed* for incomplete footprints.
- **CLIP (ViT-B/32) for avatar similarity**, not pHash. Only as a bucket tiebreak.
- **`bulk_imports` as first-class observable job.** Not an implicit worker loop.
- **Unique index on `creator_merge_candidates(a,b)` pairs** for idempotency.
- **Feature-flag rollout** behind `DISCOVERY_V2_ENABLED`; old path stays alive until smoke test passes.
