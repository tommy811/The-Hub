-- Content Scraper v1 — quality_flag enum + new structural/analytical columns on scraped_content.
-- Spec: docs/superpowers/specs/2026-04-27-content-scraper-v1-design.md §3.6

-- Quality flag (anticipates §15.2 watchdog; v1 always writes 'clean')
CREATE TYPE quality_flag AS ENUM ('clean', 'suspicious', 'rejected');

ALTER TABLE scraped_content
  ADD COLUMN quality_flag quality_flag NOT NULL DEFAULT 'clean',
  ADD COLUMN quality_reason text;

CREATE INDEX scraped_content_quality_flag_idx
  ON scraped_content (profile_id, quality_flag)
  WHERE quality_flag <> 'clean';

-- Structural / analytical columns surfaced from Apify payloads
ALTER TABLE scraped_content
  ADD COLUMN is_pinned boolean NOT NULL DEFAULT false,
  ADD COLUMN is_sponsored boolean NOT NULL DEFAULT false,
  ADD COLUMN video_duration_seconds numeric,
  ADD COLUMN hashtags text[] NOT NULL DEFAULT '{}',
  ADD COLUMN mentions text[] NOT NULL DEFAULT '{}';

-- GIN indexes for array contains queries
CREATE INDEX scraped_content_hashtags_gin ON scraped_content USING GIN (hashtags);
CREATE INDEX scraped_content_mentions_gin ON scraped_content USING GIN (mentions);

-- Btree partial indexes on common filter axes (zero cost on common path)
CREATE INDEX scraped_content_is_pinned_idx ON scraped_content (profile_id, is_pinned)
  WHERE is_pinned = true;
CREATE INDEX scraped_content_is_sponsored_idx ON scraped_content (profile_id, is_sponsored)
  WHERE is_sponsored = true;
