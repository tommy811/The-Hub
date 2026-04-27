-- Content Scraper follow-up — durable per-profile scrape run observability.
-- Manual CLI and future webhook paths write one final-status row per profile attempt.

CREATE TABLE IF NOT EXISTS scrape_runs (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  workspace_id uuid NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
  creator_id uuid REFERENCES creators(id) ON DELETE SET NULL,
  profile_id uuid REFERENCES profiles(id) ON DELETE SET NULL,
  platform platform NOT NULL,
  source text NOT NULL DEFAULT 'manual_cli',
  status text NOT NULL CHECK (status IN ('succeeded', 'skipped', 'failed')),
  reason text,
  posts_fetched integer NOT NULL DEFAULT 0,
  posts_upserted integer NOT NULL DEFAULT 0,
  outliers_flagged integer NOT NULL DEFAULT 0,
  apify_actor_id text,
  apify_run_id text,
  apify_dataset_id text,
  error_message text,
  started_at timestamptz NOT NULL DEFAULT now(),
  completed_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS scrape_runs_workspace_completed_idx
  ON scrape_runs (workspace_id, completed_at DESC);

CREATE INDEX IF NOT EXISTS scrape_runs_profile_completed_idx
  ON scrape_runs (profile_id, completed_at DESC);

CREATE INDEX IF NOT EXISTS scrape_runs_status_idx
  ON scrape_runs (workspace_id, status, completed_at DESC);

ALTER TABLE scrape_runs ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "members select scrape_runs" ON scrape_runs;
CREATE POLICY "members select scrape_runs"
  ON scrape_runs FOR SELECT
  USING (is_workspace_member(workspace_id));

DROP POLICY IF EXISTS "service role inserts scrape_runs" ON scrape_runs;
CREATE POLICY "service role inserts scrape_runs"
  ON scrape_runs FOR INSERT
  WITH CHECK (auth.role() = 'service_role');

COMMENT ON TABLE scrape_runs IS
  'Per-profile content scraper attempts. Tracks manual CLI now; cron/webhooks can reuse without schema changes.';
