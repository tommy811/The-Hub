# Changelog

## 2026-04-26 (sync 17 — handle normalization + regression-test ring + Gemini-enriched watchdog)
- Added (T18, commit `e77a252`): **Centralized `_normalize_handle(handle, platform)` helper** in `scripts/discover_creator.py` — strips leading `@` and lowercases for 35 case-insensitive platforms (`_CASE_INSENSITIVE_PLATFORMS` frozenset). Idempotent. Applied to seed account, every enriched-context append, every discovered-only append, AND `funnel_edges` (both `from_handle` and `to_handle`). Single chokepoint at the `_commit_v2` layer was preferred over sprinkling normalize calls across the resolver.
- Added (T18): **`_r` (TikTok client refresh) and `lang` (locale) added to `_TRACKING_PARAMS`** in `scripts/pipeline/canonicalize.py` so `tiktok.com/@kira?_r=1` and `tiktok.com/@kira?lang=en` canonicalize to the same string.
- Added (T18): **`_classify_linkme_redirector` runs FIRST in `pipeline.classifier.classify()`** — BEFORE the gazetteer. Parses `?sensitiveLinkLabel=OF/Fanvue/Fanfix/Fanplace/Patreon` from `visit.link.me/...` URLs via a hand-maintained `_LINKME_LABEL_TO_PLATFORM` map. Returns `(<platform>, monetization)` at confidence 1.0 with reason `rule:linkme_redirector_<label>`. Without this, these monetization-bearing URLs were classified as `(linktree, link_in_bio)` by the gazetteer's link.me catch-all.
- Migrated (T18): **5 duplicate profile rows soft-deleted** (Kira's 5 TikTok dupes from `@kira`/`@Kira`/`kira` variants; Natalie's YouTube + Twitter case dupes). 7 active rows had handles normalized (lowercased + @-stripped). One-time migration artifact: 5 soft-deleted rows tombstoned with `__deleted_<uuid>` suffix to free unique-key slots before normalizing surviving rows. Application-layer ON CONFLICT updates re-activate the same row going forward.
- Reclassified (T18): **Kira's `visit.link.me/kirapregiato?webLinkId=1577546&sensitiveLinkLabel=OF` row** retroactively from `(linktree, link_in_bio)` → `(onlyfans, monetization)`.
- Added (T19, commit `a12f45e`): **`scripts/tests/test_commit_v2_dedup.py`** — 13 tests covering EVERY duplicate-prone failure mode through `_commit_v2` with mocked RPC: 7 handle-normalization tests + 6 full-integration tests (same-canonical-URL collapse, @-prefix collapse, Valentina link.me-vs-fanfix non-collapse, higher-confidence wins, Natalie YouTube case variants, funnel-edge handle normalization).
- Added (T19): **`scripts/tests/test_platform_enum_drift.py`** — 2 static tests locking in all 19 T17 enum additions + 18 pre-T17 values via assertions on `Platform.__args__`. Catches drops/typos at PR time. 1 placeholder skip for the future live-DB drift check (requires CI to have `SUPABASE_DB_URL`).
- Added (T19, migration `20260426060000_new_platform_watchdog_view`): **`new_platform_watchdog` SQL view v1** — surfaces `platform='other'` rows grouped by URL host, joined to creator names + last_seen + sample_url. VA-friendly triage query: `SELECT * FROM new_platform_watchdog ORDER BY creator_count DESC LIMIT 50;`. Returns 0 rows currently — gazetteer + T17 backfill comprehensive for the 5-creator dataset.
- Added (T19): **PROJECT_STATE §21 "Discovery Pipeline Invariants"** — 8 numbered invariants (later extended to 9 by T20) + regression-test coverage table mapping each failure mode to its locking test.
- Added (T20, migration `20260426070000_classifier_llm_guesses_enriched_metadata`): **4 nullable TEXT columns on `classifier_llm_guesses`** — `suggested_label`, `suggested_slug`, `description`, `icon_category`. Empty-string LLM responses persist as NULL.
- Added (T20, commit `722f24b`): **LLM prompt rewritten to ALSO return enriched suggestion fields** alongside platform/account_type/confidence. `_classify_via_llm` now returns 5-tuple `(platform, account_type, confidence, model_version, enriched_metadata)`. `_cache_insert` accepts optional `enriched: dict` parameter.
- Added (T20, migration `20260426080000_watchdog_view_with_llm_suggestions`): **`new_platform_watchdog` view replaced** with CTE-based join to `classifier_llm_guesses` (`grouped` + `guess_per_host` via `DISTINCT ON (host)`). Surfaces Gemini's `suggested_label` / `suggested_slug` / `description` / `icon_category` per host. View now has 11 columns. **Caveat:** original spec used 4 correlated subqueries which Postgres rejected with `42803`; refactored to CTE-based LEFT JOIN with identical semantics.
- Added (T20): 2 new tests for enriched cache write + graceful empty-string handling.
- Removed from §20 Known Limitations: visit.link.me OF redirector entry (fixed by T18); Pydantic-vs-Postgres enum drift entry (partially locked by T19 static tests, downgraded to placeholder skip for live-DB diff).
- Verified: **249/249 pytest passing + 1 skip. tsc 0 errors.** 3 commits this pass: `e77a252` (T18) → `a12f45e` (T19) → `722f24b` (T20).

## 2026-04-26 (sync 16 — profile noise filter retroactive + specific platform identification + AccountRow + banner foundation)
- Added (T16, commit `23cc1e9`): **Profile noise filter retroactive cleanup** — soft-deleted 30 stale noise profile rows across all 5 creators in one sweep. Patterns: `*.api.linkme.global` (link.me API redirector hosts), `*.cloudfront.net` (CDN), `*.page.link` (Firebase Dynamic Links shortener), empty-path homepages, legal/footer paths (`/terms`, `/privacy`, `/about`), plus a Phase-1.2 follow-up sweep for `music.link.me`.
- Added (T16): **Resolver `_classify_and_enrich` calls `is_noise_url(canon)`** immediately after `visited_canonical.add(canon)` — drops noise URLs at the gate, before they ever become `DiscoveredUrl` rows.
- Added (T16): **`_commit_v2` URL-keyed dedup pass on `accounts`** before the RPC call — higher `discovery_confidence` wins; non-`other` platform wins on tie. Fixes Aria's `tapforallmylinks` duplicate row (and similar collisions on the way to T17's permanent fix).
- Added (T16): **Reddit / Threads / Bluesky / Snapchat to PLATFORMS dict** with proper Si* icons; new `getPlatformFromUrl()` + `resolvePlatform(platform, url)` for URL-host inference fallback so legacy `platform='other'` rows still get the right label.
- Changed (T16): **Unified clip icon (`lucide Link`) for all aggregator types** — linktree, beacons, custom_domain. Visual consistency win.
- Changed (T16): **All Destinations panel moved from above tabs to BELOW tabs** on creator HQ, wrapped in native collapsed-by-default `<details>` element. Reduces visual noise above the fold.
- Changed (T16): **Stats Strip uses `resolvePlatform(platform, url)`** so `Other` rows display proper labels (Reddit/Snapchat); Link-in-Bio now shows platform names instead of raw handles.
- Added (T17, commit `c08dcdd`): **19 new values to Postgres `platform` enum** via migration `20260426040000_add_platform_values_specific_aggregators_and_monetization` — `link_me`, `tapforallmylinks`, `allmylinks`, `lnk_bio`, `snipfeed`, `launchyoursocials`, `fanfix`, `cashapp`, `venmo`, `snapchat`, `reddit`, `spotify`, `threads`, `bluesky`, `kofi`, `buymeacoffee`, `substack`, `discord`, `whatsapp`. Total enum count post-migration ~37.
- Added (T17): **Pydantic `Platform` Literal in `scripts/schemas.py` extended to match.** Caught at pre-commit when the first discovery run after the migration failed with `pydantic.ValidationError`. Fixed before push. `test_schemas.py` updated. Future enum extensions could silently break discovery without a CI diff test (flagged as future work).
- Added (T17): **13 specific host→platform rules in gazetteer** (`data/monetization_overlay.yaml`); 6 older generic rules removed so new specifics win. Examples: `tapforallmylinks.com → tapforallmylinks` (was `custom_domain`); `cash.app → cashapp` (was `other`); `link.me → link_me` (was `custom_domain`); `app.fanfix.io → fanfix` (was `other`); `venmo.com → venmo` (was `other`).
- Added (T17): **13+ new entries to `src/lib/platforms.ts` PLATFORMS dict** with proper Si* icons (Spotify, Substack, Discord, WhatsApp, Kofi, BuyMeACoffee verified in react-icons 5.6.0); Cash App / Venmo / Fanfix use lucide fallbacks (`DollarSign`, `Heart`). No new dependencies.
- Added (T17): **`resolvePlatform` derives URL hostname as label** when `platform='custom_domain'` and no specific aggregator matches → custom funnel domains show as e.g. "ariaswan.com" instead of "Custom Domain".
- Added (T17): **`HOST_PLATFORM_MAP` extended** with all new aggregator/monetization hosts so URL-host inference works for legacy `platform='other'` data.
- Changed (T17): **AccountRow layout restructured** per Simon's UX call. Column 1 (180px) = `[icon] [Platform Name]`. Column 2 (280px) = handle (clickable) + display_name secondary line. Platform name first, not handle first.
- Added (T17): **3 new `creators` columns** via migration `20260426050000_creator_cover_and_banner` — `cover_image_url` (scraper-set, null pending Phase 3), `banner_url` (agency-managed override), `override_avatar_url` (agency-managed headshot, preferred over scraper avatar by both creator HQ and grid card).
- Added (T17): **`<BannerWithFallback>` client component** rendered on creator HQ below the merge-candidate banner / above the header. Uses `banner_url` if set, else `cover_image_url`, else gradient placeholder.
- Added (T17): **11 backfill UPDATEs** converted existing profile rows from `other` / `custom_domain` to specific platforms (tapforallmylinks=3, link_me=1, fanfix=1, cashapp=1, venmo=1, snapchat=2, reddit=1, spotify=1).
- Verified: **All 5 creators re-discovered cleanly** (Esmae, Aria, Kira, Natalie, Valentina). ~$1 Apify spend across 5 runs. Per-creator results: Aria → tapforallmylinks + Fanplace (proper labels); Valentina → link.me + Fanfix + Cash App + Venmo coexist as 4 distinct rows (unique-key collision bug fixed); Kira → link.me + Linktree; Natalie → 2 Telegram + 2 tapforallmylinks + Fanplace; Esmae → tapforallmylinks×2 + Fanplace + Telegram×2. **227 pytest passing. tsc 0 errors.**
- Known (minor leftovers): Esmae's stale `handle="tapforallmylinks.com"` host-as-handle row from older data; Kira's TT enrichment hit Apify memory cap (8192MB requested, 4096MB allotted, non-fatal one-off); banner UI bare-bones until Phase 3 scraper writes `cover_image_url`; SCHEMA.md regen still blocked on missing `SUPABASE_DB_URL` (pre-existing tooling gap).
- 2 commit batches this pass: `23cc1e9` (T16: noise filter + UI polish) → `c08dcdd` (T17: specific platform identification + AccountRow + banner foundation).

## 2026-04-26 (sync 15 — Universal URL Harvester ships)
- Added: **`scripts/harvester/` package** — single entry point `harvest_urls(url, supabase)` runs a 3-tier cascade (cache → Tier 1 httpx + 4-signal escalation detector → Tier 2 Apify Puppeteer Scraper headless render). Replaces the deleted `scripts/aggregators/{linktree,beacons,custom_domain}.py` per-aggregator dispatch.
- Added: **`apify/puppeteer-scraper`** as a new Apify dependency. Backs Tier 2 of the harvester. Custom `page_function.js` hooks `window.open` and `location.href` setters BEFORE page scripts execute, then auto-clicks 7 interstitial keyword variants ("open link", "continue", "i am over 18", "i agree", "i confirm", "18+", "enter") via Puppeteer 22+ `page.$$('xpath/...')` selector syntax.
- Added: **`url_harvest_cache` table** (24 tables total — 23 → 24). Workspace-agnostic, 24h TTL by default, indexed on `expires_at`. Mirrors the `classifier_llm_guesses` no-RLS pattern.
- Added: **3 audit columns on `profile_destination_links`** — `harvest_method` (`cache|httpx|headless`), `raw_text` (anchor / button text captured at harvest), `harvested_at` (timestamptz default NOW()).
- Added: **`DestinationClass` Literal extended 4 → 10 values** — `monetization|aggregator|social|commerce|messaging|content|affiliate|professional|other|unknown`. Live DB CHECK constraint extended to match (migration `20260426020000`).
- Added: **`commit_discovery_result` v3 + v4** — v3 writes `harvest_method` and `raw_text` to `profile_destination_links` (migration `20260426010000`); v4 patches the ON CONFLICT clause to update `destination_class` so post-fix re-runs refresh stale rows (migration `20260426030000`).
- Added: **~30 new gazetteer rules in `data/monetization_overlay.yaml`** — BuyMeCoffee, Ko-fi, Substack subdomains, Spotify, Telegram, WhatsApp, affiliate redirectors (amzn.to / geni.us / shareasale / skimresources), Apple Podcasts, etc. + host-aware `destination_class` mapping in the orchestrator.
- Added: **Creator HQ "All Destinations" section** — renders every `profile_destination_links` row grouped by `destination_class` with a `gated` chip on rows where `harvest_method='headless'`.
- Changed: **Resolver `_classify_and_enrich` now delegates to `harvest_urls()`** — one call per page, returns all outbound destinations. Per-aggregator dispatch is gone.
- Changed: **Canonicalizer strips additional tracking params** — `igsh`, `l_`, `s`, `_t`, `aff`, `ref_id` (commit `6fe423e`). `?s=21` and `?igsh=...` no longer create false-distinct rows in `profile_destination_links`.
- Fixed: **`page.$x` → `page.$$('xpath/...')`** Puppeteer 22+ migration in the page function (commit `b632b81`); messaging class mapping; same-host self-link filter (an aggregator's footer linking to its own homepage shouldn't surface as a destination of itself).
- Removed: **`scripts/aggregators/` package** entirely (commit `c71fd2e`). Functionality migrated to `harvester/`.
- Verified: **192 pytest passing. tsc 0 errors.** Live smoke (2026-04-26): re-discovery of `esmaecursed-1776896975319784` cleanly captured the Fanplace link previously hidden behind tapforallmylinks.com's 2-step "Sensitive Content / Open link" gate. All 6 destinations correctly classified including 2 messaging links. Total Apify spend ~80¢ across 4 smoke runs.
- Known limitation: **SCHEMA.md regen still blocked on missing `SUPABASE_DB_URL`** in `scripts/.env`. Live DB has 24 tables; `docs/SCHEMA.md` still shows 23. PROJECT_STATE.md §4.1 hand-updated. Pre-existing tooling gap; Simon's call to fill the env var.
- 17 commits this pass: `6fe423e` (canonicalizer) → `4cbd65b` (types) → `df456c1` (cache schema) → `f443933` (cache module) → `584302e` (Tier 1) → `f143e64` (Tier 1 test) → `7ba5e5d` (Tier 2) → `b529ee0` (Tier 2 fixes) → `321e651` (orchestrator) → `c10dc15` (gazetteer) → `27d7ad5` (resolver wiring) → `43e820a` (commit_v3) → `c71fd2e` (delete aggregators) → `880fadf` (Creator HQ section) → `b632b81` (Puppeteer migration + messaging) → `6edbee6` (CHECK extension) → `f772add` (commit_v4 ON CONFLICT update destination_class).

## 2026-04-25 (sync 13 — always-on worker + live progress UI + RPC + token fix sweep)
- Added: **always-on discovery worker** via macOS launchd. New `scripts/worker_ctl.sh` (install/start/stop/restart/unload/status/log/err/uninstall) generates `~/Library/LaunchAgents/com.thehub.worker.plist`, manages logs at `~/Library/Logs/the-hub-worker.{log,err.log}`. RunAtLoad + KeepAlive + ThrottleInterval=10s. After pipeline edits, `scripts/worker_ctl.sh restart` makes launchd respawn with fresh code.
- Added: **live progress bar UI** for in-flight discovery. New `discovery_runs.progress_pct` (smallint, default 0) + `progress_label` (text) columns (migration `20260425010000`). Pipeline emits 5 stages — Fetching profile (10%) → Resolving links (35%) → Analyzing (70%) → Saving (90%) → Done (100%). New `<DiscoveryProgress>` client component polls `getDiscoveryProgress` server action every 3s while a card is in `processing`; calls `router.refresh()` when status flips. Drops into CreatorCard processing branch + creator HQ banner.
- Added: **novel-platform persistence**. `_commit_v2` now builds stub `profiles` rows for any `DiscoveredUrl` not already enriched (Wattpad / Substack / aggregator parents / budget-skipped). Without this, those URLs only landed in `profile_destination_links` and never rendered on the HQ page. Stub `discovery_confidence=0.6, reasoning="discovered_only_no_fetcher: ..."`.
- Added: **fetcher retry-on-transient**. `fetchers/base.py::is_transient_apify_error` predicate matching "user was not found", "authentication token", "rate limit", "challenge", "session expired", "captcha", "429". Tenacity-wrapped `_call_actor` in `instagram.py` and `tiktok.py` retries 3× with 3-15s exponential backoff. EmptyDatasetError stays non-retryable.
- Added: `_seed_profile_url(platform, handle)` helper in `discover_creator.py` — builds the canonical primary URL via a per-platform host table (handles tiktok/youtube `@`-prefix, linkedin `/in/`, etc.). Used by `_commit_v2` for the seed entry.
- Fixed: **`retry_creator_discovery` now updates `creators.last_discovery_run_id`** to the new run id (migration `20260425020000`). Without this the progress UI polled the previous failed run forever and the new run's spinner stuck at "Queued 0%".
- Fixed: **`bulk_import_creator` missing `::platform` cast** on the `discovery_runs` INSERT (migration `20260425030000`). Same shape as the retry-RPC cast bug from earlier the same day; missed in that sweep. Every Bulk Paste / Single Handle import errored with Postgres `22P02` until the fix.
- Fixed: **seed/primary profile URL was never written** by `_commit_v2`. The upsert COALESCE preserved the null, so the first row on every creator HQ page rendered as plain text instead of a clickable link. Patched the commit-side wiring + backfilled Kira's row directly via SQL (the other 3 creators had URLs from earlier import paths).
- Fixed: stale `APIFY_TOKEN` in `scripts/.env` (revoked; shell had the working one). Backed up `.env` → `.env.bak.{ts}`, replaced just the `APIFY_TOKEN=` line via Python rewrite, restarted worker. Aria Swan's discovery then completed cleanly with 704K-follower IG + secondary IG + link-in-bio.
- Changed: **CreatorCard ready state** — stripped platform identity (no `@handle`, no IG icon under name). Same intent as the HQ-page subtitle cleanup.
- Changed: **CreatorCard failed state** — replaced PlatformIcon with the canonical-name monogram in a red-tinted box.
- Changed: **Sidebar tracking-type shortcuts removed** (Managed/Candidates/Competitors/Inspiration). The in-page chip filter row is now the single source of filter truth. URL-driven `?tracking=…` filtering unaffected.
- Verified: tsc 0, pytest 102 → 107 (3 new for novel-platform persistence + 2 for seed URL). Browser smoke via Chrome DevTools MCP — synthetic SQL flip confirmed the progress bar advances "FETCHING PROFILE 42%" → "ANALYZING 70%" within one poll cycle.
- 10 commits this pass: `6a7153e` (novel-platform persistence) → `c75903d` (HQ subtitle + sidebar dedup) → `db5a6b3` (launchd worker) → `2a3da9a` (progress bar) → `d6a523b` (retry RPC last_run_id) → `0b6dedb` (worker_ctl restart) → `a147455` (CreatorCard cleanup) → `5e95469` (fetcher retry) → `ac861e3` (bulk_import cast) → `8bc9ddc` (seed URL write).

## 2026-04-25 (sync 12 — creator HQ revamp + autonomous-fix-list skill)
- Fixed: `retry_creator_discovery` RPC casts `input_platform_hint::platform` (migration `20260425000300`) — UI Re-run / Retry Discovery buttons no longer hit Postgres `42703`. Verified by re-running Aria Swan from her failed-state card.
- Fixed: 4 Next 16 sync-API regressions on `[slug]/page.tsx`, `/creators`, `/platforms/instagram/accounts`, `/platforms/tiktok/accounts` — `params` and `searchParams` are Promises in Next 15+; all four routes now await them.
- Fixed: `getProfilesForCreator` filters `is_active=true` so soft-deleted profiles disappear after Remove.
- Added: real brand icons via `react-icons/si` and FontAwesome fallbacks — Instagram, TikTok, YouTube, X (Twitter), Facebook, LinkedIn, Patreon, OnlyFans, Amazon, Telegram, Linktree. Fanvue/Fanplace/Beacons fall back to lucide.
- Added: `sortAccounts` util (`src/lib/sortAccounts.ts`) with canonical platform order — primary → social (IG/TT/YT/FB/X/LinkedIn) → monetization (OF/Patreon/Fanvue/Amazon shop/TT shop) → aggregators → messaging. Applied at the render layer; DB queries keep insertion order.
- Added: `removeAccountFromCreator` server action — soft-deletes via `is_active=false`, wired to AccountRow dropdown's Remove item with native confirm. Edit / Mark Primary / Verify Connection items hidden until backed by real implementations.
- Added: header **Add Account** button on creator detail page — replaces 4 redundant per-section "Add manually" inline buttons. Opens existing `AddAccountDialog` with the v2 manual-add discovery flow.
- Added: Brand Summary placeholder card on creator detail page (between stats strip and tabs) — signals where Phase 3 brand analysis will land (niche, archetype, vibe, monetization model, SEO keywords).
- Added: new project skill `autonomous-fix-list` (`.claude/skills/autonomous-fix-list/SKILL.md`) — companion to `autonomous-execution`. When Simon hands a fix list with a full-autonomy phrase, runs the full plan → dispatch → verify → push playbook end-to-end with zero check-ins.
- Changed: creator detail page restructure into proper brand HQ — bio stripped from header (it's account-level, not creator-level identity); tabs forced horizontal across the top (was rendering side-by-side); Re-run/Retry Discovery buttons unified into a single component with `variant: 'header' | 'failed-state'`.
- Changed: AccountRow polished — `replaceAll('_',' ')` so `link_in_bio` reads as "link in bio"; em-dash for null/0 followers instead of "0 flwrs"; relative date format ("today", "1d ago"); dropdown reduced to Remove only.
- Changed: Stats Strip "Social" sub-text now de-dupes platform names — Esmae no longer reads "instagram, twitter, instagram".
- Propagated: brand icon + label-fix patterns to `/creators` grid and `/platforms/{instagram,tiktok}/accounts` clients for project-wide consistency.
- Verified: tsc 0, pytest 102/102 throughout the pass. Walked the brand-HQ creator detail page via Chrome DevTools MCP — clean console (only known IG-CDN avatar `NotSameOrigin` blocks).
- Branch / PR: `phase-2-discovery-v2` → PR [#4](https://github.com/tommy811/The-Hub/pull/4). 7 commits this pass: `3b08376` (params await) → `6f481ff` (retry RPC cast) → `6ec3048` (brand icons + sort) → `9a3b90b` (page restructure) → `cefa808` (is_active filter) → `03b0c8a` (consistency propagation) → `93960a8` (autonomous-fix-list skill).

## 2026-04-25 (sync 11 — verification stack synced)
- Added: non-interactive ESLint flat config, aggregate `npm test`, `typecheck`, `test:py`, and `test:browser` scripts, plus a Playwright browser smoke suite for route and console coverage.
- Changed: repo runtime upgraded to Next.js 16.2.4, `src/middleware.ts` replaced with `src/proxy.ts`, `tailwind.config.js` converted to ESM, favicon wired into layout, and browser dev origins allowed for local smoke tests.
- Verified: `npm run build`, `npm run lint`, `npm run typecheck`, `npm run test:py`, `npm run test:browser`, `npm test`, and `npm audit --omit=dev` all passed.

## 2026-04-25 (sync 10 — Discovery v2 shipped)
- Shipped: PR [#4 phase-2-discovery-v2](https://github.com/tommy811/The-Hub/pull/4). Replaces the single-hop pipeline with a two-stage resolver + deterministic URL classifier + rule-cascade identity scorer + multi-platform fetcher layer + first-class `bulk_imports` job.
- Added: `pipeline/` module — `resolver.py` (two-stage: fetch seed → classify+enrich destinations), `classifier.py` (rule-first gazetteer + cached LLM fallback), `identity.py` (rule cascade + CLIP avatar tiebreak), `canonicalize.py` (URL normalization + short-URL resolution), `budget.py` (Apify cost cap).
- Added: `fetchers/` module — 9 platforms: IG + TT (Apify), YT (yt-dlp), OF (curl_cffi chrome120 JA3 impersonation), Patreon + Fanvue + generic (httpx), FB + X (stubbed for SP1.1).
- Added: `aggregators/` module — Linktree, Beacons, custom_domain (redirect chain follower).
- Added: `data/monetization_overlay.yaml` gazetteer covering ~20 platforms.
- Added: 3 new tables (`bulk_imports`, `classifier_llm_guesses`, `profile_destination_links`) — 23 tables total.
- Added: `discovery_runs.{bulk_import_id, apify_cost_cents, source}` + `profiles.discovery_reason` columns.
- Added: unique functional index `creator_merge_candidates_pair_uniq` on `(LEAST/GREATEST)` pair for idempotent merge inserts.
- Added: `run_cross_workspace_merge_pass` RPC — inverted-index dedup that fires whenever a bulk terminates.
- Changed: `commit_discovery_result` → v2 (accepts `p_discovered_urls` + `p_bulk_import_id`; source-aware canonical-field protection for `manual_add`).
- Changed: `bulk_import_creator` → v2 (returns jsonb `{bulk_import_id, creator_id, run_id}`; old 6-arg overload dropped).
- Changed: Worker passes `bulk_import_id` through to `run()`, fires merge pass when bulks terminate.
- Changed: `AddAccountDialog` gains a "Run discovery on this account" checkbox (default on); server action inserts a `source='manual_add'` discovery_run.
- Removed: `scripts/apify_details.py`, `scripts/link_in_bio.py` (shims) + their test files; content migrated to `fetchers/` and `aggregators/`.
- Fixed (mid-smoke): classifier `_cache_lookup` handles supabase-py 2.x returning `None` on `.maybe_single().execute()` cache miss (commit `48849e7`).
- Fixed (mid-smoke): `commit_discovery_result` dropped the `discovery_runs.updated_at` write (migration `20260425000200`, commit `d81e645`).
- Tests: 45 → 102 pytest green. `npx tsc --noEmit` exit 0.
- Live smoke: Natalie Vox + Esmae re-discovered cleanly (4–7 profiles, 5–8 destination_links, 3–6 funnel_edges each); Aria Swan correctly failed-fast with `empty_context:`. 48¢ total Apify spend.

## 2026-04-24 (sync 9 — Phase 2 discovery rebuild + schema migration both merged)
- Merged: PR #2 (`phase-2-discovery-rebuild`) — discovery pipeline rewritten on Apify-grounded context; Linktree/Beacons resolver; grounded Gemini prompt; `edge_type` enum + funnel_edges creator_id fix; pytest scaffolding; 45 tests; dead-letter replay script.
- Merged: PR #3 (`phase-2-schema-migration`) — rebased onto main after PR #2; `trends` + `creator_label_assignments` tables; `trend_type` / `llm_model` / `content_archetype` enums; `creator_niche` on `label_type`; `archetype`+`vibe` moved to creators; `scraped_content.trend_id` FK.
- Changed: Phase 2 status on Home + Phase Roadmap — discovery rebuild now ✅, schema migration ✅; remaining Phase 2 work is scraping ingestion + trends linking + `quality_flag` on `scraped_content`.
- Added: Migration Log entries for `20260424150000_create_edge_type_enum` and `20260424160000_fix_funnel_edges_creator_id` (were live but not documented in vault).

## 2026-04-24 (sync 8 — Phase 2 schema migration)
- Added: `trends` table + `trend_type` enum (audio / dance / lipsync / transition / meme / challenge)
- Added: `creator_label_assignments` table (mirrors `content_label_assignments`, reuses `increment_label_usage` trigger)
- Added: `llm_model` enum (gemini_pro / gemini_flash / claude_opus / claude_sonnet) — reserved for analysis pipelines
- Added: `content_archetype` enum (12 Jungian values — was documented but missing from DB; audit gap closed)
- Added: `creator_niche` value on `label_type` enum
- Added: `creators.archetype` (content_archetype, nullable) and `creators.vibe` (content_vibe, nullable) — filled by Phase 3 brand analysis
- Added: `scraped_content.trend_id` FK → `trends` (nullable, ON DELETE SET NULL)
- Added: Migration `20260424000001_bulk_import_creator_rpc` — atomic RPC for creator + primary profile + pending discovery_run insert
- Added: Migration `20260424000000_consolidate_last_discovery_run_id` — drift fix; single `last_discovery_run_id` column with FK
- Removed: `archetype` and `vibe` columns on `content_analysis` (table was empty — moved to creator level)
- Removed: stale `Schema drift — live vs PROJECT_STATE` memory entry (drift fully resolved; `docs/SCHEMA.md` footer is authoritative)
- Changed: `.gitignore` — added `supabase/.temp/` (CLI runtime cache)
- Changed: Total live tables 18 → 20
- Changed: PROJECT_STATE §4.1/§4.2/§5/§14/Decisions Log — all updated
- PR: [tommy811/The-Hub#3](https://github.com/tommy811/The-Hub/pull/3) — `phase-2-schema-migration`

## 2026-04-23 (sync 7 — Phase 1 close + vault merge)
- Added: `verify-and-fix` skill (`.claude/skills/verify-and-fix/SKILL.md`) — post-change verification loop, up to 3 iterations, escalates to session note on exhaustion. Phase 1 agent requirement met.
- Changed: Phase 1 status → fully closed (feature work + required agents both complete)
- Changed: Vault merged into repo — single folder at `/Users/simon/OS/Living VAULT/Content OS/The Hub`. No separate vault path, no mirroring.
- Removed: `02-Architecture/PROJECT_STATE.md` mirror (redundant — repo root copy is the only copy)
- Changed: `.gitignore` — added Obsidian workspace files and `.claude/settings.local.json`
- Changed: `00-Meta/How This Vault Works.md` — rewritten to single-folder framing
- Changed: `sync-project-state` SKILL.md — removed mirror step, updated commit path
- Changed: `00-Meta/Stack & Tools.md` — corrected vault/repo path references, added verify-and-fix to skills table
- Fixed: All `[[02-Architecture/PROJECT_STATE...]]` wiki-links → `[[PROJECT_STATE...]]` across 7 files
- Validated: Stop hook end-to-end (typecheck failure blocks stop, clean code allows it)

## 2026-04-23 (sync 6 — agent architecture integration)
- Added: Agent architecture §15–§19 to PROJECT_STATE.md (replacing §15 Agent Roadmap stub)
- Added: 04-Pipeline/Agent Catalog.md with operational entries for all planned agents
- Installed: superpowers, chrome-devtools-mcp, playwright-mcp, apify-mcp, supabase-mcp (read-only), anthropics/skills
- Created: .claude/agents/verifier.md subagent (read-only tools, structured pass/fail output)
- Created: .claude/hooks/verify-before-stop.sh Stop hook
- Updated: .claude/settings.json with Stop hook registration
- Created: CLAUDE.md with verification protocol
- Updated: scripts/.env.example with Sentry, Slack, and Apify webhook vars
- Updated: Stack & Tools.md — superpowers and webapp-testing added to skills table
- Updated: PROJECT_STATE.md §13 — agent dir path updated to .claude/agents/, reference updated to §15–§19

## 2026-04-23 (agent roadmap)
- Added: §15 Agent Roadmap in PROJECT_STATE.md — formal table of 8 agents across Phases 1–4 + ongoing
- Added: Required Agents column in Full Product Vision module map — every module now lists its agents
- Added: Per-phase Required Agents subsections in Phase Roadmap — each phase has explicit agent completion criteria
- Added: Agent Backlog section at top of Feature Backlog — 8 agents listed, verify-and-fix marked as Phase 1 blocking
- Added: Workflow patterns #7, #8, #9 in Stack & Tools (schema-first/agent-last, agents as deliverables, verify before done)
- Added: Planned agents note in Stack & Tools Claude Code Skills section
- Added: Principle #10 in Stack & Tools project principles (agents are phase deliverables)
- Added: 04-Pipeline/Agent Catalog.md — new file with full spec for all 8 planned agents including workflows, triggers, escalation rules, design principles
- Added: Cross-Module Decision #9 in Full Product Vision (every phase ships with its agents)
- Added: Agent development cadence line in PROJECT_STATE.md §13 Development Workflow
- Changed: Phase 1 status in Phase Roadmap — marked "feature work complete" with ⚠️ note that verify-and-fix is still blocking full phase close
- Decision: Phases close only when required agents are built + validated. verify-and-fix is next build.

## 2026-04-23 (sync 5)
- Added: `AvatarWithFallback.tsx` — client component with `onError` → gradient monogram fallback. Fixes silent blank when Instagram CDN URLs expire. Used on creator cards + detail page.
- Added: `AddAccountDialog.tsx` — manual add account dialog. 18 platforms grouped (Social / Monetization / Link-in-Bio / Messaging / Other). Auto-sets account_type from platform selection. Wired to `addProfileToCreator` server action.
- Added: `RerunDiscoveryButton.tsx` — wired Re-run Discovery button. Calls `rerunCreatorDiscovery` server action → `retry_creator_discovery` RPC.
- Changed: Creator detail page (`/creators/[slug]`) — full revamp. Stats strip (Total Reach, Social count, Monetization count, Link-in-Bio count), bio from primary profile, network sections with icons, avatar fallback, fetches `bio`/`following_count`/`post_count` from profiles.
- Changed: `creators/page.tsx` — real follower count aggregation, account type breakdown per creator card, `totalFollowers` computed from social profiles.
- Fixed: Apify field names in `apify_scraper.py` — `followersCount` (not `ownerFollowers`), `profilePicUrl` (not `ownerProfilePicUrl`), `biography`, `followsCount`, `postsCount`, `ownerFullName`, `metaData` fallback. Follower counts now populate correctly.
- Fixed: `retry_creator_discovery` RPC — now copies `input_handle` + `input_platform_hint` so retry runs have context to work with.
- Fixed: `commit_discovery_result` RPC — `NULLIF` guard prevents "Unknown" from overwriting valid canonical_name.
- Fixed: `AccountRow.tsx` — hydration error from `toLocaleDateString()` → deterministic `toISOString().slice(0, 10)`.
- Known: Instagram CDN avatar URLs expire. `onError` degrades gracefully to gradient monogram. Full fix requires re-scraping or proxying to Supabase Storage.
- Known: Discovery pipeline `httpx.get()` is blocked by Instagram. Gemini fishnet does not work until discover_creator.py is rebuilt on Apify `resultsType: "details"`. Documented in §15 Known Limitations.

## 2026-04-23 (sync 4)
- Added: `/platforms/tiktok/accounts` wired to live Supabase — Server Component + `TikTokAccountsClient.tsx`, mirrors Instagram pattern exactly (platform=tiktok, account_type=social)
- Added: `supabase/migrations/20260423000000_add_is_primary_to_profiles.sql` — `is_primary BOOLEAN DEFAULT FALSE` on profiles (required by `commit_discovery_result` RPC)
- Fixed: Discovery pipeline end-to-end — Gemini 2.5 Flash schema compatibility (strip minimum/maximum/anyOf), monetization_model normalization, dependency conflict resolved
- Fixed: All 3 initial creators (Natalie Vox, Aria Swan, Esmae) discovered and in `ready` state; 10 posts scraped via Apify
- Changed: Gemini model in use updated from `gemini-1.5-pro` → `gemini-2.5-flash` (1.5-pro deprecated)
- Changed: `creators/page.tsx` and `page.tsx` (dashboard) marked `force-dynamic` to prevent stale server cache

## 2026-04-23 (sync 3)
- Added: `/platforms/instagram/accounts` wired to live Supabase — Server Component fetches `profiles` (platform=instagram, account_type=social), joins `profile_scores`, `profile_metrics_snapshots`, `scraped_content`; client component handles tracking tab (URL), rank chips, search, sort, stat cards
- Added: `InstagramAccountsClient.tsx` — new client component for IG accounts filtering/sorting
- Changed: `AccountCard` — removed `fanArchetype`, `archetype`, `vibe`, `category` props; added `isUnlinked` badge; nullable `rank`/`score`/`avatarUrl`
- Changed: `StatCardRow` — now accepts live props (total, withContent, avgFollowers, llmScored) instead of hardcoded mock values
- Changed: `TikTok accounts page` — updated to new component signatures (still placeholder mock data)

## 2026-04-23 (additional)
- Added: Stack & Tools.md (00-Meta/) — complete tool/service/skill/MCP/workflow reference
- Added: sync-project-state skill (.claude/skills/sync-project-state/SKILL.md)
- Added: Stack & Tools quick link to Home.md
- Fixed: table count (20 → 18) in PROJECT_STATE.md, mirror, and Phase Roadmap

## 2026-04-23
- Full repo + vault audit completed
- Applied all audit fixes: RPC param prefix bug, invalid `scored` enum value, outlier threshold copy (2x→3×), orphan script deleted
- Added `outlier_multiplier` column migration + rewrote `flag_outliers` RPC
- Added patreon to platforms.ts
- Rewrote README.md from AI Studio boilerplate to real project README
- Added §15 Known Limitations to PROJECT_STATE.md
- All reference docs updated: Enum Reference, RPC Reference, Migration Log, Entity Relationships
- Full Product Vision.md added (all 9 modules)
- Phase 1 marked complete across all docs

## 2026-04-22
- Vault created
- Initial schema applied to Supabase (Content OS)
- Creator layer migration applied
- Phase 1 AI Studio prompt generated
