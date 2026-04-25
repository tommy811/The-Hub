# Highlights v1 — Funnel-only Design (2026-04-25)

> Builds on: recursive funnel resolution (`docs/superpowers/specs/2026-04-24-discovery-v2-design.md`, `docs/superpowers/plans/2026-04-25-recursive-funnel-resolution.md`).
> Defers to v2 (separate spec): persistent media storage, downloadable assets, UI tab, scheduled refresh worker.
> Scope envelope: `docs/superpowers/specs/2026-04-25-highlights-tier-decision.md`.

## Goal

Some IG profiles park their CTAs in **highlights** — pinned story collections — instead of in their bio. A profile with empty `bio` and zero `external_urls` may still have an "OF" or "LINKS" highlight with a clickable link sticker pointing to OnlyFans, a custom domain, or another social. Today the resolver never sees these, so its discovery output is incomplete for highlight-driven creators. v1 closes that gap by scraping each newly-enriched IG profile's highlights, extracting (link sticker URLs + caption-mentioned handles), and feeding them through the same `_classify_and_enrich` recursion the funnel work just shipped — no new tables, no UI, no scheduled refresh. v2 (separate spec) layers persistent media storage and a Highlights tab on top of the same scrape.

## Architecture

The recursive funnel work added `_expand(ctx, depth)` — one method that, given an enriched profile context, loops over its `external_urls` and (for `depth ≥ 1` IG profiles) Gemini-extracted bio mentions, feeding each surfaced URL into `_classify_and_enrich`. v1 adds a **third source** to that same loop: highlight-surfaced URLs.

```
                       resolve_seed
                            │
           ┌────────────────┴────────────────┐
           ▼                                  ▼
       fetch_seed (depth=0)        run_gemini_discovery_v2
           │                                  │
           ▼                                  │
        _expand(seed_ctx, 0)                  │
           │                                  │
           ▼                                  ▼
      external_urls           text_mentions (depth=1)
           │                                  │
           └──────► _classify_and_enrich ◄────┘
                            │
                  ┌─────────┴─────────┐
                  ▼                   ▼
            (aggregator)         (profile)
                                       │
                                       ▼
                                fetcher(handle)  ── ctx
                                       │
                                       ▼
                                _expand(ctx, depth)         ◄─── recursion
                                       │
            ┌──────────────────────────┼──────────────────────────┐
            ▼                          ▼                          ▼
       external_urls       bio_mentions (Gemini)        ★ highlights ★  ◄── NEW
            │                          │                          │
            └──────────► _classify_and_enrich ◄───────────────────┘
```

The highlights branch fires **only** when:
1. The current ctx is an IG profile (`ctx.platform == "instagram"`).
2. `depth >= 1` — i.e. the ctx is a secondary, not the seed. The seed already gets the full Gemini canonicalization pass which includes its own bio + external_urls + posts; highlights for the seed land in v2 where they have a UI home.
3. `HIGHLIGHTS_ENABLED` env flag is on (default ON).
4. The budget can afford the highlights-scrape cost.

The highlights fetcher returns `list[HighlightLink]`, each carrying a URL plus a `source` discriminator (`highlight_link_sticker` vs `highlight_caption_mention`). The resolver synthesizes a canonical URL for each (already-canonical for link stickers; synthesized for handle mentions via `_synthesize_url` — the same helper used for bio mentions) and calls `_classify_and_enrich(synth, depth=depth+1)`. Anything that lands in `discovered_urls` flows through the existing `commit_discovery_result` RPC into `profile_destination_links` / `profiles` automatically — **no new tables, no schema changes**.

## Components

| File | Action | Responsibility |
|---|---|---|
| `scripts/schemas.py` | Modify | Add `HighlightLink` Pydantic model. |
| `scripts/fetchers/instagram_highlights.py` | Create | `fetch_highlights(client, handle) -> list[HighlightLink]`. Wraps `apify/instagram-scraper` in `stories` mode, parses `story_link_stickers[].url` and `mentions[]` from each item, deduplicates within the run, returns `[]` on any error. Mirrors `instagram.py` style — tenacity retry on transient errors, structured Pydantic return. |
| `scripts/pipeline/resolver.py` | Modify | Add `HIGHLIGHTS_ENABLED` env flag, add `fetch_highlights` wrapper for test-patching, call into `_expand` for IG depth ≥ 1 profiles. Track separate budget cost for highlights. |
| `scripts/tests/fetchers/test_instagram_highlights.py` | Create | Unit tests for the new fetcher (mocked Apify client). |
| `scripts/tests/pipeline/test_resolver_recursive.py` | Modify | Append integration tests for the resolver wiring (highlights-surfaced URLs land in `discovered_urls`, flag-off skips the call, fetcher failure returns gracefully). |

No DB migration. No UI changes. No new TS. The 122-test pytest baseline plus the new tests must remain green.

## Data flow

1. `_expand(ctx, depth)` is called with an enriched IG ctx at `depth >= 1`.
2. `external_urls` and bio-mentions branches run as today.
3. New branch: if `ctx.platform == "instagram"` and `HIGHLIGHTS_ENABLED` and `budget.can_afford(HIGHLIGHTS_COST_CENTS)`:
   a. `budget.debit("apify/instagram-scraper-stories", HIGHLIGHTS_COST_CENTS)`
   b. `links = fetch_highlights(apify_client, ctx.handle)` — wrapped in `try/except`, returns `[]` on any error.
   c. For each `HighlightLink`:
      - If `source == "highlight_link_sticker"`: `_classify_and_enrich(link.url, depth=depth+1)` directly — link sticker URLs are already absolute.
      - If `source == "highlight_caption_mention"`: synthesize a canonical URL via the existing `_synthesize_url(TextMention)` helper. (We reuse the helper by constructing a `TextMention(platform=link.platform, handle=link.handle, source="enriched_bio")` shim — the source field semantically lies but the helper only cares about platform+handle.)
4. `_classify_and_enrich` deduplicates against `visited_canonical` (same set used by external_urls and bio_mentions), records each new URL in `discovered` with `depth=depth+1`, and recurses into the resulting ctx if it's a fetchable profile.
5. `commit_discovery_result` RPC writes `discovered_urls` to `profile_destination_links` and surfaces the corresponding `accounts` rows on the HQ page — exactly the same path as today.

`HighlightLink.source` is a logical attribution. It is NOT stored anywhere yet (v1 has no new tables). It exists for two reasons: (a) the resolver needs to know whether to dispatch to `_classify_and_enrich` directly (link sticker → already a URL) or via `_synthesize_url` (caption mention → handle only); (b) v2 will persist it as `discovery_reason`.

## Cost model

- **Per-profile cost:** `apify/instagram-scraper` with `resultsType: "stories"` is priced at "from $1.00 / 1,000 result items." A typical creator with ~10 highlights × ~5 items per highlight = ~50 items, plus a per-username startup fee. **Conservative estimate: 5 cents per highlights scrape.** Codified as `HIGHLIGHTS_COST_CENTS = 5` in the resolver, hand-maintained alongside `_APIFY_COSTS` (err on the high side per existing convention).
- **Budget gating:** `budget.can_afford(HIGHLIGHTS_COST_CENTS)` is checked **before** the call. If insufficient, the highlights branch is skipped silently — same pattern as profile enrichment. The existing `BudgetTracker` cap (default `cap_cents=1000` per discovery run) absorbs the worst case (~20 highlights scrapes per run = $1.00, never exceeded in practice because depth-1 IG profile count rarely passes 4–5).
- **Net delta vs. recursive funnel only:** in the worst case where every depth-1 IG profile has highlights, +5 cents × N secondaries = ~25 cents. Well within the existing $1 cap.
- **Kill switch:** `DISCOVERY_HIGHLIGHTS_ENABLED=0` short-circuits the entire branch — no Apify call, no budget debit. Defaults to `1` (ON). Composable with `DISCOVERY_RECURSIVE_GEMINI` — they're independent flags.

## Failure modes

| Scenario | Behavior |
|---|---|
| Apify call raises `EmptyDatasetError` (private profile, no highlights, login wall) | `fetch_highlights` returns `[]`. Resolver continues with external_urls + bio_mentions. No exception leaks. |
| Apify call raises a generic exception (timeout, schema crash) | `fetch_highlights` catches in its top-level `except Exception`, logs `[yellow]highlights extraction failed: ...[/yellow]`, returns `[]`. Same pattern as `run_gemini_bio_mentions`. |
| Budget exhausted mid-run | `budget.can_afford(HIGHLIGHTS_COST_CENTS)` returns False before the call. Highlights branch skipped silently. |
| `BudgetExhaustedError` raised by `_classify_and_enrich` while iterating the returned links | Caught in `_expand`'s existing `try/except BudgetExhaustedError`, function returns cleanly. |
| Highlights-surfaced URL points to a cycle (e.g. the seed) | Existing `visited_canonical` dedup catches it — same protection as external_urls and bio_mentions. |
| Highlight has no link sticker AND no caption mention extracted by Gemini (image-only with logo overlay) | We do NOT use vision-LLM in v1. The highlight contributes nothing. Documented limitation deferred to v2 / a future "vision-OCR" task. |
| Rate-limited (429) | Tenacity retries 3× with exponential backoff inside `_call_actor`, same as the details fetcher. After exhaustion, returns `[]` (logged warning). |
| Apify actor returns highlights but with a different shape than expected (Instagram changed their internal API) | The fetcher's parser tolerates missing fields (`item.get("story_link_stickers") or []`). Each malformed item is silently skipped. Worst case: `[]`. |

**Triple-bound runaway protection** (mirrors the recursive funnel's quadruple-bound):
1. `visited_canonical` cycle dedup — same set, all branches.
2. `BudgetTracker` cap — `can_afford` check before every Apify call.
3. `MAX_DEPTH=6` — `_classify_and_enrich` early-returns when `depth > MAX_DEPTH`.
4. **NEW:** `DISCOVERY_HIGHLIGHTS_ENABLED=0` — operator kill switch for emergency rollback.

## Testing strategy

Three layers, all in CI:

1. **Unit (fetcher mock)** — `scripts/tests/fetchers/test_instagram_highlights.py`:
   - `fetch_highlights` parses link stickers from a synthetic Apify dataset.
   - Empty dataset returns `[]` (not raises).
   - Items without `story_link_stickers` and without `mentions` are silently skipped.
   - Items with multiple link stickers all surface.
   - Tenacity wrapper retries on transient errors (regex-matched).

2. **Integration (resolver-level mock chain)** — append to `scripts/tests/pipeline/test_resolver_recursive.py`:
   - `test_highlight_link_sticker_lands_in_discovered_urls` — depth-1 IG profile returns a highlight with an OnlyFans link sticker. URL appears in `result.discovered_urls` at depth 2.
   - `test_highlight_caption_mention_synthesized_and_followed` — depth-1 IG profile returns a highlight with `mentions=["sec_tt"]`. The synthesized `https://tiktok.com/@sec_tt` lands in `discovered_urls`.
   - `test_highlights_skipped_when_flag_off` — `monkeypatch.setattr("pipeline.resolver.HIGHLIGHTS_ENABLED", False)`. Mock for `fetch_highlights` is never called.
   - `test_highlights_failure_returns_gracefully` — `fetch_highlights` raises; resolver completes, `discovered_urls` still contains the external_urls / bio_mentions branches.
   - `test_highlights_skipped_when_budget_exhausted` — budget cap forces the highlights branch to skip; resolver completes cleanly.
   - `test_highlights_not_called_for_seed` — depth-0 ctx never triggers highlights; `fetch_highlights` mock has zero calls.
   - `test_highlights_not_called_for_non_ig_secondary` — depth-1 TikTok or OnlyFans ctx does not trigger highlights.

3. **Live smoke** — manual one-shot at v1 ship time, on a real creator known to use highlights for their CTAs (e.g. `@esmae` or another from the manual list — check the recursive funnel session note for known highlights-heavy creators). Verifies the assumption that `apify/instagram-scraper` `resultsType: "stories"` actually returns pinned highlights (not just live stories) AND that `story_link_stickers[].url` is populated. **If the smoke shows highlights are not returned: BLOCKED — escalate to Simon to evaluate `louisdeconinck/instagram-highlights-scraper` as a fallback** (which has `mentions` but no documented link sticker output, reducing v1 to caption-mention-only).

## Out of scope (deferred to v2)

- New tables `highlights` and `highlight_items`.
- Supabase Storage bucket for highlight covers + story media downloads.
- Creator HQ "Highlights" tab — grid of reels, click-through, per-item download.
- Scheduled worker `scripts/scrape_highlights.py` refreshing weekly.
- Vision-LLM extraction of CTAs from story image overlays (no link sticker, no caption — needs OCR). Some creators put plain text "OF: @kira_of" as a graphic overlay with no clickable element; we can't extract that without vision.
- Non-IG platforms — TikTok and YouTube don't have a highlights primitive in the same shape. (TikTok's "Featured" videos and YouTube's "About" links are covered by existing fetchers.)
- Surfacing highlights for the seed itself. Seed gets the full Gemini canonicalization which catches its own bio + posts. Highlights for the seed lands in v2 where there's a UI to display them.
