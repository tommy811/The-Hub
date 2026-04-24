-- 20260424170000_phase_2_schema_migration.sql
--
-- Phase 2 entry-point schema changes per PROJECT_STATE §4.2:
--  - New enums:  trend_type, llm_model, content_archetype
--  - Extend enum: label_type += 'creator_niche'
--  - New tables: trends, creator_label_assignments
--  - creators:   ADD archetype content_archetype (nullable), ADD vibe content_vibe (nullable)
--  - scraped_content: ADD trend_id uuid REFERENCES trends(id) (nullable)
--  - content_analysis: DROP archetype, DROP vibe (moved to creators — table is empty, safe)
--
-- content_labels.usage_count increment trigger is reused on creator_label_assignments.

BEGIN;

-- Safety guard: content_analysis MUST be empty before dropping archetype/vibe
DO $$
DECLARE
  row_count int;
BEGIN
  SELECT COUNT(*) INTO row_count FROM content_analysis;
  IF row_count > 0 THEN
    RAISE EXCEPTION
      'content_analysis has % row(s). Moving archetype/vibe to creators would lose per-post data. Review before migrating.',
      row_count;
  END IF;
END $$;

-- ---------- Enums ----------

CREATE TYPE trend_type AS ENUM (
  'audio', 'dance', 'lipsync', 'transition', 'meme', 'challenge'
);

CREATE TYPE llm_model AS ENUM (
  'gemini_pro', 'gemini_flash', 'claude_opus', 'claude_sonnet'
);

CREATE TYPE content_archetype AS ENUM (
  'the_jester',    'the_caregiver', 'the_lover',     'the_everyman',
  'the_creator',   'the_hero',      'the_sage',      'the_innocent',
  'the_explorer',  'the_rebel',     'the_magician',  'the_ruler'
);

ALTER TYPE label_type ADD VALUE IF NOT EXISTS 'creator_niche';

-- ---------- trends table ----------

CREATE TABLE trends (
  id               uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
  workspace_id     uuid        NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
  name             text        NOT NULL,
  trend_type       trend_type  NOT NULL,
  audio_signature  text,
  audio_artist     text,
  audio_title      text,
  description      text,
  usage_count      integer     NOT NULL DEFAULT 0,
  is_canonical     boolean     NOT NULL DEFAULT true,
  peak_detected_at timestamptz,
  created_at       timestamptz NOT NULL DEFAULT NOW(),
  updated_at       timestamptz NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX trends_workspace_audio_signature_unique
  ON trends (workspace_id, audio_signature)
  WHERE audio_signature IS NOT NULL;

CREATE INDEX trends_workspace_id_idx ON trends (workspace_id);
CREATE INDEX trends_trend_type_idx  ON trends (trend_type);

CREATE TRIGGER trends_set_updated_at
  BEFORE UPDATE ON trends
  FOR EACH ROW EXECUTE FUNCTION set_updated_at();

ALTER TABLE trends ENABLE ROW LEVEL SECURITY;

CREATE POLICY trends_workspace_member_select ON trends
  FOR SELECT USING (is_workspace_member(workspace_id));

CREATE POLICY trends_workspace_member_all ON trends
  FOR ALL USING (is_workspace_member(workspace_id))
  WITH CHECK (is_workspace_member(workspace_id));

-- ---------- creator_label_assignments table ----------
-- Mirrors content_label_assignments. Reuses increment_label_usage trigger
-- (which is table-agnostic — updates content_labels.usage_count based on NEW.label_id).

CREATE TABLE creator_label_assignments (
  creator_id     uuid          NOT NULL REFERENCES creators(id)       ON DELETE CASCADE,
  label_id       uuid          NOT NULL REFERENCES content_labels(id) ON DELETE CASCADE,
  assigned_by_ai boolean       NOT NULL DEFAULT false,
  confidence     numeric(3, 2),
  created_at     timestamptz   NOT NULL DEFAULT NOW(),
  PRIMARY KEY (creator_id, label_id)
);

CREATE INDEX creator_label_assignments_creator_idx ON creator_label_assignments (creator_id);
CREATE INDEX creator_label_assignments_label_idx   ON creator_label_assignments (label_id);

CREATE TRIGGER creator_label_assignments_increment_usage
  AFTER INSERT ON creator_label_assignments
  FOR EACH ROW EXECUTE FUNCTION increment_label_usage();

ALTER TABLE creator_label_assignments ENABLE ROW LEVEL SECURITY;

-- RLS inherited from creators via join (same pattern as content_label_assignments)
CREATE POLICY creator_label_assignments_workspace_member_select ON creator_label_assignments
  FOR SELECT USING (
    EXISTS (
      SELECT 1 FROM creators c
      WHERE c.id = creator_label_assignments.creator_id
        AND is_workspace_member(c.workspace_id)
    )
  );

CREATE POLICY creator_label_assignments_workspace_member_all ON creator_label_assignments
  FOR ALL USING (
    EXISTS (
      SELECT 1 FROM creators c
      WHERE c.id = creator_label_assignments.creator_id
        AND is_workspace_member(c.workspace_id)
    )
  )
  WITH CHECK (
    EXISTS (
      SELECT 1 FROM creators c
      WHERE c.id = creator_label_assignments.creator_id
        AND is_workspace_member(c.workspace_id)
    )
  );

-- ---------- Column additions ----------

ALTER TABLE creators
  ADD COLUMN archetype content_archetype,
  ADD COLUMN vibe      content_vibe;

ALTER TABLE scraped_content
  ADD COLUMN trend_id uuid REFERENCES trends(id) ON DELETE SET NULL;

CREATE INDEX scraped_content_trend_id_idx ON scraped_content (trend_id);

-- ---------- Column drops from content_analysis ----------

ALTER TABLE content_analysis
  DROP COLUMN archetype,
  DROP COLUMN vibe;

COMMIT;
