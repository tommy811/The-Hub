# Phase 3 — Analysis Engines Prompt

> Not yet written. Build after Phase 2 is complete.

## What It Will Build
- Gemini content scoring batch pipeline (quality_score, archetype, vibe, category)
- Brand analysis pipeline (multi-platform Gemini pass to creator_brand_analyses)
- Dynamic label taxonomy management UI (Classification tab)
- profile_scores + rank tier live computation wired to UI
- Content analysis drawer on account cards

## Before Writing This Prompt
1. Phase 2 must have content scraped for multiple creators
2. Run a sample Gemini analysis manually — verify GEMINI_ANALYSIS_SCHEMA matches
3. Decide: batch size for analysis runs? (default: 50 posts per run)
4. Decide: re-analysis triggers — when does a post get re-scored?
5. Update PROJECT_STATE.md with Phase 2 changes before prompting
