-- Content Scraper v1 — transactional commit RPC.
-- Writes scraped_content rows + content_metrics_snapshots in one transaction.
-- Spec: docs/superpowers/specs/2026-04-27-content-scraper-v1-design.md §3.4

CREATE OR REPLACE FUNCTION commit_scrape_result(
  p_profile_id uuid,
  p_posts jsonb
) RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER
AS $$
DECLARE
  v_workspace_id uuid;
  v_posts_upserted int := 0;
  v_snapshots_written int := 0;
  v_today date := CURRENT_DATE;
  v_post jsonb;
  v_content_id uuid;
BEGIN
  SELECT workspace_id INTO v_workspace_id
  FROM profiles WHERE id = p_profile_id;
  IF v_workspace_id IS NULL THEN
    RAISE EXCEPTION 'profile not found: %', p_profile_id;
  END IF;

  FOR v_post IN SELECT * FROM jsonb_array_elements(p_posts) LOOP
    INSERT INTO scraped_content (
      profile_id, platform, platform_post_id, post_url, post_type,
      caption, hook_text, posted_at,
      view_count, like_count, comment_count, share_count, save_count,
      is_pinned, is_sponsored, video_duration_seconds,
      hashtags, mentions,
      media_urls, thumbnail_url, platform_metrics, raw_apify_payload,
      quality_flag
    )
    VALUES (
      p_profile_id,
      (v_post->>'platform')::platform,
      v_post->>'platform_post_id',
      v_post->>'post_url',
      (v_post->>'post_type')::post_type,
      v_post->>'caption',
      v_post->>'hook_text',
      (v_post->>'posted_at')::timestamptz,
      COALESCE((v_post->>'view_count')::bigint, 0),
      COALESCE((v_post->>'like_count')::bigint, 0),
      COALESCE((v_post->>'comment_count')::bigint, 0),
      (v_post->>'share_count')::bigint,
      (v_post->>'save_count')::bigint,
      COALESCE((v_post->>'is_pinned')::bool, false),
      COALESCE((v_post->>'is_sponsored')::bool, false),
      (v_post->>'video_duration_seconds')::numeric,
      ARRAY(SELECT jsonb_array_elements_text(v_post->'hashtags')),
      ARRAY(SELECT jsonb_array_elements_text(v_post->'mentions')),
      ARRAY(SELECT jsonb_array_elements_text(v_post->'media_urls')),
      v_post->>'thumbnail_url',
      v_post->'platform_metrics',
      v_post->'raw_apify_payload',
      'clean'
    )
    ON CONFLICT (platform, platform_post_id) DO UPDATE SET
      view_count = EXCLUDED.view_count,
      like_count = EXCLUDED.like_count,
      comment_count = EXCLUDED.comment_count,
      share_count = EXCLUDED.share_count,
      save_count = EXCLUDED.save_count,
      is_pinned = EXCLUDED.is_pinned,
      is_sponsored = EXCLUDED.is_sponsored,
      hashtags = EXCLUDED.hashtags,
      mentions = EXCLUDED.mentions,
      caption = EXCLUDED.caption,
      platform_metrics = EXCLUDED.platform_metrics,
      raw_apify_payload = EXCLUDED.raw_apify_payload,
      updated_at = NOW()
    RETURNING id INTO v_content_id;

    v_posts_upserted := v_posts_upserted + 1;

    INSERT INTO content_metrics_snapshots (
      content_id, snapshot_date,
      view_count, like_count, comment_count, share_count, save_count
    )
    VALUES (
      v_content_id, v_today,
      COALESCE((v_post->>'view_count')::bigint, 0),
      COALESCE((v_post->>'like_count')::bigint, 0),
      COALESCE((v_post->>'comment_count')::bigint, 0),
      (v_post->>'share_count')::bigint,
      (v_post->>'save_count')::bigint
    )
    ON CONFLICT (content_id, snapshot_date) DO UPDATE SET
      view_count = EXCLUDED.view_count,
      like_count = EXCLUDED.like_count,
      comment_count = EXCLUDED.comment_count,
      share_count = EXCLUDED.share_count,
      save_count = EXCLUDED.save_count;

    v_snapshots_written := v_snapshots_written + 1;
  END LOOP;

  RETURN jsonb_build_object(
    'posts_upserted', v_posts_upserted,
    'snapshots_written', v_snapshots_written
  );
END;
$$;
