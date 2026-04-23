# Full Product Vision — The Hub

**Last updated:** 2026-04-23
**Purpose:** The complete feature scope. Every module, every planned capability, every decision made about what The Hub is and isn't.

> This is the umbrella. Use it to remember what you're building toward when the day-to-day of Phase 2 makes you lose sight of Phase 7.

---

## The Premise

The Hub is an internal tool for a creator management agency (2–5 person team, single workspace, no client logins). The Creator is the source of truth — every module orbits around the creator entity and the relational graph of everything they own and do online.

Build order is guided by one principle: **what makes the app most useful today without constraining what's possible tomorrow.**

---

## Module Map

The Hub contains nine modules. Each phase's required agents are listed — a phase does not close until its agents are built and validated.

| # | Module | Status | Phase | Required Agents |
|---|---|---|---|---|
| 1 | **Creator Intelligence** | ✅ Built | Phase 1 | verify-and-fix (🔜 pending) |
| 2 | **Platform Intelligence** | 🟡 Partial (UI scaffolded, data mock) | Phase 2 | schema drift watchdog, scrape-verify |
| 3 | **Content Intelligence** | ⬜ Planned | Phase 2–3 | scrape-verify |
| 4 | **Trends & Audio** | ⬜ Planned | Phase 2–3 | — |
| 5 | **Brand Analysis & SEO** | ⬜ Planned | Phase 3 | brand analysis |
| 6 | **Classification & Taxonomy** | ⬜ Planned | Phase 3 | label deduplication |
| 7 | **Funnel & Monetization** | ⬜ Planned | Phase 4 | funnel inference |
| 8 | **Trends, Alerts & Signals** | 🟡 UI mock | Ongoing | — |
| 9 | **Agency Operations (future umbrella)** | ⬜ Ideas only | Future | — |

---

## Module 1 — Creator Intelligence ✅

**What it does:** Ingest creator handles, auto-discover their full digital network, maintain the relational graph, detect and resolve cross-platform identity collisions.

### Built
- Bulk-import modal with live handle parser (URL, prefix syntax, trailing hints)
- Insert-first pattern — cards appear in Processing state immediately
- Gemini discovery pipeline (fishnet across social + monetization + link-in-bio + messaging)
- `commit_discovery_result` transactional RPC
- Three card states with Realtime transitions (Processing / Ready / Failed)
- Creator deep-dive with Network tab showing all linked accounts grouped by `account_type`
- Cross-platform identity resolution: `known_usernames[]`, handle similarity via `rapidfuzz`, `creator_merge_candidates` with human review
- Tracking-type taxonomy (managed, inspiration, competitor, candidate, hybrid_ai, coach, unreviewed)

### Planned enhancements
- **Re-run discovery** button per creator (when they add new accounts / rebrand)
- **Manual add account** with automatic data fetch (platform + handle → system pulls bio + follower count before inserting)
- **Persona filtering within a creator** via tags on accounts (no new schema — use existing `tags[]` on profiles). Example: one creator runs fitness + fashion niches, each with different handles → tag accounts, filter Network tab by tag.
- **Multi-persona creator board** — single view showing how all personas feed traffic into shared monetization assets
- **Merge candidate auto-resolution agent** (Phase 3+): Claude agent reviews high-confidence candidates, auto-merges when ≥ threshold, only surfaces ambiguous cases for human review

---

## Module 2 — Platform Intelligence 🟡

**What it does:** Per-platform account view. Scrape content, surface winning content, manage classification, show analytics.

Four sub-tabs per platform (current convention):
- **Accounts** — grid of all creator accounts on that platform
- **Outliers** — posts flagged as high-performers
- **Classification** — taxonomy curation for this platform's content
- **Analytics** — aggregate stats across all accounts on this platform

### V1 platforms
Instagram + TikTok.

### Built
- `/platforms/instagram/accounts` with stat cards, tracking tab bar, rank filter chips, card grid (**mock data**)
- `/platforms/tiktok/accounts` mirror (**mock data**)
- Sub-tab routes exist as placeholders
- `RankBadge` component (6 tiers: diamond → plastic)
- `AccountCard` with dropdown (archive, scrape, edit)

### Phase 2 build
- **Apify scraping pipeline** per platform
  - Instagram: `apify/instagram-scraper` — posts, reels, story highlights
  - TikTok: `clockworks/tiktok-scraper` — videos, profile metadata
- **Normalizer modules** (`scripts/normalize_instagram.py`, `scripts/normalize_tiktok.py`) — exact raw-field → column mapping. See [[Apify Field Mappings]].
- **Store everything** — every Apify datapoint goes into `platform_metrics` jsonb; full raw payload into `raw_apify_payload`. Nothing discarded.
- **Scraping controls**
  - Default: last 50 posts OR last 90 days (whichever smaller)
  - Default cadence: manual trigger in Phase 2, scheduled cron in Phase 3
  - Re-scrape refreshes metrics on existing posts via upsert — never duplicates
- **Media references** — store original platform URLs for video/audio (not downloadable MP4s, not MP3s — the actual IG/TikTok links so we can download ad-hoc if needed)
- **Story highlights** — scrape and store in same `scraped_content` with `post_type = 'story_highlight'`
- **Wire Accounts page to live data** — remove mocks, use real queries
- **Outliers page** — card grid sorted by `outlier_multiplier`, filtered by `is_outlier = true`
- **Classification page** — taxonomy management for this platform (see Module 6)
- **Analytics page** — aggregate charts, follower growth, engagement rate trends

### Outlier logic
`outlier_multiplier = current_views / median(last_50_posts)`. 48h post-age floor. 15-post minimum before flagging. Multiplier ≥ 3.0 flags `is_outlier = true`. Full detail in [[PROJECT_STATE#9. Outlier Detection Logic|PROJECT_STATE § 9]].

### Future platforms (Phase 2+)
YouTube, Facebook Page. Each gets its own normalizer. Platform enum already supports them.

---

## Module 3 — Content Intelligence ⬜

**What it does:** AI-score every piece of content, surface patterns, enable search by category/trend/style/niche.

### Phase 3 build
- **Gemini content analysis pipeline**
  - Input: post URL + caption + platform_metrics (audio info, hashtags)
  - Output: `quality_score`, `category`, `visual_tags[]`, dynamic labels
  - Stored in `content_analysis`
- **What gets tagged per post:**
  - **Category** (enum) — comedy_entertainment, fashion_style, fitness, lifestyle, beauty, etc. One per post.
  - **Dynamic labels** (from `content_labels` table, `label_type` enum):
    - `content_format` — GRWM, vlog, tutorial, sketch, unboxing, challenge, reaction, Q&A
    - `trend_pattern` — glow-up-transition, POV-trend, meme-format-X
    - `hook_style` — cold-open, question-hook, shock-opener, countdown (mostly used for future YT/ads analysis)
    - `visual_style` — minimalist, cinematic, raw-handheld, studio-lit, UGC-style
  - **Visual tags** (free-form array) — "beach setting", "gold jewelry", "morning light"
  - **Trend link** — if content matches a known trend, link via `scraped_content.trend_id`
- **Quality score formula** — Gemini assigns 0–100 based on: hook strength, visual quality, caption craft, engagement-normalized performance
- **Profile scores auto-refresh** — `refresh_profile_score()` called after each analysis batch → updates `profile_scores` → rank tier updates live
- **Content detail drawer** — clicking any post opens full Gemini analysis: score, labels, tags, transcription if available, direct link to original

### Creator-level vs content-level classification
**Creator-level (lives on `creators`):**
- `archetype` (Jungian 12) — determined by brand analysis across full body of work
- `vibe` — determined by brand analysis
- `niche_tags[]` — via `creator_label_assignments` + `content_labels` with `label_type = 'creator_niche'`
- `primary_niche` (free-form text for descriptive nuance)

**Content-level (lives on `scraped_content` / `content_analysis`):**
- `category` (enum)
- Dynamic labels (content_format, trend_pattern, hook_style, visual_style)
- `visual_tags[]`
- `trend_id` (nullable)

**Rationale:** archetype and vibe describe the creator's brand. A single post doesn't carry a vibe — the creator does. This classification split is enforced by the Phase 2 migration.

---

## Module 4 — Trends & Audio ⬜

**What it does:** Track trends across platforms with one source of truth. An audio or visual trend that appears on IG and TikTok is ONE trend, not two.

### Phase 2 build
- **`trends` table** (one row per canonical trend)
  - `name`, `trend_type` (audio, dance, lipsync, transition, meme, challenge)
  - `audio_signature` (normalized: `"espresso-sabrina-carpenter"`)
  - `audio_artist`, `audio_title`
  - `usage_count`, `peak_detected_at`, `is_canonical`
- **Audio metadata is already in `platform_metrics`** — Apify gives us `musicInfo` (IG) and `musicMeta` (TikTok) as text fields. No actual audio fingerprinting needed.
- **During content analysis:**
  1. Read music metadata from `platform_metrics`
  2. Normalize `artist + title` → `audio_signature`
  3. Check if signature exists in `trends` — link via `scraped_content.trend_id` or create new
- **Team reviews new trends** in a Trends management tab — promote to canonical, merge duplicates, adjust `trend_type`
- **Cross-platform queries unlocked:**
  - "All creators using Espresso audio"
  - "Every goth creator who did the glow-up-transition trend"
  - "Top 10 trending audios this week by usage_count growth"

### What we're NOT doing
- Not fingerprinting audio (Shazam-style) — not needed, Apify text metadata is enough
- Not scraping audio files — we only store the original platform URLs
- Not attempting to detect trends from raw video content (too unreliable)

---

## Module 5 — Brand Analysis & SEO ⬜

**What it does:** Produce a deep, structured brand report for each creator covering niche, USP, SEO posture, and funnel strategy.

### Phase 3 build
- **Claude-driven brand analysis skill** (multi-step agent, not monolithic prompt)
  - Reads the creator's bio, link-in-bio destinations, top-performing content captions, all hashtags used
  - Analyzes SEO: keyword density, discoverability signals, hashtag strategy
  - Produces 3–5 `brand_keywords` + 3–5 `seo_keywords`
  - Writes `niche_summary`, `usp` (unique selling proposition), `monetization_summary`
  - Proposes creator-level `archetype`, `vibe`, `niche_tags[]`
  - Stored in `creator_brand_analyses` with versioned `version` column
- **Triggered re-analysis** — every time a new platform is scraped for a creator, the brand analysis can be re-run with the expanded context. Each run creates a new `version` row so history is preserved.
- **Label-first approach** — Claude picks from the existing `content_labels` (`label_type = 'creator_niche'`) list before creating new labels. If no existing label fits, creates new with `is_canonical = false` — team promotes to canonical in Classification tab.
- **Funnel map snapshot** — brand analysis includes a JSONB snapshot of the creator's funnel at that moment (which accounts feed which monetization destinations)
- **Brand tab on creator deep-dive** — renders the latest brand analysis report

### What this enables
- Filter `/creators?niche=goth` → all goth creators
- Cross-reference: "all goth creators using the Espresso audio in dance content"
- Spot niche opportunities: "creators mentioning fitness keywords without fitness monetization set up"

### Deferred: screenshot-based funnel mapping
Original brain-dump idea was to Gemini-screenshot every page of a creator's funnel and analyze visually. **Parked.** Text-based analysis from Apify data + link-in-bio scraping is enough for now. Revisit if we find text analysis is missing something important.

---

## Module 6 — Classification & Taxonomy ⬜

**What it does:** Manage the dynamic label vocabulary. Review AI-created labels, merge duplicates, promote to canonical.

### Phase 3 build
- **Classification tab per platform** (`/platforms/instagram/classification`, etc.) — content-level labels
- **Creator Classification view** — creator-level niche labels (parallel system, same mechanics)
- **Label lifecycle:**
  - AI creates label during analysis → `is_canonical = false`, low `usage_count`
  - Threshold promotion (proposed default): `usage_count >= 5` → label promoted to `is_canonical = true` automatically, unless team manually promotes earlier
  - Team can: rename, merge two labels (merged_into_id), demote, delete (only if usage_count = 0)
- **Deduplication** — a Claude agent reviews new labels nightly, suggests merges for semantically similar labels (e.g., `glow-up-transition` vs `glowup-reveal` → suggest merge)
- **Search-by-label anywhere** — label chips on every content card are clickable, deep-link to filtered view

### Open decision
Final default for auto-canonical threshold not locked. Current proposal: `5 uses`. Will fine-tune in practice.

---

## Module 7 — Funnel & Monetization ⬜

**What it does:** Visualize how a creator's traffic flows across their owned assets. Surface monetization patterns across creators.

### Phase 4 build
- **Funnel editor** (React Flow) — drag-to-connect editor for `funnel_edges`
  - Nodes: every profile/account for the creator
  - Edges: directed, colored by `edge_type` (link_in_bio, direct_link, cta_mention, qr_code, inferred)
  - Team can override AI-proposed edges, confirm/reject inferred ones
- **Monetization intel dashboards:**
  - Monetization model distribution across managed creators
  - OF / Fanvue / Fanplace subscriber counts (when manually tracked — we don't scrape these)
  - Amazon storefront + TikTok Shop product counts
  - Telegram channel member counts
  - Revenue attribution (manual entry for now — no scraping of private revenue data)
- **Cross-creator pattern detection:**
  - "All Diamond-tier creators use Linktree — none use Beacons"
  - "Creators using cupidbot have 3× higher tip volume than those without"
  - "Goth creators with OF + Telegram convert 2× better than goth creators with OF only"

### What this WON'T scrape
- OnlyFans, Fanvue, Fanplace revenue (private data, not scrapable)
- Amazon storefront sales
- TikTok Shop sales
These are monetization **assets we track the existence of**, not revenue we scrape.

---

## Module 8 — Trends, Alerts & Signals 🟡

**What it does:** Surface moments worth paying attention to. Velocity spikes, new outliers, emerging archetypes, cadence changes.

### Built
- `/trends` UI shell with mock data
- `trend_signals`, `alerts_config`, `alerts_feed` tables exist

### Phase 2–3 build
- **Signal types** (enum already exists):
  - `velocity_spike` — post's view velocity exceeds threshold
  - `outlier_post` — `flag_outliers` flagged a new one
  - `emerging_archetype` — pattern shift in a creator's content
  - `hook_pattern` — new hook style gaining traction
  - `cadence_change` — creator's posting frequency shifts significantly
  - `new_monetization_detected` — discovery picked up a new monetization asset
- **Alert rules** configurable per workspace (managed by `alerts_config`):
  - Condition (e.g., "when velocity_spike detected on managed creator")
  - Target profiles / all
  - Notification destination (emails; future: Slack, Discord)
- **Live feed UI** — real-time rendering via Supabase Realtime on `alerts_feed`

---

## Module 9 — Agency Operations (Future Umbrella) ⬜

**Status:** Ideas only. Kept visible in sidebar as "Soon" items to remind us what the bigger vision could include. Not committed to building.

| Item | What it might be |
|---|---|
| Revenue Center | Manual revenue tracking per creator per platform, margin analysis, agency commission rollup |
| Fan Intel Hub | Manual fan profile tracking — top tippers, VIP fans, cross-platform fan identity resolution |
| Chatter Workspace | Chat coordination tool for chatters managing DM conversations on OF/Fanvue |
| Tasks | Agency-wide task board |
| Customs | Custom content request intake and fulfillment tracking |
| Handoffs | Creator handoff workflow when ownership transfers between team members |
| Briefings | Content briefing generator — given creator data, produce shoot briefs |
| Shift Center | Team scheduling and shift coverage |
| Comm Hub | Unified inbox across platforms |
| Contacts | Agency contacts database (brand deals, photographers, vendors) |

These all stay as disabled "Soon" sidebar items with a hover tooltip: "Future module — not yet in scope."

---

## Cross-Module Decisions Locked In

1. **Gemini handles:** discovery, content visual analysis, quick classification
2. **Claude handles:** brand analysis, hook pattern analysis, multi-step agent workflows
3. **Agents (Claude) introduced only when:** workflow needs iterative reasoning. First candidate: Brand Analysis (Phase 3). Second: Label deduplication (Phase 3).
4. **Straight code handles:** all scraping, all normalization, all DB RPCs, all UI
5. **Session notes:** one file per calendar day (`06-Sessions/YYYY-MM-DD.md`)
6. **PROJECT_STATE.md updates:** automatic on any architectural change; full sync on command ("update project state")
7. **Build order priority:** wire existing UI to live data first → then Phase 2 scraping → then Phase 3 analysis
8. **What won't be built:** client logins, multi-tenant SaaS, audio fingerprinting, private revenue scraping, screenshot-based funnel mapping (deferred/parked)
9. **Every phase ships with its agents.** Feature completion without agent completion is an incomplete phase. Agents live in `.claude/skills/` and are version-controlled with the repo. Full catalog: [[04-Pipeline/Agent Catalog]].

---

## What This Vision Unlocks

When all modules are built, an agency team member can:

1. Paste 50 creator handles — walk away — come back to fully mapped networks
2. See which creators are breaking out right now (outliers, velocity spikes)
3. Filter "goth creators doing dance trends with the Espresso audio" in one query
4. Read a brand analysis for any creator covering niche, USP, SEO, and funnel strategy
5. See how traffic flows through each creator's funnel visually
6. Compare monetization patterns across tiers (what do Diamond creators do that Bronze don't?)
7. Get alerted when a managed creator's posting cadence changes or a new monetization asset appears

That's the endgame. Phase 1 is built. Everything else is additive.
