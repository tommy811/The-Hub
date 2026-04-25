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
   - `classify(canon, supabase)` — deterministic rule-cascade (`monetization_overlay.yaml`) + cached LLM fallback (`classifier_llm_guesses` table).
   - Append a `DiscoveredUrl(canonical_url, platform, account_type, destination_class, reason)` to `discovered`.
   - If `account_type == 'link_in_bio'` and not already an aggregator child → expand once via `aggregators/{linktree, beacons, custom_domain}.py`. No chaining.
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

## LLM Routing

Pipeline-level Gemini 2.5 Flash for canonicalization + niche + text-mention extraction. Per-URL classification inside the resolver also uses Gemini Flash (cached in `classifier_llm_guesses`). Full routing table: [[PROJECT_STATE#8. LLM Routing]].
