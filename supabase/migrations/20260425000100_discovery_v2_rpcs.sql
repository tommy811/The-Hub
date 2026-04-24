-- 20260425000100_discovery_v2_rpcs.sql
-- Discovery v2 RPC surface per spec §4.4.
-- 1. commit_discovery_result: new p_discovered_urls + p_bulk_import_id params
-- 2. bulk_import_creator: creates bulk_imports row, returns bulk_import_id + run_ids
-- 3. run_cross_workspace_merge_pass: new RPC for cross-workspace identity dedup

BEGIN;

-- ============================================================================
-- 1. commit_discovery_result v2
-- ============================================================================

CREATE OR REPLACE FUNCTION commit_discovery_result(
  p_run_id uuid,
  p_creator_data jsonb,
  p_accounts jsonb,
  p_funnel_edges jsonb,
  p_discovered_urls jsonb DEFAULT '[]'::jsonb,
  p_bulk_import_id uuid DEFAULT NULL
)
RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
  v_run record;
  v_creator_id uuid;
  v_workspace_id uuid;
  v_accounts_upserted int := 0;
  v_urls_recorded int := 0;
  v_merge_candidates_raised int := 0;
  v_account jsonb;
  v_edge jsonb;
  v_url jsonb;
  v_profile_id uuid;
  v_from_pid uuid;
  v_to_pid uuid;
  v_source text;
  v_canonical_name text;
BEGIN
  SELECT * INTO v_run FROM discovery_runs WHERE id = p_run_id;
  IF NOT FOUND THEN
    RAISE EXCEPTION 'discovery_run % not found', p_run_id;
  END IF;

  v_creator_id := v_run.creator_id;
  v_workspace_id := v_run.workspace_id;
  v_source := v_run.source;

  -- Enrich creator — but on manual_add, preserve human-confirmed canonical fields
  v_canonical_name := NULLIF(NULLIF(TRIM(p_creator_data->>'canonical_name'), ''), 'Unknown');

  IF v_source = 'manual_add' THEN
    -- Only union-merge known_usernames; do not overwrite identity fields
    UPDATE creators SET
      known_usernames = (
        SELECT ARRAY(
          SELECT DISTINCT unnest(
            COALESCE(known_usernames, ARRAY[]::text[]) ||
            COALESCE(ARRAY(SELECT jsonb_array_elements_text(p_creator_data->'known_usernames')),
                     ARRAY[]::text[])
          )
        )
      ),
      updated_at = NOW()
    WHERE id = v_creator_id;
  ELSE
    UPDATE creators SET
      canonical_name = COALESCE(v_canonical_name, canonical_name),
      known_usernames = COALESCE(
        ARRAY(SELECT DISTINCT unnest(
          COALESCE(known_usernames, ARRAY[]::text[]) ||
          COALESCE(ARRAY(SELECT jsonb_array_elements_text(p_creator_data->'known_usernames')),
                   ARRAY[]::text[])
        )),
        known_usernames
      ),
      display_name_variants = COALESCE(
        ARRAY(SELECT DISTINCT unnest(
          COALESCE(display_name_variants, ARRAY[]::text[]) ||
          COALESCE(ARRAY(SELECT jsonb_array_elements_text(p_creator_data->'display_name_variants')),
                   ARRAY[]::text[])
        )),
        display_name_variants
      ),
      primary_niche = COALESCE(p_creator_data->>'primary_niche', primary_niche),
      monetization_model = COALESCE(
        NULLIF(p_creator_data->>'monetization_model', '')::monetization_model,
        monetization_model
      ),
      onboarding_status = 'ready',
      updated_at = NOW()
    WHERE id = v_creator_id;
  END IF;

  -- Upsert each proposed account as a profile row
  FOR v_account IN SELECT jsonb_array_elements(p_accounts)
  LOOP
    INSERT INTO profiles (
      workspace_id, creator_id, platform, handle, url, display_name,
      bio, follower_count, account_type, is_primary, discovery_confidence,
      discovery_reason, is_active, updated_at
    )
    VALUES (
      v_workspace_id, v_creator_id,
      (v_account->>'platform')::platform,
      v_account->>'handle',
      v_account->>'url',
      v_account->>'display_name',
      v_account->>'bio',
      (v_account->>'follower_count')::int,
      COALESCE((v_account->>'account_type')::account_type, 'social'),
      COALESCE((v_account->>'is_primary')::boolean, FALSE),
      (v_account->>'discovery_confidence')::numeric,
      v_account->>'reasoning',
      TRUE,
      NOW()
    )
    ON CONFLICT (workspace_id, platform, handle) DO UPDATE SET
      display_name = COALESCE(EXCLUDED.display_name, profiles.display_name),
      bio = COALESCE(EXCLUDED.bio, profiles.bio),
      follower_count = COALESCE(EXCLUDED.follower_count, profiles.follower_count),
      url = COALESCE(EXCLUDED.url, profiles.url),
      updated_at = NOW()
    RETURNING id INTO v_profile_id;

    v_accounts_upserted := v_accounts_upserted + 1;
  END LOOP;

  -- Insert funnel edges (resolve from/to handles to profile_ids)
  FOR v_edge IN SELECT jsonb_array_elements(p_funnel_edges)
  LOOP
    SELECT id INTO v_from_pid FROM profiles
    WHERE workspace_id = v_workspace_id
      AND platform = (v_edge->>'from_platform')::platform
      AND handle = v_edge->>'from_handle'
    LIMIT 1;

    SELECT id INTO v_to_pid FROM profiles
    WHERE workspace_id = v_workspace_id
      AND platform = (v_edge->>'to_platform')::platform
      AND handle = v_edge->>'to_handle'
    LIMIT 1;

    IF v_from_pid IS NOT NULL AND v_to_pid IS NOT NULL AND v_from_pid <> v_to_pid THEN
      INSERT INTO funnel_edges (
        workspace_id, creator_id, from_profile_id, to_profile_id,
        edge_type, confidence, detected_at
      )
      VALUES (
        v_workspace_id, v_creator_id, v_from_pid, v_to_pid,
        COALESCE((v_edge->>'edge_type')::edge_type, 'inferred'),
        (v_edge->>'confidence')::numeric,
        NOW()
      )
      ON CONFLICT DO NOTHING;
    END IF;
  END LOOP;

  -- Record discovered URLs into profile_destination_links (reverse index)
  FOR v_url IN SELECT jsonb_array_elements(p_discovered_urls)
  LOOP
    -- Find the profile this URL was discovered from. If the URL matches an
    -- existing profile on (platform, handle-in-URL), link there; otherwise
    -- link to the seed's primary profile for this creator.
    SELECT id INTO v_profile_id FROM profiles
    WHERE workspace_id = v_workspace_id
      AND creator_id = v_creator_id
      AND is_primary = TRUE
    LIMIT 1;

    IF v_profile_id IS NOT NULL THEN
      INSERT INTO profile_destination_links (
        profile_id, canonical_url, destination_class, workspace_id
      )
      VALUES (
        v_profile_id,
        v_url->>'canonical_url',
        v_url->>'destination_class',
        v_workspace_id
      )
      ON CONFLICT (profile_id, canonical_url) DO NOTHING;

      v_urls_recorded := v_urls_recorded + 1;
    END IF;
  END LOOP;

  -- Mark the run as completed
  UPDATE discovery_runs SET
    status = 'completed',
    completed_at = NOW(),
    assets_discovered_count = v_accounts_upserted,
    funnel_edges_discovered_count = jsonb_array_length(p_funnel_edges),
    bulk_import_id = COALESCE(p_bulk_import_id, bulk_import_id),
    updated_at = NOW()
  WHERE id = p_run_id;

  -- Bump bulk_imports counter if applicable
  IF p_bulk_import_id IS NOT NULL THEN
    UPDATE bulk_imports SET
      seeds_committed = seeds_committed + 1,
      updated_at = NOW()
    WHERE id = p_bulk_import_id;
  END IF;

  RETURN jsonb_build_object(
    'creator_id', v_creator_id,
    'accounts_upserted', v_accounts_upserted,
    'merge_candidates_raised', v_merge_candidates_raised,
    'urls_recorded', v_urls_recorded
  );
END;
$$;

GRANT EXECUTE ON FUNCTION commit_discovery_result(uuid, jsonb, jsonb, jsonb, jsonb, uuid)
  TO authenticated, service_role;


-- ============================================================================
-- 2. bulk_import_creator v2: creates bulk_imports row, returns structured result
-- ============================================================================

CREATE OR REPLACE FUNCTION bulk_import_creator(
  p_handle text,
  p_platform_hint text,
  p_tracking_type tracking_type,
  p_tags text[],
  p_user_id uuid,
  p_workspace_id uuid,
  p_bulk_import_id uuid DEFAULT NULL
)
RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
  v_bulk_id uuid;
  v_creator_id uuid;
  v_run_id uuid;
  v_profile_id uuid;
BEGIN
  -- Create bulk_imports row if not passed in (single-handle path)
  IF p_bulk_import_id IS NULL THEN
    INSERT INTO bulk_imports (workspace_id, initiated_by, seeds_total)
    VALUES (p_workspace_id, p_user_id, 1)
    RETURNING id INTO v_bulk_id;
  ELSE
    v_bulk_id := p_bulk_import_id;
  END IF;

  -- Create creator row (placeholder — canonical_name = handle until discovery fills)
  INSERT INTO creators (
    workspace_id, canonical_name, slug, known_usernames, primary_platform,
    tracking_type, tags, onboarding_status, import_source, added_by
  )
  VALUES (
    p_workspace_id, p_handle,
    p_handle || '-' || substring(gen_random_uuid()::text, 1, 16),
    ARRAY[p_handle],
    p_platform_hint::platform,
    p_tracking_type,
    COALESCE(p_tags, ARRAY[]::text[]),
    'processing',
    'bulk_import',
    p_user_id
  )
  RETURNING id INTO v_creator_id;

  -- Create primary profile stub
  INSERT INTO profiles (
    workspace_id, creator_id, platform, handle,
    tracking_type, tags, is_primary, is_active, added_by,
    discovery_reason, discovery_confidence
  )
  VALUES (
    p_workspace_id, v_creator_id, p_platform_hint::platform, p_handle,
    p_tracking_type, COALESCE(p_tags, ARRAY[]::text[]), TRUE, TRUE, p_user_id,
    'bulk_import', 1.0
  )
  RETURNING id INTO v_profile_id;

  -- Create pending discovery_run linked to bulk_import
  INSERT INTO discovery_runs (
    workspace_id, creator_id, input_handle, input_platform_hint,
    status, attempt_number, initiated_by, started_at,
    bulk_import_id, source
  )
  VALUES (
    p_workspace_id, v_creator_id, p_handle, p_platform_hint,
    'pending', 1, p_user_id, NOW(),
    v_bulk_id, 'seed'
  )
  RETURNING id INTO v_run_id;

  -- Link creator to the run
  UPDATE creators SET last_discovery_run_id = v_run_id WHERE id = v_creator_id;

  RETURN jsonb_build_object(
    'bulk_import_id', v_bulk_id,
    'creator_id', v_creator_id,
    'run_id', v_run_id
  );
END;
$$;

GRANT EXECUTE ON FUNCTION bulk_import_creator(text, text, tracking_type, text[], uuid, uuid, uuid)
  TO authenticated, anon, service_role;


-- ============================================================================
-- 3. run_cross_workspace_merge_pass: raise merge candidates from inverted index
-- ============================================================================

CREATE OR REPLACE FUNCTION run_cross_workspace_merge_pass(
  p_workspace_id uuid,
  p_bulk_import_id uuid DEFAULT NULL
)
RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
  v_candidates_raised int := 0;
  v_bucket record;
BEGIN
  -- Find URL buckets (in workspace) with >1 distinct creator attached
  FOR v_bucket IN
    SELECT
      pdl.canonical_url,
      pdl.destination_class,
      array_agg(DISTINCT p.creator_id) AS creator_ids
    FROM profile_destination_links pdl
    JOIN profiles p ON p.id = pdl.profile_id
    WHERE pdl.workspace_id = p_workspace_id
      AND pdl.destination_class IN ('monetization', 'aggregator')
      AND p.creator_id IS NOT NULL
    GROUP BY pdl.canonical_url, pdl.destination_class
    HAVING COUNT(DISTINCT p.creator_id) > 1
  LOOP
    -- For every pair of creator_ids in the bucket, insert a merge candidate
    -- (ordered so a < b, absorbed by the unique index on re-runs)
    INSERT INTO creator_merge_candidates (
      workspace_id, creator_a_id, creator_b_id, confidence, evidence, status
    )
    SELECT
      p_workspace_id,
      LEAST(a.id, b.id),
      GREATEST(a.id, b.id),
      1.0,
      jsonb_build_object(
        'reason',
        CASE v_bucket.destination_class
          WHEN 'monetization' THEN 'shared_monetization_url'
          ELSE 'shared_aggregator_url'
        END,
        'shared_url', v_bucket.canonical_url,
        'class', v_bucket.destination_class
      ),
      'pending'
    FROM unnest(v_bucket.creator_ids) AS a(id)
    CROSS JOIN unnest(v_bucket.creator_ids) AS b(id)
    WHERE a.id < b.id
    ON CONFLICT (LEAST(creator_a_id, creator_b_id), GREATEST(creator_a_id, creator_b_id))
      DO UPDATE SET evidence = EXCLUDED.evidence;

    v_candidates_raised := v_candidates_raised + 1;
  END LOOP;

  -- Mark bulk_import merge pass complete
  IF p_bulk_import_id IS NOT NULL THEN
    UPDATE bulk_imports SET
      merge_pass_completed_at = NOW(),
      status = CASE
        WHEN seeds_failed > 0 AND seeds_blocked_by_budget > 0 THEN 'partial_budget_exceeded'
        WHEN seeds_failed > 0 THEN 'completed_with_failures'
        WHEN seeds_blocked_by_budget > 0 THEN 'partial_budget_exceeded'
        ELSE 'completed'
      END,
      updated_at = NOW()
    WHERE id = p_bulk_import_id;
  END IF;

  RETURN jsonb_build_object(
    'buckets_evaluated', v_candidates_raised,
    'bulk_import_id', p_bulk_import_id
  );
END;
$$;

GRANT EXECUTE ON FUNCTION run_cross_workspace_merge_pass(uuid, uuid)
  TO authenticated, service_role;

COMMIT;
