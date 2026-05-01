-- T20: enriched watchdog view — surfaces Gemini's platform suggestions
-- alongside the active 'other' rows for one-click VA ratification.

CREATE OR REPLACE VIEW new_platform_watchdog AS
WITH grouped AS (
  SELECT
    -- Strip leading 'www.', take only the host portion
    LOWER(REGEXP_REPLACE(REGEXP_REPLACE(p.url, '^https?://(www\.)?', ''), '/.*$', '')) AS host,
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
),
guess_per_host AS (
  -- Most-confident Gemini suggestion per host (one row per host)
  SELECT DISTINCT ON (host)
    LOWER(REGEXP_REPLACE(REGEXP_REPLACE(g.canonical_url, '^https?://(www\.)?', ''), '/.*$', '')) AS host,
    g.suggested_label,
    g.suggested_slug,
    g.description,
    g.icon_category
  FROM classifier_llm_guesses g
  ORDER BY host, g.confidence DESC NULLS LAST, g.classified_at DESC
)
SELECT
  grouped.host,
  grouped.creator_count,
  grouped.row_count,
  grouped.creators,
  grouped.account_types_seen,
  grouped.sample_url,
  grouped.last_seen,
  guess_per_host.suggested_label,
  guess_per_host.suggested_slug,
  guess_per_host.description,
  guess_per_host.icon_category
FROM grouped
LEFT JOIN guess_per_host ON guess_per_host.host = grouped.host
ORDER BY grouped.creator_count DESC, grouped.row_count DESC;

COMMENT ON VIEW new_platform_watchdog IS
  'Surfaces URL hosts classified as platform=other with Gemini-suggested label/slug/description/icon_category for VA-ratifiable platform additions.';
