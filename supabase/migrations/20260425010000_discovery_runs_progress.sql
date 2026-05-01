-- Adds progress tracking to discovery_runs so the UI can render a real
-- progress bar + label while the pipeline is in flight.
--
-- progress_pct  : 0..100, NOT NULL DEFAULT 0
-- progress_label: short 2-3 word label for the current pipeline stage
--                 (Fetching profile / Resolving links / Enriching accounts /
--                  Analyzing / Done). Nullable: rows created before the
--                  pipeline starts have no label yet.

ALTER TABLE discovery_runs
  ADD COLUMN IF NOT EXISTS progress_pct smallint NOT NULL DEFAULT 0,
  ADD COLUMN IF NOT EXISTS progress_label text;

COMMENT ON COLUMN discovery_runs.progress_pct IS
  'Pipeline progress 0..100. Set by the Python pipeline at each stage; UI polls + renders.';
COMMENT ON COLUMN discovery_runs.progress_label IS
  'Short 2-3 word label for the current stage (e.g. "Fetching profile"). Updated by pipeline.';
