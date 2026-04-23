# Feature Backlog

## Agent Backlog

Agents are phase deliverables. A phase closes only when its agents are built + validated. See [[04-Pipeline/Agent Catalog]] for full specs.

- [x] **verify-and-fix** (Phase 1 — ✅ built, `.claude/skills/verify-and-fix/SKILL.md`)
- [ ] **schema-drift-watchdog** (Phase 2)
- [ ] **scrape-verify** (Phase 2)
- [ ] **/verify-scrape slash command** (Phase 2)
- [ ] **brand-analysis** (Phase 3)
- [ ] **label-deduplication** (Phase 3)
- [ ] **merge-candidate-resolver** (Phase 3)
- [ ] **funnel-inference** (Phase 4)
- [ ] **documentation-drift** (ongoing, Phase 2+)

---

## Phase 1 ✅ Complete (feature work)

- [x] Bulk import modal with live handle parser
- [x] Creator card grid (Processing / Ready / Failed states)
- [x] Creator card — Realtime state transitions via Supabase
- [x] Creator deep-dive — Network tab (live accounts list)
- [x] Creator deep-dive — Funnel tab (React Flow stub)
- [x] Merge candidate detection + review UI
- [x] BulkImportDialog with HandleChipPreview
- [x] Discovery pipeline Python worker
- [x] Edge Function: trigger-discovery
- [x] Sidebar updated with Creators section
- [x] Re-run Discovery button — wired end-to-end (RerunDiscoveryButton → rerunCreatorDiscovery action → retry_creator_discovery RPC → worker)
- [x] Manual Add Account dialog — AddAccountDialog with 18 platforms, auto account_type, wired to addProfileToCreator server action
- [x] Creator detail page revamp — stats strip (Total Reach, Social/Monetization/Link-in-Bio counts), bio, avatar with fallback
- [x] AvatarWithFallback — client component, onError → gradient monogram, eliminates blank avatar from expired CDN URLs
- [x] Apify field mapping fix — followersCount / profilePicUrl / biography / metaData fallback. Follower counts (627K Natalie, 49.7K Esmae) now populate correctly.

## Now (Phase 2)

- [x] Wire `/platforms/instagram/accounts` to live Supabase data (remove mocks)
- [x] Mirror for TikTok once Instagram accounts page is live
- [ ] Wire `/content` and `/trends` routes
- [ ] IG scraper (Apify: apify/instagram-scraper) + normalize_instagram.py
- [ ] TikTok scraper (Apify: clockworks/tiktok-scraper) + normalize_tiktok.py
- [ ] Outlier detection (flag_outliers RPC — live, ≥ 3.0× threshold)
- [ ] Platform accounts page — 4-tab layout (Accounts / Outliers / Classification / Analytics)
- [ ] Account card grid with rank badges, vibe/archetype/category pills
- [ ] Daily snapshot cron job
- [ ] Trend signals pipeline + trends table migration

## Later (Phase 3+)

- [ ] Gemini content scoring batch pipeline
- [ ] Brand analysis report generator (Claude Sonnet)
- [ ] Label taxonomy management UI (Classification tab)
- [ ] Funnel flowchart full editor (React Flow drag-to-connect)
- [ ] Telegram channel tracking
- [ ] OF/Fanvue monetization intel

## Ideas / Not Scoped

- Client-facing portal login
- Custom domain creation for creators
- Automated content briefing generator
- Shift scheduling (Comm Hub)
