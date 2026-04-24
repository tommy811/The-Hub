-- 20260424150000_create_edge_type_enum.sql
-- Fix latent crash in commit_discovery_result: the RPC casts
-- (v_edge->>'edge_type')::edge_type but no such enum existed.
-- funnel_edges is currently empty, so converting the column type is safe.

BEGIN;

-- Guard: abort if any rows slipped in since the audit
DO $$
DECLARE
  row_count int;
BEGIN
  SELECT COUNT(*) INTO row_count FROM funnel_edges;
  IF row_count > 0 THEN
    RAISE EXCEPTION
      'funnel_edges has % row(s). Review existing edge_type values before migrating.',
      row_count;
  END IF;
END $$;

CREATE TYPE edge_type AS ENUM (
  'link_in_bio',
  'direct_link',
  'cta_mention',
  'qr_code',
  'inferred'
);

-- The existing CHECK constraint compares edge_type (text) against text literals;
-- after the type conversion the operator edge_type = text no longer exists,
-- and the constraint is redundant once the column is an enum.
ALTER TABLE funnel_edges
  DROP CONSTRAINT funnel_edges_edge_type_check;

-- Drop the text default so the column can change type, then restore it typed.
ALTER TABLE funnel_edges
  ALTER COLUMN edge_type DROP DEFAULT;

ALTER TABLE funnel_edges
  ALTER COLUMN edge_type TYPE edge_type USING edge_type::edge_type;

ALTER TABLE funnel_edges
  ALTER COLUMN edge_type SET DEFAULT 'inferred'::edge_type;

COMMIT;
