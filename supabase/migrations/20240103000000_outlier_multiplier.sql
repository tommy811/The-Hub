-- Add outlier_multiplier column to scraped_content and rewrite flag_outliers
-- to store the computed ratio alongside the boolean flag.

ALTER TABLE scraped_content
  ADD COLUMN IF NOT EXISTS outlier_multiplier NUMERIC(5,2);

-- Rewrite flag_outliers to compute and store the multiplier,
-- then set is_outlier = true when multiplier >= 3.0.
-- Window: last 50 posts OR last 90 days (whichever smaller).
-- Floor: minimum 15 posts before flagging activates.
-- Age guard: post must be >= 48 hours old.
CREATE OR REPLACE FUNCTION flag_outliers(p_profile_id UUID)
RETURNS VOID
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
  v_window_start TIMESTAMPTZ;
  v_post_count   INT;
  v_median_views NUMERIC;
BEGIN
  -- Determine the 90-day window start
  v_window_start := NOW() - INTERVAL '90 days';

  -- Count qualifying posts in the window
  SELECT COUNT(*)
    INTO v_post_count
    FROM scraped_content
   WHERE profile_id  = p_profile_id
     AND posted_at  >= v_window_start
     AND posted_at  <= NOW() - INTERVAL '48 hours';

  -- If we don't have enough posts, bail out without touching any rows
  IF v_post_count < 15 THEN
    RETURN;
  END IF;

  -- Compute median from the qualifying window (capped at last 50 posts)
  SELECT PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY view_count)
    INTO v_median_views
    FROM (
      SELECT view_count
        FROM scraped_content
       WHERE profile_id  = p_profile_id
         AND posted_at  >= v_window_start
         AND posted_at  <= NOW() - INTERVAL '48 hours'
       ORDER BY posted_at DESC
       LIMIT 50
    ) sub;

  -- Guard against divide-by-zero when median is 0
  IF v_median_views IS NULL OR v_median_views = 0 THEN
    RETURN;
  END IF;

  -- Update outlier_multiplier for all posts in this profile that are >= 48h old
  UPDATE scraped_content
     SET outlier_multiplier = ROUND((view_count::NUMERIC / v_median_views), 2),
         is_outlier         = (view_count::NUMERIC / v_median_views) >= 3.0
   WHERE profile_id = p_profile_id
     AND posted_at <= NOW() - INTERVAL '48 hours';
END;
$$;
