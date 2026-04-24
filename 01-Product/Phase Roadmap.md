# Phase Roadmap

See [[Full Product Vision]] for the complete 9-module scope.

---

## Phase 1 — Foundation & Creators ✅ COMPLETE (feature work)

- ✅ Complete Supabase schema (18 tables, all RLS)
- ✅ Creator layer migration applied to Content OS
- ✅ Creators hub UI (Bulk import, card grid, deep-dive)
- ✅ Discovery pipeline (Python + Gemini, worker, apify_scraper)
- ✅ Cross-platform identity resolution (merge candidates, rapidfuzz)
- ✅ Claude Code wiring to live Supabase + Realtime transitions
- ✅ Phase 1 UX hardening (Re-run Discovery, Add Account dialog, detail page revamp, avatar fallback, Apify field mapping fix)

### Required Agents — Phase 1
- **verify-and-fix** — ✅ Built (`claude/skills/verify-and-fix/SKILL.md`)

> ✅ Phase 1 agent requirement met. Phase 1 is fully closed.

See [[PROJECT_STATE#16. Per-Phase Agent Requirements]] for full agent requirements table.

**verify-and-fix** — Post-change verification loop. Starts dev server, checks TypeScript compile, curls affected pages for 200 response, verifies Supabase query shapes via MCP, smoke-tests server actions. Auto-fixes up to 3 loops, then escalates with full error context. Solves "Claude says it works, doesn't actually work."

---

## Phase 2 — Platform Intelligence 🔄 IN PROGRESS

### Feature Work
- ✅ Wire `/platforms/instagram/accounts` + `/platforms/tiktok/accounts` to live data
- ✅ Phase 2 schema migration: `trends` + `creator_label_assignments` tables; `trend_type` / `llm_model` / `content_archetype` enums; `creator_niche` on `label_type`; `archetype`+`vibe` moved from `content_analysis` → `creators`; `scraped_content.trend_id` FK. (Migration `20260424170000_phase_2_schema_migration`, PR #3.)
- 🔜 Discovery pipeline rebuild — replace `httpx.get()` with Apify `resultsType: "details"` in `scripts/discover_creator.py` (Phase 2 first task — see PROJECT_STATE §20)
- 🔜 Wire `/content` and `/trends` routes
- 🔜 Per-platform scraping: IG + TikTok via Apify (scheduled via GitHub Actions every 12h)
- 🔜 Normalizer modules (`normalize_instagram.py`, `normalize_tiktok.py`)
- 🔜 Outlier detection (flag_outliers RPC — threshold ≥ 3.0×, 15-post floor, 48h age guard)
- 🔜 Platform accounts page — 4-tab layout (Accounts / Outliers / Classification / Analytics)
- 🔜 Daily snapshot cron job (`content_metrics_snapshots`, `profile_metrics_snapshots`)
- 🔜 Trend linking during content analysis — audio signature extraction from `platform_metrics` populates `scraped_content.trend_id`
- 🔜 `quality_flag` + `quality_reason` columns on `scraped_content` (runtime watchdog per §15.2)

### Required Agents — Phase 2
- **schema-drift-watchdog** — Weekly scan: live Supabase schema vs PROJECT_STATE.md §4 vs code queries. Surfaces drift before it breaks production.
- **scrape-verify** — Post-ingestion verification. Apify webhook handler: row counts, field success rates, auth-wall regex, Pydantic validation. Sets `quality_flag`.
- **verify-scrape** (slash command) — On-demand end-to-end check: Apify → Supabase → UI DOM integrity. Run before declaring any scraper work complete.

---

## Phase 3 — Analysis Engines

### Feature Work
- Gemini content scoring batch pipeline (quality_score, category, visual_tags)
- Claude brand analysis per creator (niche_summary, USP, SEO keywords, archetype, vibe)
- Dynamic label taxonomy + Classification UI
- `profile_scores` + rank tier live computation
- `creator_brand_analyses` reports in creator deep-dive

### Required Agents — Phase 3
- **brand-analysis** — Multi-step Claude agent: bio + link-in-bio + top content → niche, USP, brand_keywords, seo_keywords, archetype, vibe. Writes to `creator_brand_analyses` with versioned `version` column.
- **label-deduplication** — Nightly embedding-based semantic merge of near-duplicate `content_labels`. Auto-merge at ≥ 0.98 similarity; escalate 0.92–0.98.
- **merge-candidate-resolver** — Auto-merges `creator_merge_candidates` at confidence ≥ 0.9 nightly. Escalates lower for human review.

---

## Phase 4 — Funnel & Monetization

### Feature Work
- React Flow funnel editor (drag-to-connect `funnel_edges`)
- Monetization intelligence dashboards
- Cross-creator pattern detection
- Revenue Center shell (manual entry — no scraping of private revenue data)
- Telegram + OF intel

### Required Agents — Phase 4
- **funnel-inference** — Scans content captions + link-in-bio destinations for `funnel_edges` the discovery pass missed. Proposes with confidence ≤ 0.7; requires human approval in funnel editor UI.

## Out of Scope

- Client-facing portal login
- Multi-tenant SaaS
- Audio fingerprinting
- Screenshot-based funnel mapping (deferred)
- Private revenue scraping (OF/Fanvue/Amazon)
