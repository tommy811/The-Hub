-- Fix: bulk_import_creator was missing ::platform cast on p_platform_hint
-- in the discovery_runs INSERT.
--
-- The function declares p_platform_hint TEXT, casts it correctly in the
-- creators INSERT (p_platform_hint::platform) and the profiles INSERT
-- (p_platform_hint::platform), but the third INSERT into discovery_runs
-- passes the raw text. Postgres errors:
--   22P02 column "input_platform_hint" is of type platform but expression
--   is of type text
--
-- This blocks every bulk import via Bulk Paste / Single Handle UI.
-- Same root cause as the 2026-04-25 retry_creator_discovery cast fix
-- (migration 20260425000300); retry_creator was patched then but
-- bulk_import was missed.

CREATE OR REPLACE FUNCTION public.bulk_import_creator(
  p_handle text,
  p_platform_hint text,
  p_tracking_type tracking_type,
  p_tags text[],
  p_user_id uuid,
  p_workspace_id uuid,
  p_bulk_import_id uuid DEFAULT NULL::uuid
)
 RETURNS jsonb
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'public'
AS $function$
DECLARE
  v_bulk_id uuid;
  v_creator_id uuid;
  v_run_id uuid;
  v_profile_id uuid;
BEGIN
  IF p_bulk_import_id IS NULL THEN
    INSERT INTO bulk_imports (workspace_id, initiated_by, seeds_total)
    VALUES (p_workspace_id, p_user_id, 1)
    RETURNING id INTO v_bulk_id;
  ELSE
    v_bulk_id := p_bulk_import_id;
  END IF;

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

  INSERT INTO discovery_runs (
    workspace_id, creator_id, input_handle, input_platform_hint,
    status, attempt_number, initiated_by, started_at,
    bulk_import_id, source
  )
  VALUES (
    p_workspace_id, v_creator_id, p_handle, p_platform_hint::platform,  -- <<< fix: cast to platform enum
    'pending', 1, p_user_id, NOW(),
    v_bulk_id, 'seed'
  )
  RETURNING id INTO v_run_id;

  UPDATE creators SET last_discovery_run_id = v_run_id WHERE id = v_creator_id;

  RETURN jsonb_build_object(
    'bulk_import_id', v_bulk_id,
    'creator_id', v_creator_id,
    'run_id', v_run_id
  );
END;
$function$;
