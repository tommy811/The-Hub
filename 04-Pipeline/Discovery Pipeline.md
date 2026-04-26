# Discovery Pipeline

## Overview
Input: social handle or URL (any platform)
Output: fully mapped creator network in the database, plus a live progress bar in the UI as it runs.
Time: ~30–90 seconds per creator depending on destination count and Apify proxy luck.

The pipeline runs in two layers:
1. **Worker** (`scripts/worker.py`) — long-running poller, claims `pending` runs from the queue, dispatches to `discover_creator.run()`.
2. **Resolver** (`scripts/pipeline/resolver.py`) — two-stage seed-then-enrich logic that builds the canonical network for one creator.

---

## Worker Lifecycle (always-on via launchd)

The worker is registered as a macOS launchd user agent — auto-starts at login, restarts on crash, no manual `python worker.py` ritual.

**Plist:** `~/Library/LaunchAgents/com.thehub.worker.plist` (generated from a template; see `scripts/worker_ctl.sh`)
**Logs:** `~/Library/Logs/the-hub-worker.log` (stdout) + `~/Library/Logs/the-hub-worker.err.log` (stderr)
**Working dir:** `${REPO_ROOT}/scripts` so `python-dotenv`'s `load_dotenv()` picks up `scripts/.env`.
**Poll interval:** 30s (configurable via `POLL_INTERVAL_SECONDS` env var)
**Concurrency:** 5 (configurable via `MAX_CONCURRENT_RUNS`)

### Subcommands

```
scripts/worker_ctl.sh install     # one-time: write plist + load
scripts/worker_ctl.sh start       # start (no-op if already running)
scripts/worker_ctl.sh stop        # SIGTERM (KeepAlive auto-restarts)
scripts/worker_ctl.sh restart     # stop → KeepAlive respawns with fresh code
scripts/worker_ctl.sh unload      # disable auto-restart
scripts/worker_ctl.sh status      # PID + last 5 stdout lines
scripts/worker_ctl.sh log         # tail -f stdout
scripts/worker_ctl.sh err         # tail -f stderr
scripts/worker_ctl.sh uninstall   # unload + delete plist
```

> **After any code change touching `worker.py` or `pipeline/`**: run `scripts/worker_ctl.sh restart` so the running process picks up the new module bytecode. KeepAlive=true means stop is non-destructive — launchd respawns within `ThrottleInterval=10s`.

### Worker env requirements

The launchd-spawned process has a **clean environment** (only `PATH` + `HOME` from the plist). All API tokens are loaded by `dotenv.load_dotenv()` from `scripts/.env`:

- `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`
- `GEMINI_API_KEY`
- `APIFY_TOKEN`

> **Common failure mode:** if your shell exports a working `APIFY_TOKEN` but `scripts/.env` holds a stale/revoked one, your direct Python calls succeed (shell-exported wins because `load_dotenv` doesn't override existing env vars) while the launchd worker fails with `ApifyApiError: User was not found or authentication token is not valid`. Cure: keep `scripts/.env` and your shell config in sync whenever you rotate an API token.

---

## Pipeline Flow (one seed)

### Stage 0: queue pickup

`worker.py` selects up to `MAX_CONCURRENT_RUNS` rows from `discovery_runs` where `status='pending'`, claims each via `UPDATE ... SET status='processing' WHERE status='pending'` (CAS — only one worker wins), then dispatches to `discover_creator.run()` per row.

### Stage 1: progress writer + budget

`discover_creator.run()` initializes:
- `progress = _make_progress_writer(sb, run_id)` — closure over a non-fatal `discovery_runs.update()` call. Failures log a yellow warning but don't blow up the run.
- `BudgetTracker(cap_cents=int(env.BULK_IMPORT_APIFY_USD_CAP * 100))` — Apify spend cap per seed (default $5).

### Stage 2: resolver — Stage A (fetch seed)

`resolver.resolve_seed(handle, platform_hint, supabase, apify_client, budget, progress=...)`:

1. **`_emit(10, "Fetching profile")`** — first progress write.
2. `budget.debit("apify/{platform_hint}-scraper", _apify_cost(...))`.
3. `seed_ctx = fetch_seed(handle, platform_hint, apify_client)` — dispatches to one of:
   - `fetchers/instagram.py` — `apify/instagram-scraper` details mode (with retry — see "Fetcher resilience" below)
   - `fetchers/tiktok.py` — `clockworks/tiktok-scraper` (with retry)
   - `fetchers/youtube.py` — `yt-dlp` channel info
   - `fetchers/onlyfans.py` — `curl_cffi` chrome120 JA3 impersonation
   - `fetchers/patreon.py`, `fetchers/fanvue.py`, `fetchers/generic.py` — `httpx`
   - `fetchers/facebook.py`, `fetchers/twitter.py` — **stubbed for SP1.1** (return `source_note='stub:not_implemented'`)
4. If the actor returns shape-valid but empty data → `EmptyDatasetError` (creator marked failed with `empty_context:` reason).

### Stage 3: resolver — Stage B (classify + enrich destinations)

5. **`_emit(35, "Resolving links")`** — second progress write.
6. For each URL in `seed_ctx.external_urls`:
   - Resolve short URLs, canonicalize, dedupe via `visited_canonical` set.
   - **Noise filter at entry (sync 16, 2026-04-26)** — `_classify_and_enrich` calls `is_noise_url(canon)` immediately after `visited_canonical.add(canon)`. If the URL matches any noise pattern (CDN hosts `*.cloudfront.net`, API redirector hosts `*.api.linkme.global`, Firebase Dynamic Links `*.page.link`, empty-path homepages, legal/footer paths like `/terms`/`/privacy`/`/about`), drop it before it ever becomes a `DiscoveredUrl` row. Same predicate also retroactively soft-deleted 30 stale rows from before the filter shipped — see PROJECT_STATE Decisions Log sync 16.
   - `classify(canon, supabase)` — dispatch order:
     1. **`_classify_linkme_redirector` (sync 17, T18)** runs FIRST. Parses `?sensitiveLinkLabel=OF/Fanvue/Fanfix/Fanplace/Patreon` from `visit.link.me/...` URLs via a hand-maintained `_LINKME_LABEL_TO_PLATFORM` map and returns `(<platform>, monetization)` at confidence 1.0 with reason `rule:linkme_redirector_<label>`. Without this, the gazetteer's link.me catch-all classified these monetization-bearing URLs as `(linktree, link_in_bio)`.
     2. Deterministic rule-cascade (`monetization_overlay.yaml`, with 13 specific host→platform rules added in T17 sync 16 so `tapforallmylinks.com → tapforallmylinks` etc. instead of bucketing as `custom_domain`).
     3. Cached LLM fallback (`classifier_llm_guesses` table). LLM prompt was rewritten in T20 (sync 17) to ALSO return 4 enriched suggestion fields (`suggested_label`, `suggested_slug`, `description`, `icon_category`); `_classify_via_llm` now returns a 5-tuple `(platform, account_type, confidence, model_version, enriched_metadata)`; `_cache_insert` accepts an optional `enriched: dict` parameter and writes those 4 columns alongside the platform/account_type guess. Empty-string responses persist as NULL.
   - Append a `DiscoveredUrl(canonical_url, platform, account_type, destination_class, reason, harvest_method, raw_text)` to `discovered`.
   - **Universal URL Harvester (2026-04-26)** — if the URL needs page-level destination extraction (aggregators, link-in-bio, gated landing pages), call `harvester.harvest_urls(canon, supabase)` to pull all outbound destinations in one shot. Replaces the previous per-aggregator dispatch (`aggregators/{linktree,beacons,custom_domain}.py`, deleted). Cascade described below in **Universal URL Harvester** section.
   - If `account_type ∈ {'social', 'monetization'}` and budget allows → enrich via the platform fetcher. Successful enrichments land in `enriched_contexts[canon] = ctx`.

### Stage 4: Gemini — canonicalization + niche + text mentions

7. **`_emit(70, "Analyzing")`** — third progress write.
8. `gemini_result = run_gemini_discovery_v2(seed_ctx)` — single Gemini 2.5 Flash call. Returns `DiscoveryResultV2(canonical_name, known_usernames, display_name_variants, primary_niche, monetization_model, text_mentions[])`.
9. For each `text_mention`: synthesize URL from `(platform, handle)` and feed back into `_classify_and_enrich` (one-shot expansion only).

### Stage 5: commit

Back in `discover_creator.run()`:

10. **`progress(90, "Saving")`** — fourth progress write.
11. `_commit_v2(sb, run_id, workspace_id, result, bulk_import_id)` builds `p_accounts`:
    - **Seed entry:** `is_primary=True, url=_seed_profile_url(seed.platform, seed.handle)` (canonical profile URL via the `_SEED_URL_HOSTS` table — handles tiktok/youtube `@`-prefix, linkedin `/in/`, etc.).
    - **Enriched entries:** one per `enriched_contexts.items()` with `url=canon, discovery_confidence=0.9`.
    - **Discovered-only stub entries:** one per `DiscoveredUrl` not already in `enriched_contexts` — no fetcher exists for that platform (novel: Wattpad / Substack / etc.) OR resolver skipped enrichment (link_in_bio aggregator parents, budget-skipped). `discovery_confidence=0.6, reasoning="discovered_only_no_fetcher: {classifier reason}"`. Without this, novel-platform URLs lived only in `profile_destination_links` and never rendered on the HQ page.
    - **URL-keyed dedup pass (sync 16, 2026-04-26)** — before sending `p_accounts` to the RPC, `_commit_v2` dedupes by canonical URL. Higher `discovery_confidence` wins; on a tie, a non-`other` platform wins over `other`. Without this, distinct gazetteer rules / discovery paths could each emit a row for the same URL with different `platform` values, and the DB-side `profiles_url_unique` constraint would reject the second INSERT and crash the whole commit. Combined with T17's specific platform-enum extensions, this resolves the long-running unique-key collision pattern (e.g. Aria's `tapforallmylinks` row no longer doubles up).
12. RPC `commit_discovery_result` upserts profiles, inserts funnel edges, writes `profile_destination_links`, bumps `bulk_imports.seeds_committed`, marks the run completed.
13. **`progress(100, "Done")`** — final progress write.

### Stage 6: posts scrape (IG seeds only)

14. After `_commit_v2`, IG seeds also trigger `scrape_instagram_profile(workspace_id, handle, limit=5)` to pull the latest 5 posts into `scraped_content`. TikTok/YouTube/etc. wait for the Phase 2 scraping cron.

---

## UI Progress Surface

While `creators.onboarding_status='processing'`, both the grid `CreatorCard` and the creator HQ banner mount `<DiscoveryProgress runId={...} />`:

- Polls `getDiscoveryProgress(runId)` (server action) every 3s.
- Renders a thin progress bar + 2-3 word stage label + `{pct}%`.
- When `status` flips out of `pending|processing` → calls `router.refresh()` to flip the parent into its terminal state (ready / failed).
- Component unmounts cleanly when status changes; no zombie pollers.

---

## Fetcher Resilience

Apify scrapers rotate proxies; some profiles get blocked on certain pools and succeed on the next attempt. Without retry, a single hostile proxy hit fails the whole run.

`fetchers/base.py::is_transient_apify_error(exc)` — predicate matching upstream errors we've actually seen:
- `user was not found`
- `authentication token` (matches the upstream Apify API auth challenge wording)
- `rate limit`, `429`, `too many requests`
- `challenge`, `session expired`, `captcha`

`fetchers/instagram.py::_call_actor` and `fetchers/tiktok.py::_call_actor` are tenacity-wrapped:
- 3 attempts max (`stop_after_attempt(3)`)
- exponential backoff `wait_exponential(multiplier=2, min=3, max=15)`
- `before_sleep_log` writes the retry to stderr (visible in `~/Library/Logs/the-hub-worker.err.log`)

`EmptyDatasetError` is **not** retriable by design — its message shape ("returned 0 items") doesn't match the predicate, so a real "actor succeeded but no data" outcome fails fast rather than burning 3 attempts.

---

## Error Handling

`discover_creator.run()` has three exception branches:

- `EmptyDatasetError` → `mark_discovery_failed_with_retry(run_id, "empty_context: {e}")` (private/restricted/banned)
- `BudgetExhaustedError` → `mark_discovery_failed_with_retry(run_id, "budget_exceeded: {e}")` (Apify spend cap hit)
- `Exception` (catch-all) → `mark_discovery_failed_with_retry(run_id, str(e))`

`mark_discovery_failed_with_retry` uses tenacity (3 attempts, exponential backoff) on the RPC call itself, falling back to writing to `scripts/discovery_dead_letter.jsonl` if the RPC stays down. `scripts/replay_dead_letter.py` re-queues entries from that file.

---

## Retry from the UI

Failed creator card / HQ page → `Re-run Discovery` button → `retryCreatorDiscovery` server action → `retry_creator_discovery` RPC → new `discovery_runs` row with `attempt_number+1`, copies `input_handle` + `input_platform_hint` (with `::platform` cast), updates `creators.last_discovery_run_id` to the new run, resets `onboarding_status='processing'`. Worker picks up the new pending row within ~30s.

> The `last_discovery_run_id` update is critical for the progress UI — without it the polling component would lock onto the previous (terminal) run and never observe the new one.

---

## Universal URL Harvester

Single entry point: `harvester.harvest_urls(url, supabase)`. Replaces the per-aggregator extractor dispatch (`aggregators/{linktree,beacons,custom_domain}.py`, deleted 2026-04-26).

**3-tier cascade:**

1. **Cache** — `url_harvest_cache` table (24h TTL, workspace-agnostic, mirrors `classifier_llm_guesses`). On hit, returns the cached `HarvestedUrl[]` immediately and skips Tiers 1+2. Lives in `harvester/cache.py`.
2. **Tier 1 (httpx + BS4)** — `harvester/tier1_static.py::fetch_static`. Pulls the page, parses anchors, runs a 4-signal escalation detector: (a) SPA marker (e.g. astro-island, next-data, root div pattern); (b) near-empty anchor count (`< 3` resolved hrefs); (c) sensitive-content gate keywords ("over 18", "i agree", "open link" etc.); (d) JS-only body (no rendered text). Any signal trips → escalate to Tier 2.
3. **Tier 2 (Apify Puppeteer Scraper)** — `harvester/tier2_headless.py::fetch_headless`. Calls `apify/puppeteer-scraper` with a custom `page_function.js` that hooks `window.open` + `location.href` setters BEFORE page scripts execute (so SPA single-page redirectors get captured even if their click handler tries to navigate the entire window away), then auto-clicks 7 interstitial keyword variants ("open link", "continue", "i am over 18", "i agree", "i confirm", "18+", "enter") via Puppeteer 22+ `page.$$('xpath/...')` selector syntax. Returns the unified anchor + intercepted-navigation set.

**Classification + destination_class mapping** (in `harvester/orchestrator.py`):
- Each harvested URL is canonicalized (`pipeline.canonicalize.canonicalize_url`) and classified (`pipeline.classifier.classify`).
- A host-aware `_destination_class_for(account_type, canonical_url)` maps the result through 10 classes — promotes Substack subdomains, Spotify, Apple Podcasts to `content`; amzn.to, geni.us, lnk.to, shareasale, skimresources to `affiliate`; Shopify subdomains, Etsy, Depop to `commerce`; Telegram, WhatsApp, Discord to `messaging`. Same-host self-links are dropped (an aggregator's footer linking to its own homepage shouldn't surface as a destination of itself).

**Cache write** — on Tier 1 or Tier 2 success, the orchestrator writes the result back to `url_harvest_cache` with `expires_at = NOW() + 24h`.

**Audit columns** — `commit_discovery_result` v3+ writes `harvest_method` (`cache|httpx|headless`) and `raw_text` (anchor / button text from harvest) to `profile_destination_links` per URL. Surfaces in Creator HQ as a `gated` chip on rows where `harvest_method='headless'`.

**Live-smoke result (2026-04-26)** — re-discovery of `esmaecursed-1776896975319784` cleanly captured the Fanplace link previously hidden behind tapforallmylinks.com's 2-step "Sensitive Content / Open link" gate. Tier 1 detected the gate, Tier 2 hooked the `location.href` setter and harvested all 6 destinations (4 social + 2 messaging). Total Apify spend ~80¢ across 4 smoke runs.

---

## LLM Routing

Pipeline-level Gemini 2.5 Flash for canonicalization + niche + text-mention extraction. Per-URL classification inside the resolver also uses Gemini Flash (cached in `classifier_llm_guesses`). Full routing table: [[PROJECT_STATE#8. LLM Routing]].

---

## Operator Workflow — `new_platform_watchdog` view (sync 17)

When the resolver hits a host its gazetteer doesn't recognize, the row lands in `profiles` with `platform='other'`. Those rows surface in the `new_platform_watchdog` SQL view (migration `20260426060000` v1, replaced by `20260426080000` v2 with Gemini enrichment).

**v2 columns (11):** host, creator_count, profile_count, last_seen, sample_url, sample_creator_name, **suggested_label**, **suggested_slug**, **description**, **icon_category**, classified_at — with the 4 LLM-suggestion columns joined via CTE (`grouped` + `guess_per_host` via `DISTINCT ON (host)`) from `classifier_llm_guesses`.

**Triage query:**
```sql
SELECT * FROM new_platform_watchdog ORDER BY creator_count DESC LIMIT 50;
```

**Workflow:** VA opens the view, ratifies Gemini's recommendation per row (one click — no manual research because the LLM already provided a label, slug, description, icon-category guess), then runs the standard 3-step add per ratified host:

1. Add a gazetteer rule in `data/monetization_overlay.yaml` mapping the host to the suggested platform value (or a new enum value if Gemini's `suggested_slug` is novel and ratifiable).
2. Add a PLATFORMS dict entry in `src/lib/platforms.ts` with the right react-icons Si* / lucide fallback (driven by `icon_category`).
3. Add a `HOST_PLATFORM_MAP` entry so URL-host inference works for legacy `platform='other'` rows.

Total ~5 minutes per platform. Each ratified host drops the watchdog count by 1.

The view returns 0 rows for the current 5-creator dataset — the gazetteer + T17 backfill is comprehensive. The watchdog is forward-cover for novel platforms surfacing during future bulk imports.
