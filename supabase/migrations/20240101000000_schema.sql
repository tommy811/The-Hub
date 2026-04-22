-- Enums
CREATE TYPE platform AS ENUM ('instagram', 'tiktok', 'youtube', 'patreon', 'twitter', 'linkedin');
CREATE TYPE tracking_type AS ENUM ('managed', 'inspiration', 'competitor', 'candidate', 'hybrid_ai', 'coach', 'unreviewed');
CREATE TYPE rank_tier AS ENUM ('diamond', 'platinum', 'gold', 'silver', 'bronze', 'plastic');
CREATE TYPE post_type AS ENUM ('reel', 'tiktok_video', 'image', 'carousel', 'story');
-- content_archetype enum removed per user request (will use TEXT instead)
CREATE TYPE content_vibe AS ENUM (
    'playful', 'girl_next_door', 'body_worship', 'wifey', 'luxury', 'edgy', 
    'wholesome', 'mysterious', 'confident', 'aspirational'
);
CREATE TYPE content_category AS ENUM (
    'comedy_entertainment', 'fashion_style', 'fitness', 'lifestyle', 'beauty', 
    'travel', 'food', 'music', 'gaming', 'education', 'other'
);
CREATE TYPE workspace_role AS ENUM ('owner', 'admin', 'member');
CREATE TYPE signal_type AS ENUM ('velocity_spike', 'outlier_post', 'emerging_archetype', 'hook_pattern', 'cadence_change');

-- Tables
CREATE TABLE workspaces (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,
    slug TEXT UNIQUE NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    owner_id UUID REFERENCES auth.users(id) NOT NULL
);

CREATE TABLE workspace_members (
    workspace_id UUID REFERENCES workspaces(id) ON DELETE CASCADE,
    user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE,
    role workspace_role NOT NULL DEFAULT 'member',
    joined_at TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (workspace_id, user_id)
);

CREATE TABLE profiles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id UUID REFERENCES workspaces(id) ON DELETE CASCADE,
    platform platform NOT NULL,
    handle TEXT NOT NULL,
    display_name TEXT,
    profile_url TEXT,
    avatar_url TEXT,
    bio TEXT,
    follower_count BIGINT DEFAULT 0,
    following_count BIGINT DEFAULT 0,
    post_count BIGINT DEFAULT 0,
    tracking_type tracking_type DEFAULT 'unreviewed',
    tags TEXT[] DEFAULT '{}',
    is_clean BOOLEAN DEFAULT true,
    analysis_version TEXT DEFAULT 'v1',
    last_scraped_at TIMESTAMPTZ,
    added_by UUID REFERENCES auth.users(id),
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (workspace_id, platform, handle)
);

CREATE TABLE scraped_content (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    profile_id UUID REFERENCES profiles(id) ON DELETE CASCADE,
    platform platform NOT NULL,
    platform_post_id TEXT NOT NULL,
    post_url TEXT,
    post_type post_type NOT NULL,
    caption TEXT,
    hook_text TEXT,
    posted_at TIMESTAMPTZ,
    view_count BIGINT DEFAULT 0,
    like_count BIGINT DEFAULT 0,
    comment_count BIGINT DEFAULT 0,
    share_count BIGINT DEFAULT 0,
    save_count BIGINT DEFAULT 0,
    engagement_rate NUMERIC GENERATED ALWAYS AS (
        CASE WHEN view_count > 0 THEN 
            ((like_count + comment_count + share_count + save_count)::numeric / view_count::numeric) * 100 
        ELSE 0 END
    ) STORED,
    platform_metrics JSONB DEFAULT '{}'::jsonb,
    media_urls TEXT[] DEFAULT '{}',
    thumbnail_url TEXT,
    is_outlier BOOLEAN DEFAULT false,
    raw_apify_payload JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (platform, platform_post_id)
);

CREATE TABLE content_metrics_snapshots (
    content_id UUID REFERENCES scraped_content(id) ON DELETE CASCADE,
    snapshot_date DATE NOT NULL DEFAULT CURRENT_DATE,
    view_count BIGINT DEFAULT 0,
    like_count BIGINT DEFAULT 0,
    comment_count BIGINT DEFAULT 0,
    share_count BIGINT DEFAULT 0,
    save_count BIGINT DEFAULT 0,
    velocity numeric DEFAULT 0,
    PRIMARY KEY (content_id, snapshot_date)
);

CREATE TABLE profile_metrics_snapshots (
    profile_id UUID REFERENCES profiles(id) ON DELETE CASCADE,
    snapshot_date DATE NOT NULL DEFAULT CURRENT_DATE,
    follower_count BIGINT DEFAULT 0,
    median_views NUMERIC DEFAULT 0,
    avg_engagement_rate NUMERIC DEFAULT 0,
    outlier_count INT DEFAULT 0,
    quality_score NUMERIC DEFAULT 0,
    PRIMARY KEY (profile_id, snapshot_date)
);

CREATE TABLE content_analysis (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    content_id UUID REFERENCES scraped_content(id) ON DELETE CASCADE UNIQUE,
    quality_score NUMERIC(3,1),
    archetype TEXT,
    vibe content_vibe,
    category content_category,
    visual_tags TEXT[] DEFAULT '{}',
    transcription TEXT,
    hook_analysis TEXT,
    is_clean BOOLEAN DEFAULT true,
    analysis_version TEXT,
    gemini_raw_response JSONB DEFAULT '{}'::jsonb,
    model_version TEXT,
    analyzed_at TIMESTAMPTZ DEFAULT NOW()
);

-- Defined before profile_scores so we can use it in GENERATED ALWAYS AS
CREATE OR REPLACE FUNCTION calculate_rank(score numeric) 
RETURNS rank_tier AS $$
BEGIN
    IF score >= 85 THEN RETURN 'diamond'::rank_tier;
    ELSIF score >= 70 THEN RETURN 'platinum'::rank_tier;
    ELSIF score >= 55 THEN RETURN 'gold'::rank_tier;
    ELSIF score >= 40 THEN RETURN 'silver'::rank_tier;
    ELSIF score >= 25 THEN RETURN 'bronze'::rank_tier;
    ELSE RETURN 'plastic'::rank_tier;
    END IF;
END;
$$ LANGUAGE plpgsql IMMUTABLE;

CREATE TABLE profile_scores (
    profile_id UUID REFERENCES profiles(id) ON DELETE CASCADE UNIQUE,
    current_score NUMERIC(3,1) DEFAULT 0,
    current_rank rank_tier GENERATED ALWAYS AS (calculate_rank(current_score)) STORED,
    scored_content_count INT DEFAULT 0,
    last_computed_at TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (profile_id)
);

CREATE TABLE trend_signals (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id UUID REFERENCES workspaces(id) ON DELETE CASCADE,
    signal_type signal_type NOT NULL,
    profile_id UUID REFERENCES profiles(id) ON DELETE CASCADE,
    content_id UUID REFERENCES scraped_content(id) ON DELETE CASCADE,
    score NUMERIC(5,2),
    detected_at TIMESTAMPTZ DEFAULT NOW(),
    metadata JSONB DEFAULT '{}'::jsonb,
    is_dismissed BOOLEAN DEFAULT false
);

CREATE TABLE alerts_config (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id UUID REFERENCES workspaces(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    rule_type TEXT NOT NULL,
    threshold_json JSONB DEFAULT '{}'::jsonb,
    target_profile_ids UUID[] DEFAULT '{}',
    is_enabled BOOLEAN DEFAULT true,
    notify_emails TEXT[] DEFAULT '{}',
    created_by UUID REFERENCES auth.users(id)
);

CREATE TABLE alerts_feed (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id UUID REFERENCES workspaces(id) ON DELETE CASCADE,
    config_id UUID REFERENCES alerts_config(id) ON DELETE CASCADE,
    content_id UUID REFERENCES scraped_content(id) ON DELETE CASCADE,
    profile_id UUID REFERENCES profiles(id) ON DELETE CASCADE,
    triggered_at TIMESTAMPTZ DEFAULT NOW(),
    is_read BOOLEAN DEFAULT false,
    payload JSONB DEFAULT '{}'::jsonb
);

-- Functions
CREATE OR REPLACE FUNCTION flag_outliers(p_profile_id uuid) RETURNS void AS $$
DECLARE
    v_median_views NUMERIC;
BEGIN
    -- Get median views for the profile
    SELECT PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY view_count)
    INTO v_median_views
    FROM scraped_content
    WHERE profile_id = p_profile_id;

    -- Update strictly where view_count > 2x median
    IF v_median_views > 0 THEN
        UPDATE scraped_content
        SET is_outlier = true
        WHERE profile_id = p_profile_id AND view_count > (v_median_views * 2);
    END IF;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

CREATE OR REPLACE FUNCTION refresh_profile_score(p_profile_id uuid) RETURNS void AS $$
DECLARE
    v_avg_score NUMERIC;
    v_scored_count INT;
BEGIN
    SELECT COALESCE(AVG(quality_score), 0), COUNT(*)
    INTO v_avg_score, v_scored_count
    FROM content_analysis ca
    JOIN scraped_content sc ON ca.content_id = sc.id
    WHERE sc.profile_id = p_profile_id;

    INSERT INTO profile_scores (profile_id, current_score, scored_content_count, last_computed_at)
    VALUES (p_profile_id, v_avg_score, v_scored_count, NOW())
    ON CONFLICT (profile_id) DO UPDATE SET
        current_score = EXCLUDED.current_score,
        scored_content_count = EXCLUDED.scored_content_count,
        last_computed_at = EXCLUDED.last_computed_at;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- RLS Enable
ALTER TABLE workspaces ENABLE ROW LEVEL SECURITY;
ALTER TABLE workspace_members ENABLE ROW LEVEL SECURITY;
ALTER TABLE profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE scraped_content ENABLE ROW LEVEL SECURITY;
ALTER TABLE content_metrics_snapshots ENABLE ROW LEVEL SECURITY;
ALTER TABLE profile_metrics_snapshots ENABLE ROW LEVEL SECURITY;
ALTER TABLE content_analysis ENABLE ROW LEVEL SECURITY;
ALTER TABLE profile_scores ENABLE ROW LEVEL SECURITY;
ALTER TABLE trend_signals ENABLE ROW LEVEL SECURITY;
ALTER TABLE alerts_config ENABLE ROW LEVEL SECURITY;
ALTER TABLE alerts_feed ENABLE ROW LEVEL SECURITY;

-- Helper to check workspace membership
CREATE OR REPLACE FUNCTION public.is_workspace_member(ws_id UUID)
RETURNS BOOLEAN AS $$
  SELECT EXISTS (
    SELECT 1 FROM public.workspace_members
    WHERE workspace_id = ws_id AND user_id = auth.uid()
  );
$$ LANGUAGE sql SECURITY DEFINER;

-- RLS Policies
CREATE POLICY "Users view workspaces they belong to" ON workspaces FOR SELECT USING (public.is_workspace_member(id));
CREATE POLICY "Users view workspace members" ON workspace_members FOR SELECT USING (public.is_workspace_member(workspace_id));
CREATE POLICY "Users view profiles in their workspace" ON profiles FOR SELECT USING (public.is_workspace_member(workspace_id));
-- Allow Insert / Update for users to manage profiles
CREATE POLICY "Users insert profiles to their workspace" ON profiles FOR INSERT WITH CHECK (public.is_workspace_member(workspace_id));
CREATE POLICY "Users update profiles in their workspace" ON profiles FOR UPDATE USING (public.is_workspace_member(workspace_id));

CREATE POLICY "Users view content from profiles in their workspace" ON scraped_content FOR SELECT USING (
  EXISTS (SELECT 1 FROM profiles WHERE profiles.id = scraped_content.profile_id AND public.is_workspace_member(profiles.workspace_id))
);
CREATE POLICY "Users view content metrics" ON content_metrics_snapshots FOR SELECT USING (
  EXISTS (SELECT 1 FROM scraped_content JOIN profiles ON profiles.id = scraped_content.profile_id WHERE scraped_content.id = content_metrics_snapshots.content_id AND public.is_workspace_member(profiles.workspace_id))
);
CREATE POLICY "Users view profile metrics" ON profile_metrics_snapshots FOR SELECT USING (
  EXISTS (SELECT 1 FROM profiles WHERE profiles.id = profile_metrics_snapshots.profile_id AND public.is_workspace_member(profiles.workspace_id))
);
CREATE POLICY "Users view content analysis" ON content_analysis FOR SELECT USING (
  EXISTS (SELECT 1 FROM scraped_content JOIN profiles ON profiles.id = scraped_content.profile_id WHERE scraped_content.id = content_analysis.content_id AND public.is_workspace_member(profiles.workspace_id))
);
CREATE POLICY "Users view profile scores" ON profile_scores FOR SELECT USING (
  EXISTS (SELECT 1 FROM profiles WHERE profiles.id = profile_scores.profile_id AND public.is_workspace_member(profiles.workspace_id))
);

CREATE POLICY "Users view trend signals" ON trend_signals FOR SELECT USING (public.is_workspace_member(workspace_id));
CREATE POLICY "Users view alerts config" ON alerts_config FOR SELECT USING (public.is_workspace_member(workspace_id));
CREATE POLICY "Users view alerts feed" ON alerts_feed FOR SELECT USING (public.is_workspace_member(workspace_id));

-- Indexes
CREATE INDEX idx_workspace_members_user ON workspace_members(user_id);
CREATE INDEX idx_profiles_workspace_platform_tracking ON profiles(workspace_id, platform, tracking_type);
CREATE INDEX idx_scraped_content_profile_posted_desc ON scraped_content(profile_id, posted_at DESC);
CREATE INDEX idx_snapshots_content_date ON content_metrics_snapshots(content_id, snapshot_date);
CREATE INDEX idx_snapshots_profile_date ON profile_metrics_snapshots(profile_id, snapshot_date);
CREATE INDEX idx_scraped_content_outliers ON scraped_content(profile_id) WHERE is_outlier = true;
CREATE INDEX idx_trend_signals_workspace ON trend_signals(workspace_id);

-- SEED BLOCK
/*
INSERT INTO workspaces (id, name, slug, owner_id) VALUES ('00000000-0000-0000-0000-000000000001', 'Acme Agency', 'acme-agency', 'YOUR_AUTH_UID_HERE');
INSERT INTO workspace_members (workspace_id, user_id, role) VALUES ('00000000-0000-0000-0000-000000000001', 'YOUR_AUTH_UID_HERE', 'owner');
*/
