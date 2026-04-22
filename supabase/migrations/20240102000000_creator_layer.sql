-- ============================================================
-- THE HUB — CREATOR LAYER MIGRATION
-- Run in Supabase SQL Editor AFTER the existing schema is applied.
-- Adds the creator-centric architecture on top of the existing
-- platform-first schema. Does NOT modify existing tables' columns
-- except to ADD new nullable columns to `profiles`.
-- Safe to run on a fresh DB too — uses IF NOT EXISTS throughout.
-- ============================================================


-- ============================================================
-- STEP 1: Extend existing enums
-- NOTE: ALTER TYPE ADD VALUE cannot run inside a transaction block.
-- Run these statements first, alone, if your client wraps in a transaction.
-- Supabase SQL Editor runs each statement independently — you're fine.
-- ============================================================

ALTER TYPE platform ADD VALUE IF NOT EXISTS 'onlyfans';
ALTER TYPE platform ADD VALUE IF NOT EXISTS 'fanvue';
ALTER TYPE platform ADD VALUE IF NOT EXISTS 'fanplace';
ALTER TYPE platform ADD VALUE IF NOT EXISTS 'amazon_storefront';
ALTER TYPE platform ADD VALUE IF NOT EXISTS 'tiktok_shop';
ALTER TYPE platform ADD VALUE IF NOT EXISTS 'linktree';
ALTER TYPE platform ADD VALUE IF NOT EXISTS 'beacons';
ALTER TYPE platform ADD VALUE IF NOT EXISTS 'custom_domain';
ALTER TYPE platform ADD VALUE IF NOT EXISTS 'telegram_channel';
ALTER TYPE platform ADD VALUE IF NOT EXISTS 'telegram_cupidbot';
ALTER TYPE platform ADD VALUE IF NOT EXISTS 'facebook';
ALTER TYPE platform ADD VALUE IF NOT EXISTS 'other';
-- Note: 'patreon' already exists in the original enum — no action needed.

ALTER TYPE post_type ADD VALUE IF NOT EXISTS 'story_highlight';
ALTER TYPE post_type ADD VALUE IF NOT EXISTS 'youtube_short';
ALTER TYPE post_type ADD VALUE IF NOT EXISTS 'youtube_long';
ALTER TYPE post_type ADD VALUE IF NOT EXISTS 'other';

ALTER TYPE signal_type ADD VALUE IF NOT EXISTS 'new_monetization_detected';


-- ============================================================
-- STEP 2: New enums
-- Using DO blocks so this is safe to re-run (IF NOT EXISTS pattern).
-- ============================================================

DO $$ BEGIN
  CREATE TYPE account_type AS ENUM (
    'social',        -- IG, TikTok, YouTube, Facebook, Twitter, LinkedIn
    'monetization',  -- OF, Fanvue, Fanplace, Amazon storefront, TikTok Shop
    'link_in_bio',   -- Linktree, Beacons, custom domain landing pages
    'messaging',     -- Telegram channel, cupidbot deployment
    'other'
  );
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
  CREATE TYPE onboarding_status AS ENUM (
    'processing',  -- Gemini discovery is running
    'ready',       -- Discovery complete, full network resolved
    'failed',      -- Discovery errored — retry available
    'archived'     -- Soft-deleted
  );
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
  CREATE TYPE monetization_model AS ENUM (
    'subscription', 'tips', 'ppv', 'affiliate', 'brand_deals',
    'ecommerce', 'coaching', 'saas', 'mixed', 'unknown'
  );
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
  CREATE TYPE discovery_run_status AS ENUM (
    'pending',     -- queued, not yet started
    'processing',  -- Gemini call in flight
    'completed',   -- committed to DB
    'failed'       -- errored, see error_message
  );
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
  CREATE TYPE merge_candidate_status AS ENUM (
    'pending',   -- awaiting human review
    'merged',    -- merge_creators() was called
    'dismissed'  -- confirmed as different people
  );
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
  CREATE TYPE label_type AS ENUM (
    'content_format',  -- GRWM, tutorial, comedy sketch, vlog
    'trend_pattern',   -- specific viral trends (e.g. glow-up, lipsync)
    'hook_style',      -- cold open, question hook, transformation
    'visual_style',    -- minimalist, cinematic, raw/lo-fi
    'other'
  );
EXCEPTION WHEN duplicate_object THEN NULL; END $$;


-- ============================================================
-- STEP 3: `creators` table — the new root entity
-- One creator owns many platform accounts (rows in `profiles`).
-- ============================================================

CREATE TABLE IF NOT EXISTS creators (
  id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  workspace_id          UUID REFERENCES workspaces(id) ON DELETE CASCADE NOT NULL,
  canonical_name        TEXT NOT NULL,
  slug                  TEXT NOT NULL,
  -- All handles this creator is known by across all platforms.
  -- e.g. {"vikingbarbie", "viking.barbie", "vikingb"}
  -- GIN-indexed for fast membership queries.
  known_usernames       TEXT[] DEFAULT '{}',
  -- Display name variations: "Viking Barbie", "Viking Barbie 🔥"
  display_name_variants TEXT[] DEFAULT '{}',
  primary_niche         TEXT,
  primary_platform      platform,
  monetization_model    monetization_model DEFAULT 'unknown',
  tracking_type         tracking_type DEFAULT 'unreviewed',
  tags                  TEXT[] DEFAULT '{}',
  notes                 TEXT,
  onboarding_status     onboarding_status DEFAULT 'processing',
  import_source         TEXT DEFAULT 'bulk',
  -- Set after first successful discovery run (FK added after discovery_runs exists)
  last_discovery_run_id UUID,
  last_discovery_error  TEXT,
  added_by              UUID REFERENCES auth.users(id),
  created_at            TIMESTAMPTZ DEFAULT NOW(),
  updated_at            TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE (workspace_id, slug)
);


-- ============================================================
-- STEP 4: Add new columns to existing `profiles` table
-- `profiles` IS our creator_accounts going forward.
-- All new columns are nullable so existing rows are unaffected.
-- ============================================================

ALTER TABLE profiles
  ADD COLUMN IF NOT EXISTS creator_id           UUID REFERENCES creators(id) ON DELETE SET NULL,
  ADD COLUMN IF NOT EXISTS account_type         account_type DEFAULT 'social',
  ADD COLUMN IF NOT EXISTS url                  TEXT,
  ADD COLUMN IF NOT EXISTS discovery_confidence NUMERIC(3,2),
  ADD COLUMN IF NOT EXISTS updated_at           TIMESTAMPTZ DEFAULT NOW();


-- ============================================================
-- STEP 5: `discovery_runs` — processing log (invisible to users)
-- One row per creator per discovery attempt.
-- ============================================================

CREATE TABLE IF NOT EXISTS discovery_runs (
  id                           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  workspace_id                 UUID REFERENCES workspaces(id) ON DELETE CASCADE NOT NULL,
  creator_id                   UUID REFERENCES creators(id) ON DELETE CASCADE NOT NULL,
  input_handle                 TEXT,
  input_url                    TEXT,
  input_platform_hint          platform,
  input_screenshot_path        TEXT,  -- Supabase Storage path if screenshot used
  status                       discovery_run_status DEFAULT 'pending',
  raw_gemini_response          JSONB,
  assets_discovered_count      INT DEFAULT 0,
  funnel_edges_discovered_count INT DEFAULT 0,
  merge_candidates_raised      INT DEFAULT 0,
  initiated_by                 UUID REFERENCES auth.users(id),
  started_at                   TIMESTAMPTZ,
  completed_at                 TIMESTAMPTZ,
  error_message                TEXT,
  attempt_number               INT DEFAULT 1,
  created_at                   TIMESTAMPTZ DEFAULT NOW()
);

-- Now that discovery_runs exists, add the FK on creators
ALTER TABLE creators
  ADD CONSTRAINT IF NOT EXISTS fk_creators_last_run
  FOREIGN KEY (last_discovery_run_id)
  REFERENCES discovery_runs(id)
  ON DELETE SET NULL;


-- ============================================================
-- STEP 6: `creator_merge_candidates`
-- Raised when a discovered handle already exists under a different creator.
-- Human reviews in UI and chooses merge or dismiss.
-- ============================================================

CREATE TABLE IF NOT EXISTS creator_merge_candidates (
  id                   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  workspace_id         UUID REFERENCES workspaces(id) ON DELETE CASCADE NOT NULL,
  -- creator_a_id < creator_b_id (enforced by CHECK) — prevents duplicate pairs
  creator_a_id         UUID REFERENCES creators(id) ON DELETE CASCADE NOT NULL,
  creator_b_id         UUID REFERENCES creators(id) ON DELETE CASCADE NOT NULL,
  confidence           NUMERIC(3,2) NOT NULL CHECK (confidence >= 0 AND confidence <= 1),
  -- Array of matching signals, e.g.:
  -- [{"signal": "handle_collision", "platform": "instagram", "handle": "vikingbarbie"}]
  -- [{"signal": "handle_similarity", "score": 0.93, "handles": ["viking.barbie","vikingbarbie"]}]
  evidence             JSONB NOT NULL DEFAULT '[]',
  triggered_by_run_id  UUID REFERENCES discovery_runs(id) ON DELETE SET NULL,
  status               merge_candidate_status DEFAULT 'pending',
  resolved_by          UUID REFERENCES auth.users(id),
  resolved_at          TIMESTAMPTZ,
  created_at           TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE (workspace_id, creator_a_id, creator_b_id),
  CHECK (creator_a_id < creator_b_id)
);


-- ============================================================
-- STEP 7: `funnel_edges`
-- Directed edges representing traffic flow between a creator's accounts.
-- e.g. IG → Linktree → OnlyFans
-- ============================================================

CREATE TABLE IF NOT EXISTS funnel_edges (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  creator_id      UUID REFERENCES creators(id) ON DELETE CASCADE NOT NULL,
  workspace_id    UUID REFERENCES workspaces(id) ON DELETE CASCADE NOT NULL,
  from_profile_id UUID REFERENCES profiles(id) ON DELETE CASCADE NOT NULL,
  to_profile_id   UUID REFERENCES profiles(id) ON DELETE CASCADE NOT NULL,
  edge_type       TEXT DEFAULT 'inferred'
                  CHECK (edge_type IN ('link_in_bio','direct_link','cta_mention','qr_code','inferred')),
  confidence      NUMERIC(3,2) DEFAULT 1.0,
  detected_at     TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE (from_profile_id, to_profile_id),
  CHECK (from_profile_id <> to_profile_id)
);


-- ============================================================
-- STEP 8: `content_labels` + `content_label_assignments`
-- Dynamic taxonomy for long-tail content type vocabulary.
-- AI creates labels as needed; team canonicalizes via Classification UI.
-- ============================================================

CREATE TABLE IF NOT EXISTS content_labels (
  id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  workspace_id   UUID REFERENCES workspaces(id) ON DELETE CASCADE NOT NULL,
  label_type     label_type NOT NULL,
  name           TEXT NOT NULL,
  slug           TEXT NOT NULL,
  description    TEXT,
  usage_count    INT DEFAULT 0,
  is_canonical   BOOLEAN DEFAULT false,
  merged_into_id UUID REFERENCES content_labels(id) ON DELETE SET NULL,
  created_by     UUID REFERENCES auth.users(id),  -- NULL = AI-created
  created_at     TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE (workspace_id, label_type, slug)
);

CREATE TABLE IF NOT EXISTS content_label_assignments (
  content_id     UUID REFERENCES scraped_content(id) ON DELETE CASCADE NOT NULL,
  label_id       UUID REFERENCES content_labels(id)  ON DELETE CASCADE NOT NULL,
  assigned_by_ai BOOLEAN DEFAULT true,
  confidence     NUMERIC(3,2),
  PRIMARY KEY (content_id, label_id)
);


-- ============================================================
-- STEP 9: `creator_brand_analyses` — Phase 3, schema ready now
-- ============================================================

CREATE TABLE IF NOT EXISTS creator_brand_analyses (
  id                   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  creator_id           UUID REFERENCES creators(id) ON DELETE CASCADE NOT NULL,
  workspace_id         UUID REFERENCES workspaces(id) ON DELETE CASCADE NOT NULL,
  version              INT NOT NULL DEFAULT 1,
  niche_summary        TEXT,
  usp                  TEXT,
  brand_keywords       TEXT[] DEFAULT '{}',
  seo_keywords         TEXT[] DEFAULT '{}',
  funnel_map           JSONB DEFAULT '{}',
  monetization_summary TEXT,
  platforms_included   platform[] DEFAULT '{}',
  gemini_raw_response  JSONB DEFAULT '{}',
  analyzed_at          TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE (creator_id, version)
);


-- ============================================================
-- STEP 10: Helper functions & triggers
-- ============================================================

-- Auto-update updated_at timestamps
CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
  NEW.updated_at = NOW();
  RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_creators_updated_at ON creators;
CREATE TRIGGER trg_creators_updated_at
  BEFORE UPDATE ON creators
  FOR EACH ROW EXECUTE FUNCTION set_updated_at();

DROP TRIGGER IF EXISTS trg_profiles_updated_at ON profiles;
CREATE TRIGGER trg_profiles_updated_at
  BEFORE UPDATE ON profiles
  FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- Increment content_labels.usage_count when a label is assigned
CREATE OR REPLACE FUNCTION increment_label_usage()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
  UPDATE content_labels SET usage_count = usage_count + 1 WHERE id = NEW.label_id;
  RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_increment_label_usage ON content_label_assignments;
CREATE TRIGGER trg_increment_label_usage
  AFTER INSERT ON content_label_assignments
  FOR EACH ROW EXECUTE FUNCTION increment_label_usage();

-- Handle normalization for similarity matching (Python also does this via rapidfuzz)
-- Used in merge candidate evaluation queries.
CREATE OR REPLACE FUNCTION normalize_handle(h TEXT)
RETURNS TEXT LANGUAGE sql IMMUTABLE AS $$
  SELECT lower(regexp_replace(COALESCE(h, ''), '[@.\-_\s]', '', 'g'));
$$;


-- ============================================================
-- STEP 11: Core RPCs — called by the Python discovery pipeline
-- ============================================================

-- commit_discovery_result
-- Transactional: enriches creator + upserts all discovered profiles
-- + inserts funnel edges + runs collision detection → merge candidates.
-- Called by discover_creator.py on successful Gemini response.
CREATE OR REPLACE FUNCTION commit_discovery_result(
  p_run_id       UUID,
  p_creator_data JSONB,
  -- {canonical_name, known_usernames[], display_name_variants[],
  --  primary_platform, primary_niche, monetization_model}
  p_accounts     JSONB,
  -- [{account_type, platform, handle, url, display_name, bio,
  --   follower_count, is_primary, discovery_confidence}]
  p_funnel_edges JSONB
  -- [{from_handle, from_platform, to_handle, to_platform, edge_type, confidence}]
)
RETURNS JSONB  -- {creator_id, accounts_upserted, merge_candidates_raised}
LANGUAGE plpgsql AS $$
DECLARE
  v_creator_id        UUID;
  v_workspace_id      UUID;
  v_account           JSONB;
  v_edge              JSONB;
  v_from_id           UUID;
  v_to_id             UUID;
  v_existing_creator  UUID;
  v_accounts_upserted INT := 0;
  v_merges_raised     INT := 0;
BEGIN
  SELECT creator_id, workspace_id
  INTO   v_creator_id, v_workspace_id
  FROM   discovery_runs
  WHERE  id = p_run_id;

  IF v_creator_id IS NULL THEN
    RAISE EXCEPTION 'discovery_run % not found or already processed', p_run_id;
  END IF;

  -- 1. Enrich creator
  UPDATE creators SET
    canonical_name = COALESCE(
      NULLIF(p_creator_data->>'canonical_name', ''),
      canonical_name
    ),
    known_usernames = (
      SELECT ARRAY_AGG(DISTINCT u)
      FROM UNNEST(
        known_usernames ||
        ARRAY(SELECT JSONB_ARRAY_ELEMENTS_TEXT(p_creator_data->'known_usernames'))
      ) AS u
      WHERE u IS NOT NULL AND u <> ''
    ),
    display_name_variants = (
      SELECT ARRAY_AGG(DISTINCT v)
      FROM UNNEST(
        display_name_variants ||
        ARRAY(SELECT JSONB_ARRAY_ELEMENTS_TEXT(p_creator_data->'display_name_variants'))
      ) AS v
      WHERE v IS NOT NULL AND v <> ''
    ),
    primary_platform   = COALESCE(
      (p_creator_data->>'primary_platform')::platform,
      primary_platform
    ),
    primary_niche      = COALESCE(p_creator_data->>'primary_niche', primary_niche),
    monetization_model = COALESCE(
      (p_creator_data->>'monetization_model')::monetization_model,
      monetization_model
    ),
    onboarding_status     = 'ready',
    last_discovery_run_id = p_run_id,
    updated_at            = NOW()
  WHERE id = v_creator_id;

  -- 2. Upsert each discovered account.
  --    Before inserting: check if handle exists under a DIFFERENT creator (collision → merge candidate).
  FOR v_account IN SELECT * FROM JSONB_ARRAY_ELEMENTS(p_accounts) LOOP
    CONTINUE WHEN v_account->>'handle' IS NULL AND v_account->>'url' IS NULL;

    -- Collision check: same handle + platform, different creator
    IF v_account->>'handle' IS NOT NULL THEN
      SELECT p.creator_id INTO v_existing_creator
      FROM   profiles p
      WHERE  p.workspace_id  = v_workspace_id
        AND  p.platform      = (v_account->>'platform')::platform
        AND  p.handle        = v_account->>'handle'
        AND  p.creator_id    IS NOT NULL
        AND  p.creator_id   <> v_creator_id
      LIMIT 1;

      IF v_existing_creator IS NOT NULL THEN
        INSERT INTO creator_merge_candidates (
          workspace_id,
          creator_a_id,
          creator_b_id,
          confidence,
          evidence,
          triggered_by_run_id
        ) VALUES (
          v_workspace_id,
          LEAST(v_existing_creator, v_creator_id),
          GREATEST(v_existing_creator, v_creator_id),
          COALESCE((v_account->>'discovery_confidence')::NUMERIC, 0.85),
          JSONB_BUILD_ARRAY(JSONB_BUILD_OBJECT(
            'signal',     'handle_collision',
            'platform',   v_account->>'platform',
            'handle',     v_account->>'handle',
            'confidence', COALESCE((v_account->>'discovery_confidence')::NUMERIC, 0.85)
          )),
          p_run_id
        )
        ON CONFLICT (workspace_id, creator_a_id, creator_b_id) DO NOTHING;

        v_merges_raised := v_merges_raised + 1;
        CONTINUE;  -- Do not insert this account under current creator
      END IF;
    END IF;

    -- Safe to upsert
    INSERT INTO profiles (
      workspace_id, creator_id,
      platform, handle, url,
      display_name, bio,
      follower_count, account_type,
      is_primary, discovery_confidence,
      is_active
    ) VALUES (
      v_workspace_id,
      v_creator_id,
      (v_account->>'platform')::platform,
      v_account->>'handle',
      v_account->>'url',
      v_account->>'display_name',
      v_account->>'bio',
      COALESCE((v_account->>'follower_count')::BIGINT, 0),
      COALESCE((v_account->>'account_type')::account_type, 'social'),
      COALESCE((v_account->>'is_primary')::BOOLEAN, false),
      COALESCE((v_account->>'discovery_confidence')::NUMERIC, 1.0),
      true
    )
    ON CONFLICT (workspace_id, platform, handle) WHERE handle IS NOT NULL
    DO UPDATE SET
      creator_id           = EXCLUDED.creator_id,
      url                  = COALESCE(EXCLUDED.url, profiles.url),
      display_name         = COALESCE(EXCLUDED.display_name, profiles.display_name),
      bio                  = COALESCE(EXCLUDED.bio, profiles.bio),
      follower_count       = CASE
                               WHEN EXCLUDED.follower_count > 0 THEN EXCLUDED.follower_count
                               ELSE profiles.follower_count
                             END,
      account_type         = EXCLUDED.account_type,
      is_primary           = EXCLUDED.is_primary,
      discovery_confidence = EXCLUDED.discovery_confidence,
      updated_at           = NOW();

    v_accounts_upserted := v_accounts_upserted + 1;
  END LOOP;

  -- 3. Insert funnel edges (resolve handles → profile IDs)
  FOR v_edge IN SELECT * FROM JSONB_ARRAY_ELEMENTS(p_funnel_edges) LOOP
    SELECT id INTO v_from_id FROM profiles
    WHERE  workspace_id = v_workspace_id
      AND  platform     = (v_edge->>'from_platform')::platform
      AND  handle       = v_edge->>'from_handle'
    LIMIT 1;

    SELECT id INTO v_to_id FROM profiles
    WHERE  workspace_id = v_workspace_id
      AND  platform     = (v_edge->>'to_platform')::platform
      AND  handle       = v_edge->>'to_handle'
    LIMIT 1;

    IF v_from_id IS NOT NULL AND v_to_id IS NOT NULL AND v_from_id <> v_to_id THEN
      INSERT INTO funnel_edges (
        creator_id, workspace_id,
        from_profile_id, to_profile_id,
        edge_type, confidence
      ) VALUES (
        v_creator_id, v_workspace_id,
        v_from_id, v_to_id,
        COALESCE(v_edge->>'edge_type', 'inferred'),
        COALESCE((v_edge->>'confidence')::NUMERIC, 0.8)
      )
      ON CONFLICT (from_profile_id, to_profile_id) DO NOTHING;
    END IF;
  END LOOP;

  -- 4. Mark run completed
  UPDATE discovery_runs SET
    status                        = 'completed',
    assets_discovered_count       = v_accounts_upserted,
    merge_candidates_raised       = v_merges_raised,
    completed_at                  = NOW()
  WHERE id = p_run_id;

  RETURN JSONB_BUILD_OBJECT(
    'creator_id',              v_creator_id,
    'accounts_upserted',       v_accounts_upserted,
    'merge_candidates_raised', v_merges_raised
  );
END;
$$;


-- mark_discovery_failed — called by pipeline on exception
CREATE OR REPLACE FUNCTION mark_discovery_failed(
  p_run_id UUID,
  p_error  TEXT
)
RETURNS VOID LANGUAGE plpgsql AS $$
DECLARE
  v_creator_id UUID;
BEGIN
  SELECT creator_id INTO v_creator_id FROM discovery_runs WHERE id = p_run_id;
  UPDATE discovery_runs SET
    status        = 'failed',
    error_message = p_error,
    completed_at  = NOW()
  WHERE id = p_run_id;
  UPDATE creators SET
    onboarding_status    = 'failed',
    last_discovery_error = p_error,
    updated_at           = NOW()
  WHERE id = v_creator_id;
END;
$$;


-- retry_creator_discovery — called from UI Retry button
CREATE OR REPLACE FUNCTION retry_creator_discovery(
  p_creator_id UUID,
  p_user_id    UUID
)
RETURNS UUID LANGUAGE plpgsql AS $$
DECLARE
  v_run_id   UUID;
  v_ws_id    UUID;
  v_attempts INT;
BEGIN
  SELECT workspace_id INTO v_ws_id FROM creators WHERE id = p_creator_id;
  SELECT COALESCE(MAX(attempt_number), 0) INTO v_attempts
  FROM discovery_runs WHERE creator_id = p_creator_id;

  INSERT INTO discovery_runs (workspace_id, creator_id, initiated_by, status, attempt_number)
  VALUES (v_ws_id, p_creator_id, p_user_id, 'pending', v_attempts + 1)
  RETURNING id INTO v_run_id;

  UPDATE creators SET
    onboarding_status    = 'processing',
    last_discovery_error = NULL,
    updated_at           = NOW()
  WHERE id = p_creator_id;

  RETURN v_run_id;
END;
$$;


-- merge_creators — keep creator A, migrate everything from B, archive B
-- Called from the UI merge review panel.
CREATE OR REPLACE FUNCTION merge_creators(
  p_keep_id      UUID,
  p_merge_id     UUID,
  p_resolver_id  UUID,
  p_candidate_id UUID
)
RETURNS VOID LANGUAGE plpgsql AS $$
BEGIN
  -- Migrate all profiles (creator_accounts)
  UPDATE profiles          SET creator_id = p_keep_id WHERE creator_id = p_merge_id;
  -- Migrate funnel edges
  UPDATE funnel_edges      SET creator_id = p_keep_id WHERE creator_id = p_merge_id;
  -- Migrate brand analyses
  UPDATE creator_brand_analyses SET creator_id = p_keep_id WHERE creator_id = p_merge_id;

  -- Merge known_usernames + display_name_variants into the kept creator
  UPDATE creators SET
    known_usernames = (
      SELECT ARRAY_AGG(DISTINCT u)
      FROM UNNEST(
        (SELECT known_usernames FROM creators WHERE id = p_keep_id) ||
        (SELECT known_usernames FROM creators WHERE id = p_merge_id)
      ) AS u WHERE u IS NOT NULL
    ),
    display_name_variants = (
      SELECT ARRAY_AGG(DISTINCT v)
      FROM UNNEST(
        (SELECT display_name_variants FROM creators WHERE id = p_keep_id) ||
        (SELECT display_name_variants FROM creators WHERE id = p_merge_id)
      ) AS v WHERE v IS NOT NULL
    ),
    updated_at = NOW()
  WHERE id = p_keep_id;

  -- Soft-delete merged creator
  UPDATE creators SET
    onboarding_status = 'archived',
    updated_at        = NOW()
  WHERE id = p_merge_id;

  -- Resolve the merge candidate
  UPDATE creator_merge_candidates SET
    status      = 'merged',
    resolved_by = p_resolver_id,
    resolved_at = NOW()
  WHERE id = p_candidate_id;
END;
$$;


-- ============================================================
-- STEP 12: RLS for new tables
-- ============================================================

ALTER TABLE creators                  ENABLE ROW LEVEL SECURITY;
ALTER TABLE discovery_runs            ENABLE ROW LEVEL SECURITY;
ALTER TABLE creator_merge_candidates  ENABLE ROW LEVEL SECURITY;
ALTER TABLE funnel_edges              ENABLE ROW LEVEL SECURITY;
ALTER TABLE content_labels            ENABLE ROW LEVEL SECURITY;
ALTER TABLE content_label_assignments ENABLE ROW LEVEL SECURITY;
ALTER TABLE creator_brand_analyses    ENABLE ROW LEVEL SECURITY;

-- creators
CREATE POLICY "members select creators"
  ON creators FOR SELECT USING (public.is_workspace_member(workspace_id));
CREATE POLICY "members insert creators"
  ON creators FOR INSERT WITH CHECK (public.is_workspace_member(workspace_id));
CREATE POLICY "members update creators"
  ON creators FOR UPDATE USING (public.is_workspace_member(workspace_id));

-- discovery_runs
CREATE POLICY "members select discovery_runs"
  ON discovery_runs FOR SELECT USING (public.is_workspace_member(workspace_id));
CREATE POLICY "members insert discovery_runs"
  ON discovery_runs FOR INSERT WITH CHECK (public.is_workspace_member(workspace_id));
CREATE POLICY "members update discovery_runs"
  ON discovery_runs FOR UPDATE USING (public.is_workspace_member(workspace_id));

-- creator_merge_candidates
CREATE POLICY "members select merge_candidates"
  ON creator_merge_candidates FOR SELECT USING (public.is_workspace_member(workspace_id));
CREATE POLICY "members insert merge_candidates"
  ON creator_merge_candidates FOR INSERT WITH CHECK (public.is_workspace_member(workspace_id));
CREATE POLICY "members update merge_candidates"
  ON creator_merge_candidates FOR UPDATE USING (public.is_workspace_member(workspace_id));

-- funnel_edges
CREATE POLICY "members select funnel_edges"
  ON funnel_edges FOR SELECT USING (public.is_workspace_member(workspace_id));
CREATE POLICY "members insert funnel_edges"
  ON funnel_edges FOR INSERT WITH CHECK (public.is_workspace_member(workspace_id));

-- content_labels
CREATE POLICY "members select content_labels"
  ON content_labels FOR SELECT USING (public.is_workspace_member(workspace_id));
CREATE POLICY "members insert content_labels"
  ON content_labels FOR INSERT WITH CHECK (public.is_workspace_member(workspace_id));
CREATE POLICY "members update content_labels"
  ON content_labels FOR UPDATE USING (public.is_workspace_member(workspace_id));

-- content_label_assignments (workspace via label join)
CREATE POLICY "members select label_assignments"
  ON content_label_assignments FOR SELECT USING (
    EXISTS (
      SELECT 1 FROM content_labels cl
      WHERE  cl.id = content_label_assignments.label_id
        AND  public.is_workspace_member(cl.workspace_id)
    )
  );
CREATE POLICY "members insert label_assignments"
  ON content_label_assignments FOR INSERT WITH CHECK (
    EXISTS (
      SELECT 1 FROM content_labels cl
      WHERE  cl.id = label_id
        AND  public.is_workspace_member(cl.workspace_id)
    )
  );

-- creator_brand_analyses
CREATE POLICY "members select brand_analyses"
  ON creator_brand_analyses FOR SELECT USING (public.is_workspace_member(workspace_id));
CREATE POLICY "members insert brand_analyses"
  ON creator_brand_analyses FOR INSERT WITH CHECK (public.is_workspace_member(workspace_id));


-- ============================================================
-- STEP 13: Indexes for new tables + new columns on profiles
-- ============================================================

-- creators
CREATE INDEX IF NOT EXISTS idx_creators_workspace_status
  ON creators(workspace_id, onboarding_status);
CREATE INDEX IF NOT EXISTS idx_creators_workspace_tracking
  ON creators(workspace_id, tracking_type);
CREATE INDEX IF NOT EXISTS idx_creators_workspace_platform
  ON creators(workspace_id, primary_platform);
CREATE INDEX IF NOT EXISTS idx_creators_known_usernames
  ON creators USING GIN(known_usernames);
CREATE INDEX IF NOT EXISTS idx_creators_tags
  ON creators USING GIN(tags);

-- profiles (new columns)
CREATE INDEX IF NOT EXISTS idx_profiles_creator_id
  ON profiles(creator_id);
CREATE INDEX IF NOT EXISTS idx_profiles_account_type
  ON profiles(workspace_id, account_type);

-- discovery_runs
CREATE INDEX IF NOT EXISTS idx_discovery_runs_creator
  ON discovery_runs(creator_id);
CREATE INDEX IF NOT EXISTS idx_discovery_runs_workspace_status
  ON discovery_runs(workspace_id, status);

-- merge candidates
CREATE INDEX IF NOT EXISTS idx_merge_candidates_workspace_status
  ON creator_merge_candidates(workspace_id, status);
CREATE INDEX IF NOT EXISTS idx_merge_candidates_creator_a
  ON creator_merge_candidates(creator_a_id);
CREATE INDEX IF NOT EXISTS idx_merge_candidates_creator_b
  ON creator_merge_candidates(creator_b_id);

-- funnel edges
CREATE INDEX IF NOT EXISTS idx_funnel_edges_creator
  ON funnel_edges(creator_id);

-- content labels
CREATE INDEX IF NOT EXISTS idx_content_labels_workspace_type
  ON content_labels(workspace_id, label_type);
CREATE INDEX IF NOT EXISTS idx_label_assignments_content
  ON content_label_assignments(content_id);
CREATE INDEX IF NOT EXISTS idx_label_assignments_label
  ON content_label_assignments(label_id);

-- brand analyses
CREATE INDEX IF NOT EXISTS idx_brand_analyses_creator
  ON creator_brand_analyses(creator_id);


-- ============================================================
-- STEP 14: Enable Realtime for live card state transitions
-- creators:     card flips processing → ready / failed
-- discovery_runs: progress tracking
-- creator_merge_candidates: amber banner count updates
-- ============================================================

ALTER PUBLICATION supabase_realtime ADD TABLE creators;
ALTER PUBLICATION supabase_realtime ADD TABLE discovery_runs;
ALTER PUBLICATION supabase_realtime ADD TABLE creator_merge_candidates;


-- ============================================================
-- DONE.
-- What was added:
--   Enums:  account_type, onboarding_status, monetization_model,
--           discovery_run_status, merge_candidate_status, label_type
--   Tables: creators, discovery_runs, creator_merge_candidates,
--           funnel_edges, content_labels, content_label_assignments,
--           creator_brand_analyses
--   Columns added to profiles: creator_id, account_type, url,
--           discovery_confidence, updated_at
--   Functions: set_updated_at, increment_label_usage, normalize_handle,
--              commit_discovery_result, mark_discovery_failed,
--              retry_creator_discovery, merge_creators
--   Triggers: trg_creators_updated_at, trg_profiles_updated_at,
--             trg_increment_label_usage
--   Realtime: creators, discovery_runs, creator_merge_candidates
-- ============================================================
