-- supabase/migrations/20260426030000_commit_discovery_result_v4_update_destination_class.sql
-- Universal URL Harvester v1: ON CONFLICT clause in profile_destination_links
-- INSERT was only updating audit fields (harvest_method, raw_text, harvested_at)
-- but NOT destination_class. This meant buggy rows from prior runs stuck around
-- with stale class values even after fixes (e.g. t.me URLs stuck at 'other'
-- after the resolver was patched to map 'messaging'). Caught by 2026-04-26 smoke.
-- Body identical to 20260426010000 except the ON CONFLICT DO UPDATE clause now
-- includes destination_class.

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

  v_canonical_name := NULLIF(NULLIF(TRIM(p_creator_data->>'canonical_name'), ''), 'Unknown');

  IF v_source = 'manual_add' THEN
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
      NULLIF(v_account->>'follower_count', '')::int,
      (v_account->>'account_type')::account_type,
      COALESCE((v_account->>'is_primary')::boolean, FALSE),
      NULLIF(v_account->>'discovery_confidence', '')::numeric,
      v_account->>'discovery_reason',
      TRUE,
      NOW()
    )
    ON CONFLICT (workspace_id, platform, handle) DO UPDATE SET
      bio = COALESCE(EXCLUDED.bio, profiles.bio),
      display_name = COALESCE(EXCLUDED.display_name, profiles.display_name),
      follower_count = COALESCE(EXCLUDED.follower_count, profiles.follower_count),
      url = COALESCE(EXCLUDED.url, profiles.url),
      account_type = EXCLUDED.account_type,
      discovery_confidence = COALESCE(EXCLUDED.discovery_confidence, profiles.discovery_confidence),
      discovery_reason = COALESCE(EXCLUDED.discovery_reason, profiles.discovery_reason),
      is_active = TRUE,
      updated_at = NOW()
    RETURNING id INTO v_profile_id;

    v_accounts_upserted := v_accounts_upserted + 1;
  END LOOP;

  FOR v_edge IN SELECT jsonb_array_elements(p_funnel_edges)
  LOOP
    SELECT id INTO v_from_pid FROM profiles
    WHERE workspace_id = v_workspace_id AND creator_id = v_creator_id
      AND platform = (v_edge->>'from_platform')::platform
      AND handle = v_edge->>'from_handle' LIMIT 1;
    SELECT id INTO v_to_pid FROM profiles
    WHERE workspace_id = v_workspace_id AND creator_id = v_creator_id
      AND platform = (v_edge->>'to_platform')::platform
      AND handle = v_edge->>'to_handle' LIMIT 1;

    IF v_from_pid IS NOT NULL AND v_to_pid IS NOT NULL THEN
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

  FOR v_url IN SELECT jsonb_array_elements(p_discovered_urls)
  LOOP
    SELECT id INTO v_profile_id FROM profiles
    WHERE workspace_id = v_workspace_id
      AND creator_id = v_creator_id
      AND is_primary = TRUE
    LIMIT 1;

    IF v_profile_id IS NOT NULL THEN
      INSERT INTO profile_destination_links (
        profile_id, canonical_url, destination_class, workspace_id,
        harvest_method, raw_text, harvested_at
      )
      VALUES (
        v_profile_id,
        v_url->>'canonical_url',
        v_url->>'destination_class',
        v_workspace_id,
        v_url->>'harvest_method',
        v_url->>'raw_text',
        NOW()
      )
      ON CONFLICT (profile_id, canonical_url) DO UPDATE SET
        destination_class = EXCLUDED.destination_class,
        harvest_method = COALESCE(EXCLUDED.harvest_method, profile_destination_links.harvest_method),
        raw_text = COALESCE(EXCLUDED.raw_text, profile_destination_links.raw_text),
        harvested_at = NOW();

      v_urls_recorded := v_urls_recorded + 1;
    END IF;
  END LOOP;

  -- discovery_runs has no updated_at column; completed_at carries the signal.
  UPDATE discovery_runs SET
    status = 'completed',
    completed_at = NOW(),
    assets_discovered_count = v_accounts_upserted,
    funnel_edges_discovered_count = jsonb_array_length(p_funnel_edges),
    bulk_import_id = COALESCE(p_bulk_import_id, bulk_import_id)
  WHERE id = p_run_id;

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
