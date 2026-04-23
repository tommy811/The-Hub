# Discovery Pipeline

## Overview
Input: social handle or URL (any platform)
Output: fully mapped creator network in the database
Time: ~30–90 seconds per creator

---

## Step-by-Step Flow

### Step 1: User Input
User pastes handles into Bulk Import modal.
`lib/handleParser.ts` parses each line:
- Full URL → extract platform from domain, handle from path
- `platform:handle` prefix syntax (ig:, tt:, of:, fv:, lt:, tg:)
- `@handle platform-hint` trailing hint
- Bare `@handle` → flagged, user must assign platform

### Step 2: Immediate DB Insert (insert-first pattern)
Before any API call:
1. INSERT `creators` row: `{canonical_name: handle, onboarding_status: 'processing'}`
2. INSERT `profiles` row: `{platform, handle, account_type: 'social', is_primary: true}`
3. INSERT `discovery_runs` row: `{status: 'pending'}`
4. Card appears in grid immediately in **Processing** state
5. POST to Edge Function `trigger-discovery` with `run_id`

### Step 3: Edge Function
`supabase/functions/trigger-discovery/index.ts`
- Validates run_id
- Updates run status → 'processing'
- Calls Python worker HTTP endpoint (or worker picks up on next poll)

### Step 4: Python — fetch_input_context()
`scripts/discover_creator.py`
- **⚠️ BROKEN AS OF 2026-04-23:** `httpx.get("https://www.instagram.com/{handle}/")` is blocked by Instagram — returns login redirect or bot-detection page. Gemini receives garbage HTML and discovery produces no real data.
- BeautifulSoup extracts: bio, display_name, link_in_bio_url, follower_count, avatar_url (design intent, not working)
- If screenshot input: loads from Supabase Storage, base64 encodes for Gemini vision

**Planned fix (Phase 2, first task):** Replace `httpx.get()` with Apify `apify/instagram-scraper` using `resultsType: "details"`. This returns real profile data (bio, followers, `externalUrls`[] including link-in-bio destinations) in clean JSON. No HTML scraping needed. The rest of the pipeline (Gemini classification, commit_discovery_result RPC) remains unchanged.

### Step 5: Python — resolve_link_in_bio()
Follows the link-in-bio URL:
- linktr.ee → scrapes all anchor hrefs in the link list
- beacons.ai → scrapes anchor hrefs
- bio.link, taplink.cc → scrapes anchor hrefs
- Custom domain → extracts all outbound external hrefs
Returns: list of destination URLs

### Step 6: Python — run_gemini_discovery()
Single Gemini 1.5 Pro call (JSON mode + response_schema = GEMINI_DISCOVERY_SCHEMA)

**Prompt instructs Gemini to:**
1. Identify EVERY account the creator owns
2. Specifically probe for: OF, Fanvue, Fanplace, Amazon storefront, TikTok Shop, Linktree, Beacons, custom domain, Telegram channels, cupidbot, Twitter/X, YouTube, Facebook
3. Assign confidence 0.0–1.0 per account (1.0 = found via direct link, 0.5–0.8 = name-matched)
4. Map funnel edges (which account links to which)
5. Classify monetization_model

**Input context provided:** bio, display_name, source URL, all link-in-bio destination URLs

### Step 7: Python — commit()
Calls `commit_discovery_result` RPC with:
- `p_creator_data`: canonical_name, known_usernames[], primary_platform, monetization_model
- `p_accounts`: array of ProposedAccount objects
- `p_funnel_edges`: array of ProposedFunnelEdge objects

**RPC does (transactional):**
- Enriches creator row
- For each account: collision check → merge candidate OR upsert profile
- Inserts funnel edges
- Marks run completed, sets onboarding_status = 'ready'

### Step 8: Realtime Update
Supabase Realtime fires on `creators` row update.
Browser receives event.
Creator card animates from Processing → Ready state (framer-motion).

---

## Error Handling
Any exception in steps 4–7 → calls `mark_discovery_failed` RPC
- Run status = 'failed'
- Creator onboarding_status = 'failed'
- Error stored in `last_discovery_error`
- Card shows Failed state with Retry button
- Retry creates new `discovery_runs` row, resets to processing

## Retry Logic
- Python: tenacity decorator on Gemini call (exp backoff, 3 attempts)
- UI: Retry button calls `retry_creator_discovery` RPC → new run_id → triggers pipeline again
- Max tracked in `discovery_runs.attempt_number`

## LLM Routing

This pipeline uses Gemini 1.5 Pro for discovery. For the full routing table across all pipelines, see [[PROJECT_STATE#8. LLM Routing]].
