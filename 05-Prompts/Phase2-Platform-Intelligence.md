# Phase 2 — Platform Intelligence Prompt

> ⬜ Not yet written. Build after Phase 1 is fully wired by Claude Code.

## What It Will Build
- IG + TikTok Apify scraping pipeline (normalize_instagram.py, normalize_tiktok.py)
- Platform accounts page — 4-tab layout (Accounts / Outliers / Classification / Analytics)
- Account card grid matching reference UI (rank badges, vibe/archetype/category pills)
- Outlier detection integration (flag_outliers RPC wired to UI)
- Daily snapshot cron
- Trend signals pipeline

## Before Writing This Prompt
1. Phase 1 must be fully working in production
2. Update PROJECT_STATE.md with any changes Claude Code made
3. Paste updated PROJECT_STATE.md at top of this prompt
4. List ALL existing files (Phase 1 output) so AI doesn't regenerate them
5. Test Apify actors manually in Apify console first — log raw JSON output
6. Add raw field samples to [[03-Database/Apify Field Mappings]] before prompting

## Key Decisions to Make First
- Scraping frequency: every 12h or 24h?
- Content volume: last 30 days or last 50 posts?
- Outlier formula: 2x median views (current) — adjust?
- Classification tab: what does the team do here exactly?
