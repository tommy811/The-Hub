-- 20260424000000_consolidate_last_discovery_run_id.sql
-- Drift fix: collapse the duplicate last_discovery_run_id columns on creators.
-- Live DB has both `last_discovery_run_id` (no FK) and `last_discovery_run_id_fk` (FK→discovery_runs.id).
-- This migration drops the no-FK column and renames the FK column to take its place.

BEGIN;

-- Backfill: copy any value from the no-FK column into the FK column where the FK column is null.
UPDATE creators
SET last_discovery_run_id_fk = last_discovery_run_id
WHERE last_discovery_run_id_fk IS NULL
  AND last_discovery_run_id IS NOT NULL
  AND EXISTS (SELECT 1 FROM discovery_runs WHERE id = creators.last_discovery_run_id);

-- Drop the no-FK column.
ALTER TABLE creators DROP COLUMN last_discovery_run_id;

-- Rename FK column to take its place.
ALTER TABLE creators RENAME COLUMN last_discovery_run_id_fk TO last_discovery_run_id;

-- Update the commit_discovery_result RPC body to write to the (now-only) column name.
-- (The function body in the original 20240102000000_creator_layer.sql already writes
-- `last_discovery_run_id = p_run_id` — after the rename, that name resolves correctly.
-- No function redefinition needed.)

COMMIT;
