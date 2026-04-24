-- 20260424160000_fix_funnel_edges_creator_id.sql
-- Fix bug in commit_discovery_result: the funnel_edges INSERT omitted creator_id,
-- causing NOT-NULL-constraint violations whenever Gemini proposed funnel edges.
-- This surfaced during the first post-Apify smoke test (2026-04-24), when Gemini
-- had real context for the first time and proposed real link-in-bio edges.
--
-- Change: add creator_id (v_creator_id already resolved earlier in the function)
-- to the INSERT column list and VALUES. Everything else is preserved verbatim.

CREATE OR REPLACE FUNCTION public.commit_discovery_result(
  p_run_id uuid, p_creator_data jsonb, p_accounts jsonb, p_funnel_edges jsonb
)
 RETURNS jsonb
 LANGUAGE plpgsql
AS $function$
DECLARE
  v_creator_id        UUID;
  v_workspace_id      UUID;
  v_account           JSONB;
  v_edge              JSONB;
  v_from_id           UUID;
  v_to_id             UUID;
  v_existing_creator  UUID;
  v_accounts_upserted INT := 0;
  v_merges_raised     INT := 0;
  v_proposed_name     TEXT;
BEGIN
  SELECT creator_id, workspace_id
  INTO   v_creator_id, v_workspace_id
  FROM   discovery_runs
  WHERE  id = p_run_id;

  IF v_creator_id IS NULL THEN
    RAISE EXCEPTION 'discovery_run % not found or already processed', p_run_id;
  END IF;

  v_proposed_name := NULLIF(NULLIF(TRIM(p_creator_data->>'canonical_name'), ''), 'Unknown');

  UPDATE creators SET
    canonical_name = COALESCE(v_proposed_name, canonical_name),
    known_usernames = (
      SELECT ARRAY_AGG(DISTINCT u)
      FROM UNNEST(
        known_usernames ||
        ARRAY(SELECT JSONB_ARRAY_ELEMENTS_TEXT(p_creator_data->'known_usernames'))
      ) AS u
      WHERE u IS NOT NULL AND u <> ''
    ),
    display_name_variants = (
      SELECT ARRAY_AGG(DISTINCT v)
      FROM UNNEST(
        display_name_variants ||
        ARRAY(SELECT JSONB_ARRAY_ELEMENTS_TEXT(p_creator_data->'display_name_variants'))
      ) AS v
      WHERE v IS NOT NULL AND v <> ''
    ),
    primary_platform   = COALESCE(
      NULLIF(p_creator_data->>'primary_platform', '')::platform,
      primary_platform
    ),
    primary_niche      = COALESCE(NULLIF(p_creator_data->>'primary_niche', ''), primary_niche),
    monetization_model = COALESCE(
      NULLIF(p_creator_data->>'monetization_model', '')::monetization_model,
      monetization_model
    ),
    onboarding_status  = 'ready',
    updated_at         = NOW()
  WHERE id = v_creator_id;

  -- Upsert discovered profiles
  FOR v_account IN SELECT * FROM JSONB_ARRAY_ELEMENTS(p_accounts)
  LOOP
    INSERT INTO profiles (
      workspace_id, creator_id, platform, handle, url,
      display_name, bio, follower_count, account_type,
      discovery_confidence, is_primary
    ) VALUES (
      v_workspace_id,
      v_creator_id,
      (v_account->>'platform')::platform,
      NULLIF(TRIM(v_account->>'handle'), ''),
      NULLIF(TRIM(v_account->>'url'), ''),
      NULLIF(TRIM(v_account->>'display_name'), ''),
      NULLIF(TRIM(v_account->>'bio'), ''),
      COALESCE((v_account->>'follower_count')::BIGINT, 0),
      (v_account->>'account_type')::account_type,
      COALESCE((v_account->>'discovery_confidence')::NUMERIC, 0.5),
      COALESCE((v_account->>'is_primary')::BOOLEAN, FALSE)
    )
    ON CONFLICT (workspace_id, platform, handle) WHERE handle IS NOT NULL
    DO UPDATE SET
      display_name         = COALESCE(NULLIF(EXCLUDED.display_name, ''), profiles.display_name),
      bio                  = COALESCE(NULLIF(EXCLUDED.bio, ''), profiles.bio),
      follower_count       = CASE
                               WHEN EXCLUDED.follower_count > 0 THEN EXCLUDED.follower_count
                               ELSE profiles.follower_count
                             END,
      discovery_confidence = GREATEST(EXCLUDED.discovery_confidence, profiles.discovery_confidence),
      is_primary           = CASE WHEN EXCLUDED.is_primary THEN TRUE ELSE profiles.is_primary END,
      creator_id           = COALESCE(profiles.creator_id, EXCLUDED.creator_id),
      updated_at           = NOW();

    v_accounts_upserted := v_accounts_upserted + 1;
  END LOOP;

  -- Funnel edges
  FOR v_edge IN SELECT * FROM JSONB_ARRAY_ELEMENTS(p_funnel_edges)
  LOOP
    SELECT id INTO v_from_id FROM profiles
    WHERE workspace_id = v_workspace_id
      AND platform = (v_edge->>'from_platform')::platform
      AND handle   = v_edge->>'from_handle'
    LIMIT 1;

    SELECT id INTO v_to_id FROM profiles
    WHERE workspace_id = v_workspace_id
      AND platform = (v_edge->>'to_platform')::platform
      AND handle   = v_edge->>'to_handle'
    LIMIT 1;

    IF v_from_id IS NOT NULL AND v_to_id IS NOT NULL THEN
      -- FIX: include creator_id in the INSERT (was missing, violating NOT NULL)
      INSERT INTO funnel_edges (creator_id, workspace_id, from_profile_id, to_profile_id, edge_type, confidence)
      VALUES (
        v_creator_id, v_workspace_id, v_from_id, v_to_id,
        (v_edge->>'edge_type')::edge_type,
        COALESCE((v_edge->>'confidence')::NUMERIC, 0.5)
      )
      ON CONFLICT (from_profile_id, to_profile_id) DO NOTHING;
    END IF;
  END LOOP;

  -- Merge candidate detection (handle similarity)
  FOR v_existing_creator IN
    SELECT DISTINCT c.id FROM creators c
    JOIN profiles p ON p.creator_id = c.id
    WHERE c.workspace_id = v_workspace_id
      AND c.id <> v_creator_id
      AND c.onboarding_status = 'ready'
  LOOP
    IF EXISTS (
      SELECT 1 FROM profiles p1
      JOIN profiles p2 ON p2.creator_id = v_existing_creator
        AND p1.platform = p2.platform
        AND p1.handle = p2.handle
      WHERE p1.creator_id = v_creator_id
    ) THEN
      INSERT INTO creator_merge_candidates (
        workspace_id, creator_a_id, creator_b_id, status, evidence
      ) VALUES (
        v_workspace_id,
        LEAST(v_creator_id, v_existing_creator),
        GREATEST(v_creator_id, v_existing_creator),
        'pending',
        '{"reason": "shared_handle"}'::JSONB
      )
      ON CONFLICT (workspace_id, creator_a_id, creator_b_id) DO NOTHING;

      v_merges_raised := v_merges_raised + 1;
    END IF;
  END LOOP;

  UPDATE discovery_runs SET status = 'completed', completed_at = NOW()
  WHERE id = p_run_id;

  RETURN JSONB_BUILD_OBJECT(
    'creator_id',           v_creator_id,
    'accounts_upserted',    v_accounts_upserted,
    'merge_candidates_raised', v_merges_raised
  );
END;
$function$;
