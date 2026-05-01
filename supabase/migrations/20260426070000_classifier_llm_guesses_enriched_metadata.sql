-- T20: Gemini-enriched classifier metadata.
-- The LLM already classifies (platform, account_type) but we throw away the
-- richer judgment that comes "for free" with the same call (label, slug,
-- one-sentence description, icon-category hint). Capture them so the
-- new_platform_watchdog view can surface VA-actionable suggestions.

ALTER TABLE classifier_llm_guesses
  ADD COLUMN IF NOT EXISTS suggested_label TEXT,
  ADD COLUMN IF NOT EXISTS suggested_slug TEXT,
  ADD COLUMN IF NOT EXISTS description TEXT,
  ADD COLUMN IF NOT EXISTS icon_category TEXT;

COMMENT ON COLUMN classifier_llm_guesses.suggested_label IS
  'Gemini-suggested human-readable platform name (e.g. "Stan Store"). Surfaces in new_platform_watchdog view.';
COMMENT ON COLUMN classifier_llm_guesses.suggested_slug IS
  'Gemini-suggested platform-enum slug ("stan_store", "bunny_app"). Reviewed before adding to Postgres platform enum.';
COMMENT ON COLUMN classifier_llm_guesses.description IS
  'Gemini one-sentence summary of what this platform/site is.';
COMMENT ON COLUMN classifier_llm_guesses.icon_category IS
  'Visual class hint for icon picking: monetization | social | aggregator | messaging | content | ecommerce | other.';
