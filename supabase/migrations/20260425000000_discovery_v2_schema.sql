-- 20260425000000_discovery_v2_schema.sql
-- Discovery v2 — new tables and columns per docs/superpowers/specs/2026-04-24-discovery-v2-design.md §4.
-- Additive only. Feature-flagged rollout via DISCOVERY_V2_ENABLED.

BEGIN;

-- 1. bulk_imports: first-class observable job table
CREATE TABLE bulk_imports (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  workspace_id uuid NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
  initiated_by uuid,
  seeds_total int NOT NULL,
  seeds_committed int NOT NULL DEFAULT 0,
  seeds_failed int NOT NULL DEFAULT 0,
  seeds_blocked_by_budget int NOT NULL DEFAULT 0,
  merge_pass_completed_at timestamptz,
  cost_apify_cents int NOT NULL DEFAULT 0,
  status text NOT NULL DEFAULT 'running'
    CHECK (status IN (
      'running', 'completed', 'completed_with_failures',
      'partial_budget_exceeded', 'cancelled'
    )),
  created_at timestamptz NOT NULL DEFAULT NOW(),
  updated_at timestamptz NOT NULL DEFAULT NOW()
);

CREATE INDEX bulk_imports_workspace_status_idx
  ON bulk_imports (workspace_id, status, created_at DESC);

CREATE TRIGGER trg_bulk_imports_updated_at
  BEFORE UPDATE ON bulk_imports
  FOR EACH ROW EXECUTE FUNCTION set_updated_at();

ALTER TABLE bulk_imports ENABLE ROW LEVEL SECURITY;

CREATE POLICY bulk_imports_workspace_members ON bulk_imports
  FOR ALL TO authenticated
  USING (is_workspace_member(workspace_id))
  WITH CHECK (is_workspace_member(workspace_id));

-- 2. classifier_llm_guesses: cache of LLM-classified URLs
CREATE TABLE classifier_llm_guesses (
  canonical_url text PRIMARY KEY,
  platform_guess platform,
  account_type_guess account_type,
  confidence numeric(3,2) NOT NULL CHECK (confidence >= 0 AND confidence <= 1),
  model_version text NOT NULL,
  classified_at timestamptz NOT NULL DEFAULT NOW()
);

-- No RLS: this is a workspace-agnostic classification cache. URLs don't have
-- workspace scope. Read-only from Python, write via service role only.

-- 3. profile_destination_links: persistent reverse index for identity dedup
CREATE TABLE profile_destination_links (
  profile_id uuid NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
  canonical_url text NOT NULL,
  destination_class text NOT NULL
    CHECK (destination_class IN ('monetization','aggregator','social','other')),
  workspace_id uuid NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
  created_at timestamptz NOT NULL DEFAULT NOW(),
  PRIMARY KEY (profile_id, canonical_url)
);

CREATE INDEX profile_destination_links_url_idx
  ON profile_destination_links (canonical_url);

CREATE INDEX profile_destination_links_class_idx
  ON profile_destination_links (destination_class)
  WHERE destination_class IN ('monetization','aggregator');

CREATE INDEX profile_destination_links_workspace_url_idx
  ON profile_destination_links (workspace_id, canonical_url);

ALTER TABLE profile_destination_links ENABLE ROW LEVEL SECURITY;

CREATE POLICY profile_destination_links_workspace_members ON profile_destination_links
  FOR ALL TO authenticated
  USING (is_workspace_member(workspace_id))
  WITH CHECK (is_workspace_member(workspace_id));

-- 4. discovery_runs additions
ALTER TABLE discovery_runs
  ADD COLUMN bulk_import_id uuid REFERENCES bulk_imports(id) ON DELETE SET NULL,
  ADD COLUMN apify_cost_cents int NOT NULL DEFAULT 0,
  ADD COLUMN source text NOT NULL DEFAULT 'seed'
    CHECK (source IN ('seed','manual_add','retry','auto_expand'));

CREATE INDEX discovery_runs_bulk_import_idx
  ON discovery_runs (bulk_import_id)
  WHERE bulk_import_id IS NOT NULL;

-- 5. profiles additions — audit trail for classification
ALTER TABLE profiles
  ADD COLUMN discovery_reason text;

-- 6. creator_merge_candidates: unique index on canonical pair for idempotency
CREATE UNIQUE INDEX creator_merge_candidates_pair_uniq
  ON creator_merge_candidates (
    LEAST(creator_a_id, creator_b_id),
    GREATEST(creator_a_id, creator_b_id)
  );

COMMIT;
