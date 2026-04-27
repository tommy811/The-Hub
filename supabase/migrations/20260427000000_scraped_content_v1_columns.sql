-- Content Scraper v1 — quality_flag enum + new structural/analytical columns on scraped_content.
-- Spec: docs/superpowers/specs/2026-04-27-content-scraper-v1-design.md §3.6

-- Quality flag (anticipates §15.2 watchdog; v1 always writes 'clean')
DO $$
BEGIN
  CREATE TYPE quality_flag AS ENUM ('clean', 'suspicious', 'rejected');
EXCEPTION
  WHEN duplicate_object THEN NULL;
END
$$;

ALTER TABLE scraped_content
  ADD COLUMN IF NOT EXISTS quality_flag quality_flag NOT NULL DEFAULT 'clean',
  ADD COLUMN IF NOT EXISTS quality_reason text;

COMMENT ON TYPE quality_flag IS
  'Watchdog quality flag (anticipates §15.2). v1 always writes ''clean''; future validators flip to ''suspicious''/''rejected''.';
COMMENT ON COLUMN scraped_content.quality_flag IS
  'Watchdog quality flag (anticipates §15.2 watchdog stack).';
COMMENT ON COLUMN scraped_content.quality_reason IS
  'Free-text reason populated by future LLM-as-judge / validators when quality_flag <> clean.';

CREATE INDEX IF NOT EXISTS scraped_content_quality_flag_idx
  ON scraped_content (profile_id, quality_flag)
  WHERE quality_flag <> 'clean';

-- Structural / analytical columns surfaced from Apify payloads
ALTER TABLE scraped_content
  ADD COLUMN IF NOT EXISTS is_pinned boolean NOT NULL DEFAULT false,
  ADD COLUMN IF NOT EXISTS is_sponsored boolean NOT NULL DEFAULT false,
  ADD COLUMN IF NOT EXISTS video_duration_seconds numeric,
  ADD COLUMN IF NOT EXISTS hashtags text[] NOT NULL DEFAULT '{}',
  ADD COLUMN IF NOT EXISTS mentions text[] NOT NULL DEFAULT '{}';

COMMENT ON COLUMN scraped_content.is_pinned IS
  'TT pinned posts; pinned content skews profile metrics and must be filterable.';
COMMENT ON COLUMN scraped_content.is_sponsored IS
  'IG isSponsored / TT isAd — UGC vs paid analysis.';
COMMENT ON COLUMN scraped_content.video_duration_seconds IS
  'Video length in seconds; cohort analysis by length.';
COMMENT ON COLUMN scraped_content.hashtags IS
  'Hashtag tokens (no leading #) extracted by per-platform normalizer.';
COMMENT ON COLUMN scraped_content.mentions IS
  '@-mentioned handles in post body — collab/cross-promo network.';

-- GIN indexes for array contains queries
CREATE INDEX IF NOT EXISTS scraped_content_hashtags_gin ON scraped_content USING GIN (hashtags);
CREATE INDEX IF NOT EXISTS scraped_content_mentions_gin ON scraped_content USING GIN (mentions);

-- Btree partial indexes on common filter axes (zero cost on common path)
CREATE INDEX IF NOT EXISTS scraped_content_is_pinned_idx ON scraped_content (profile_id, is_pinned)
  WHERE is_pinned = true;
CREATE INDEX IF NOT EXISTS scraped_content_is_sponsored_idx ON scraped_content (profile_id, is_sponsored)
  WHERE is_sponsored = true;
