# Highlights Tier — Scope Decision (2026-04-25)

> Short decision record. Detailed designs land in their own specs (v1 and v2) at brainstorm time.

## The 3-tier scraping model

| Tier | Scope | Cadence | Apify cost | Purpose |
|---|---|---|---|---|
| **Discovery** (today) | Profile bio + external_urls | Per Re-run Discovery | ~$0.10 | Funnel resolution |
| **Highlights** (this decision) | Highlight reels + story media + link stickers + caption mentions | Per new IG profile + scheduled refresh | ~$0.05–0.15 | (a) Surface CTAs the bio doesn't show — closes the funnel-completeness gap (b) First-class browseable media in the app |
| **Content** (Phase 2 §14 #9, planned) | Last 50–100 posts | Every 12h cron | ~$0.30–0.50 | Outlier detection, trends |

Highlights bridges Discovery and Content — same Apify actor (`apify/instagram-scraper`), different mode. It serves two needs that share a scrape but diverge on storage and presentation.

## Architecture: Hybrid (Option C)

Considered three architectures:

- A. **Inline with discovery** — fetch highlights in the same flow. Doubles Apify cost on every Re-run; blocks the user.
- B. **Fully decoupled cron** — scheduled only. CTA gap stays open until the next cycle.
- **C. Hybrid (chosen)** — discovery commits as today; an async highlights job is queued for each newly-enriched IG profile. When it completes, it (1) persists highlights/items/media (v2) and (2) feeds new link stickers + caption mentions back into the same `_classify_and_enrich` loop as a delta-discovery pass, raising new accounts/merge candidates. A scheduled worker refreshes highlights for tracked profiles weekly. UI shows them whenever present.

C keeps discovery snappy, closes the CTA gap shortly after, and gives us the scheduled refresh path the content tier will also need.

## Phasing: Sequenced (Option C)

Two slices, sequenced for fastest functional wins:

### v1 — Funnel-only (~3 days work after recursive funnel ships)

**Scope:**
- Scrape highlights once per newly-enriched IG profile (async after discovery commits)
- Extract link stickers + Gemini-extracted caption mentions
- Feed into `_classify_and_enrich` at depth = source profile depth + 1 (composes with the recursive-funnel work)
- No new tables — write extracted URLs/mentions back through the existing `discovered_urls` / `profile_destination_links` plumbing
- No UI changes

**Deliverable:** Closes the gap where IG profiles park their CTAs in highlights instead of bios.

### v2 — Content storage + UI (~1.5–2 weeks)

**Scope:**
- New tables: `highlights` (per profile) + `highlight_items` (per story)
- Supabase Storage bucket `creator-media` with media download pipeline
- Default download policy: cover image eagerly, video on demand (configurable)
- Creator HQ "Highlights" tab — grid of reels, click-through to story items, per-item download
- Scheduled worker `scripts/scrape_highlights.py` refreshing weekly for tracked profiles

**Deliverable:** First-class browseable highlights library. Operators can save assets to the workspace.

## Autonomous execution queue (decided 2026-04-25)

1. **Recursive funnel** — already specced (`docs/superpowers/plans/2026-04-25-recursive-funnel-resolution.md`). Executes first via subagent-driven-development.
2. **Highlights v1** — brainstorm → spec → plan → execute autonomously. Builds on recursive funnel's `_classify_and_enrich` recursion.
3. **Highlights v2** — brainstorm → spec → plan → execute autonomously. UI choices made tastefully against existing shadcn + web-design-guidelines patterns.

Each slice gets its own design doc + plan. This file only records the scope/architecture/phasing decision.

## Why this phasing

- **Funnel-only ships in days**, closing the immediate completeness gap. The user starts benefiting before the bigger build lands.
- **Content storage ships next** because it's substantially larger (schema + storage + UI) and benefits from the proven scrape pipeline established in v1.
- **Recursive funnel ships first** because it's already designed, depth-aware `_classify_and_enrich` is the foundation that v1 layers on top of, and it works without highlights — they compose.
