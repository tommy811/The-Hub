-- Fix: retry_creator_discovery must update creators.last_discovery_run_id.
--
-- Without this, every retry leaves the creator pointing at the OLD run.
-- The DiscoveryProgress UI polls by last_discovery_run_id and immediately
-- sees the old run's terminal status (failed/completed), so the new
-- run's spinner is stuck at "Queued 0%" forever — the UI never observes
-- the actual in-flight run.
--
-- bulk_import_creator already updates last_discovery_run_id correctly
-- (verified). This patch only touches retry_creator_discovery.
--
-- Behavior: identical to the prior version except the UPDATE creators
-- now also writes last_discovery_run_id = v_run_id (the new run).

CREATE OR REPLACE FUNCTION public.retry_creator_discovery(p_creator_id uuid, p_user_id uuid)
 RETURNS uuid
 LANGUAGE plpgsql
AS $function$
DECLARE
  v_run_id           UUID;
  v_ws_id            UUID;
  v_attempts         INT;
  v_input_handle     TEXT;
  v_platform_hint    TEXT;
BEGIN
  SELECT workspace_id INTO v_ws_id FROM creators WHERE id = p_creator_id;
  SELECT COALESCE(MAX(attempt_number), 0) INTO v_attempts
  FROM discovery_runs WHERE creator_id = p_creator_id;

  -- Carry forward handle + platform from the most recent run that had them
  SELECT input_handle, input_platform_hint
  INTO   v_input_handle, v_platform_hint
  FROM   discovery_runs
  WHERE  creator_id = p_creator_id
    AND  input_handle IS NOT NULL
  ORDER BY created_at DESC
  LIMIT 1;

  INSERT INTO discovery_runs (workspace_id, creator_id, initiated_by, status, attempt_number, input_handle, input_platform_hint)
  VALUES (v_ws_id, p_creator_id, p_user_id, 'pending', v_attempts + 1, v_input_handle, v_platform_hint::platform)
  RETURNING id INTO v_run_id;

  UPDATE creators SET
    onboarding_status     = 'processing',
    last_discovery_run_id = v_run_id,   -- <<< fix: keep pointer fresh
    last_discovery_error  = NULL,
    updated_at            = NOW()
  WHERE id = p_creator_id;

  RETURN v_run_id;
END;
$function$;
