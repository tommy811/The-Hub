-- supabase/migrations/20260426000000_url_harvester_v1.sql
-- Universal URL Harvester v1.
-- 1. Add audit trail columns to profile_destination_links.
-- 2. Create workspace-agnostic url_harvest_cache table.

-- 1. Audit trail on profile_destination_links
ALTER TABLE profile_destination_links
  ADD COLUMN harvest_method TEXT,
  ADD COLUMN raw_text TEXT,
  ADD COLUMN harvested_at TIMESTAMPTZ DEFAULT NOW();

COMMENT ON COLUMN profile_destination_links.harvest_method IS
  'How this URL was discovered: cache | httpx | headless. NULL on rows pre-dating the harvester.';

-- 2. URL → harvested destinations cache (mirrors classifier_llm_guesses pattern).
-- Workspace-agnostic; service role writes; reads keyed on canonical_url.
CREATE TABLE url_harvest_cache (
  canonical_url       TEXT PRIMARY KEY,
  harvest_method      TEXT NOT NULL CHECK (harvest_method IN ('httpx', 'headless')),
  destinations        JSONB NOT NULL,  -- [{canonical_url, raw_url, raw_text, destination_class}, ...]
  harvested_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  expires_at          TIMESTAMPTZ NOT NULL,
  created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE url_harvest_cache IS
  'Workspace-agnostic cache of URL → outbound destinations. 24h TTL by default. Service role only.';

-- Index supports the common query: lookup by canonical_url with TTL filter.
CREATE INDEX idx_url_harvest_cache_expires ON url_harvest_cache (expires_at);

-- No RLS — workspace-agnostic, service role only (matching classifier_llm_guesses).
