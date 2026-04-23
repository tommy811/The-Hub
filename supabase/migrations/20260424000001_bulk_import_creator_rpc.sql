-- 20260424000001_bulk_import_creator_rpc.sql
-- Atomic bulk import: insert creator + profile + discovery_run in one transaction.
-- Caller invokes once per handle; collects per-handle errors at the action layer.

CREATE OR REPLACE FUNCTION bulk_import_creator(
  p_handle text,
  p_platform_hint platform,
  p_tracking_type tracking_type,
  p_tags text[],
  p_user_id uuid,
  p_workspace_id uuid
) RETURNS uuid
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
  v_normalized text;
  v_slug text;
  v_creator_id uuid;
  v_run_id uuid;
BEGIN
  IF p_handle IS NULL OR length(trim(p_handle)) = 0 THEN
    RAISE EXCEPTION 'p_handle must be non-empty';
  END IF;
  IF p_workspace_id IS NULL THEN
    RAISE EXCEPTION 'p_workspace_id is required';
  END IF;

  v_normalized := normalize_handle(p_handle);
  -- Ensure slug uniqueness with a short random suffix.
  v_slug := v_normalized || '-' || substr(md5(random()::text || clock_timestamp()::text), 1, 6);

  -- 1. Insert creator (placeholder; discovery enriches later).
  INSERT INTO creators (
    workspace_id, canonical_name, slug, primary_platform,
    known_usernames, tracking_type, tags, onboarding_status,
    import_source, added_by
  ) VALUES (
    p_workspace_id, p_handle, v_slug,
    CASE WHEN p_platform_hint::text = 'other' THEN NULL ELSE p_platform_hint END,
    ARRAY[p_handle], p_tracking_type, COALESCE(p_tags, ARRAY[]::text[]),
    'processing', 'bulk', p_user_id
  )
  RETURNING id INTO v_creator_id;

  -- 2. Insert primary profile so the card shows a handle immediately.
  INSERT INTO profiles (
    workspace_id, creator_id, platform, handle, account_type,
    is_primary, added_by, discovery_confidence
  ) VALUES (
    p_workspace_id, v_creator_id,
    COALESCE(p_platform_hint, 'other'::platform),
    p_handle, 'social', true, p_user_id, 1.0
  );

  -- 3. Insert pending discovery run (Python worker picks it up).
  INSERT INTO discovery_runs (
    workspace_id, creator_id, input_handle, input_platform_hint,
    status, attempt_number, initiated_by
  ) VALUES (
    p_workspace_id, v_creator_id, p_handle, p_platform_hint,
    'pending', 1, p_user_id
  )
  RETURNING id INTO v_run_id;

  -- 4. Link creator → run.
  UPDATE creators SET last_discovery_run_id = v_run_id WHERE id = v_creator_id;

  RETURN v_creator_id;
END;
$$;

-- Grant execute to authenticated and anon (RLS policies still apply via SECURITY DEFINER's
-- own privileges; the function uses workspace_id passed by the caller).
GRANT EXECUTE ON FUNCTION bulk_import_creator(text, platform, tracking_type, text[], uuid, uuid) TO authenticated, anon, service_role;
