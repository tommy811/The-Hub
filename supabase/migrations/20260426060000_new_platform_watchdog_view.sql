-- supabase/migrations/20260426060000_new_platform_watchdog_view.sql
-- VA-friendly view for surfacing newly-encountered platforms.
-- Any active profile row classified as platform='other' is a candidate for
-- gazetteer + PLATFORMS dict additions. This view groups them by URL host so
-- the operator can see "5 creators have rows pointing at stan.store — let's
-- add it to the gazetteer + icon registry".
--
-- Usage from the dashboard (or via Supabase SQL editor):
--   SELECT * FROM new_platform_watchdog ORDER BY creator_count DESC LIMIT 50;

CREATE OR REPLACE VIEW new_platform_watchdog AS
SELECT
  -- Strip leading 'www.', take only the host portion
  LOWER(REGEXP_REPLACE(REGEXP_REPLACE(url, '^https?://(www\.)?', ''), '/.*$', '')) AS host,
  COUNT(DISTINCT p.creator_id) AS creator_count,
  COUNT(*) AS row_count,
  ARRAY_AGG(DISTINCT c.canonical_name ORDER BY c.canonical_name) AS creators,
  ARRAY_AGG(DISTINCT p.account_type) AS account_types_seen,
  MIN(p.url) AS sample_url,
  MAX(p.updated_at) AS last_seen
FROM profiles p
JOIN creators c ON c.id = p.creator_id
WHERE p.is_active = true
  AND p.platform = 'other'
  AND p.url IS NOT NULL
GROUP BY 1
ORDER BY creator_count DESC, row_count DESC;

COMMENT ON VIEW new_platform_watchdog IS
  'Surfaces URL hosts classified as platform=other (no gazetteer rule, no icon). '
  'Operator runs this periodically to triage and add new platforms to '
  'scripts/data/monetization_overlay.yaml + src/lib/platforms.ts.';
