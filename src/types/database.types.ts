export type Json =
  | string
  | number
  | boolean
  | null
  | { [key: string]: Json | undefined }
  | Json[]

export type Database = {
  // Allows to automatically instantiate createClient with right options
  // instead of createClient<Database, { PostgrestVersion: 'XX' }>(URL, KEY)
  __InternalSupabase: {
    PostgrestVersion: "14.5"
  }
  public: {
    Tables: {
      alerts_config: {
        Row: {
          created_by: string | null
          id: string
          is_enabled: boolean | null
          name: string
          notify_emails: string[] | null
          rule_type: string
          target_profile_ids: string[] | null
          threshold_json: Json | null
          workspace_id: string | null
        }
        Insert: {
          created_by?: string | null
          id?: string
          is_enabled?: boolean | null
          name: string
          notify_emails?: string[] | null
          rule_type: string
          target_profile_ids?: string[] | null
          threshold_json?: Json | null
          workspace_id?: string | null
        }
        Update: {
          created_by?: string | null
          id?: string
          is_enabled?: boolean | null
          name?: string
          notify_emails?: string[] | null
          rule_type?: string
          target_profile_ids?: string[] | null
          threshold_json?: Json | null
          workspace_id?: string | null
        }
        Relationships: [
          {
            foreignKeyName: "alerts_config_workspace_id_fkey"
            columns: ["workspace_id"]
            isOneToOne: false
            referencedRelation: "workspaces"
            referencedColumns: ["id"]
          },
        ]
      }
      alerts_feed: {
        Row: {
          config_id: string | null
          content_id: string | null
          id: string
          is_read: boolean | null
          payload: Json | null
          profile_id: string | null
          triggered_at: string | null
          workspace_id: string | null
        }
        Insert: {
          config_id?: string | null
          content_id?: string | null
          id?: string
          is_read?: boolean | null
          payload?: Json | null
          profile_id?: string | null
          triggered_at?: string | null
          workspace_id?: string | null
        }
        Update: {
          config_id?: string | null
          content_id?: string | null
          id?: string
          is_read?: boolean | null
          payload?: Json | null
          profile_id?: string | null
          triggered_at?: string | null
          workspace_id?: string | null
        }
        Relationships: [
          {
            foreignKeyName: "alerts_feed_config_id_fkey"
            columns: ["config_id"]
            isOneToOne: false
            referencedRelation: "alerts_config"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "alerts_feed_content_id_fkey"
            columns: ["content_id"]
            isOneToOne: false
            referencedRelation: "scraped_content"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "alerts_feed_profile_id_fkey"
            columns: ["profile_id"]
            isOneToOne: false
            referencedRelation: "profiles"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "alerts_feed_workspace_id_fkey"
            columns: ["workspace_id"]
            isOneToOne: false
            referencedRelation: "workspaces"
            referencedColumns: ["id"]
          },
        ]
      }
      content_analysis: {
        Row: {
          analysis_version: string | null
          analyzed_at: string | null
          archetype: string | null
          category: Database["public"]["Enums"]["content_category"] | null
          content_id: string | null
          gemini_raw_response: Json | null
          hook_analysis: string | null
          id: string
          is_clean: boolean | null
          model_version: string | null
          quality_score: number | null
          transcription: string | null
          vibe: Database["public"]["Enums"]["content_vibe"] | null
          visual_tags: string[] | null
        }
        Insert: {
          analysis_version?: string | null
          analyzed_at?: string | null
          archetype?: string | null
          category?: Database["public"]["Enums"]["content_category"] | null
          content_id?: string | null
          gemini_raw_response?: Json | null
          hook_analysis?: string | null
          id?: string
          is_clean?: boolean | null
          model_version?: string | null
          quality_score?: number | null
          transcription?: string | null
          vibe?: Database["public"]["Enums"]["content_vibe"] | null
          visual_tags?: string[] | null
        }
        Update: {
          analysis_version?: string | null
          analyzed_at?: string | null
          archetype?: string | null
          category?: Database["public"]["Enums"]["content_category"] | null
          content_id?: string | null
          gemini_raw_response?: Json | null
          hook_analysis?: string | null
          id?: string
          is_clean?: boolean | null
          model_version?: string | null
          quality_score?: number | null
          transcription?: string | null
          vibe?: Database["public"]["Enums"]["content_vibe"] | null
          visual_tags?: string[] | null
        }
        Relationships: [
          {
            foreignKeyName: "content_analysis_content_id_fkey"
            columns: ["content_id"]
            isOneToOne: true
            referencedRelation: "scraped_content"
            referencedColumns: ["id"]
          },
        ]
      }
      content_label_assignments: {
        Row: {
          assigned_by_ai: boolean | null
          confidence: number | null
          content_id: string
          label_id: string
        }
        Insert: {
          assigned_by_ai?: boolean | null
          confidence?: number | null
          content_id: string
          label_id: string
        }
        Update: {
          assigned_by_ai?: boolean | null
          confidence?: number | null
          content_id?: string
          label_id?: string
        }
        Relationships: [
          {
            foreignKeyName: "content_label_assignments_content_id_fkey"
            columns: ["content_id"]
            isOneToOne: false
            referencedRelation: "scraped_content"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "content_label_assignments_label_id_fkey"
            columns: ["label_id"]
            isOneToOne: false
            referencedRelation: "content_labels"
            referencedColumns: ["id"]
          },
        ]
      }
      content_labels: {
        Row: {
          created_at: string | null
          created_by: string | null
          description: string | null
          id: string
          is_canonical: boolean | null
          label_type: Database["public"]["Enums"]["label_type"]
          merged_into_id: string | null
          name: string
          slug: string
          usage_count: number | null
          workspace_id: string
        }
        Insert: {
          created_at?: string | null
          created_by?: string | null
          description?: string | null
          id?: string
          is_canonical?: boolean | null
          label_type: Database["public"]["Enums"]["label_type"]
          merged_into_id?: string | null
          name: string
          slug: string
          usage_count?: number | null
          workspace_id: string
        }
        Update: {
          created_at?: string | null
          created_by?: string | null
          description?: string | null
          id?: string
          is_canonical?: boolean | null
          label_type?: Database["public"]["Enums"]["label_type"]
          merged_into_id?: string | null
          name?: string
          slug?: string
          usage_count?: number | null
          workspace_id?: string
        }
        Relationships: [
          {
            foreignKeyName: "content_labels_merged_into_id_fkey"
            columns: ["merged_into_id"]
            isOneToOne: false
            referencedRelation: "content_labels"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "content_labels_workspace_id_fkey"
            columns: ["workspace_id"]
            isOneToOne: false
            referencedRelation: "workspaces"
            referencedColumns: ["id"]
          },
        ]
      }
      content_metrics_snapshots: {
        Row: {
          comment_count: number | null
          content_id: string
          like_count: number | null
          save_count: number | null
          share_count: number | null
          snapshot_date: string
          velocity: number | null
          view_count: number | null
        }
        Insert: {
          comment_count?: number | null
          content_id: string
          like_count?: number | null
          save_count?: number | null
          share_count?: number | null
          snapshot_date?: string
          velocity?: number | null
          view_count?: number | null
        }
        Update: {
          comment_count?: number | null
          content_id?: string
          like_count?: number | null
          save_count?: number | null
          share_count?: number | null
          snapshot_date?: string
          velocity?: number | null
          view_count?: number | null
        }
        Relationships: [
          {
            foreignKeyName: "content_metrics_snapshots_content_id_fkey"
            columns: ["content_id"]
            isOneToOne: false
            referencedRelation: "scraped_content"
            referencedColumns: ["id"]
          },
        ]
      }
      creator_brand_analyses: {
        Row: {
          analyzed_at: string | null
          brand_keywords: string[] | null
          creator_id: string
          funnel_map: Json | null
          gemini_raw_response: Json | null
          id: string
          monetization_summary: string | null
          niche_summary: string | null
          platforms_included: string[] | null
          seo_keywords: string[] | null
          usp: string | null
          version: number
          workspace_id: string
        }
        Insert: {
          analyzed_at?: string | null
          brand_keywords?: string[] | null
          creator_id: string
          funnel_map?: Json | null
          gemini_raw_response?: Json | null
          id?: string
          monetization_summary?: string | null
          niche_summary?: string | null
          platforms_included?: string[] | null
          seo_keywords?: string[] | null
          usp?: string | null
          version?: number
          workspace_id: string
        }
        Update: {
          analyzed_at?: string | null
          brand_keywords?: string[] | null
          creator_id?: string
          funnel_map?: Json | null
          gemini_raw_response?: Json | null
          id?: string
          monetization_summary?: string | null
          niche_summary?: string | null
          platforms_included?: string[] | null
          seo_keywords?: string[] | null
          usp?: string | null
          version?: number
          workspace_id?: string
        }
        Relationships: [
          {
            foreignKeyName: "creator_brand_analyses_creator_id_fkey"
            columns: ["creator_id"]
            isOneToOne: false
            referencedRelation: "creators"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "creator_brand_analyses_workspace_id_fkey"
            columns: ["workspace_id"]
            isOneToOne: false
            referencedRelation: "workspaces"
            referencedColumns: ["id"]
          },
        ]
      }
      creator_merge_candidates: {
        Row: {
          confidence: number
          created_at: string | null
          creator_a_id: string
          creator_b_id: string
          evidence: Json
          id: string
          resolved_at: string | null
          resolved_by: string | null
          status: Database["public"]["Enums"]["merge_candidate_status"] | null
          triggered_by_run_id: string | null
          workspace_id: string
        }
        Insert: {
          confidence: number
          created_at?: string | null
          creator_a_id: string
          creator_b_id: string
          evidence?: Json
          id?: string
          resolved_at?: string | null
          resolved_by?: string | null
          status?: Database["public"]["Enums"]["merge_candidate_status"] | null
          triggered_by_run_id?: string | null
          workspace_id: string
        }
        Update: {
          confidence?: number
          created_at?: string | null
          creator_a_id?: string
          creator_b_id?: string
          evidence?: Json
          id?: string
          resolved_at?: string | null
          resolved_by?: string | null
          status?: Database["public"]["Enums"]["merge_candidate_status"] | null
          triggered_by_run_id?: string | null
          workspace_id?: string
        }
        Relationships: [
          {
            foreignKeyName: "creator_merge_candidates_creator_a_id_fkey"
            columns: ["creator_a_id"]
            isOneToOne: false
            referencedRelation: "creators"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "creator_merge_candidates_creator_b_id_fkey"
            columns: ["creator_b_id"]
            isOneToOne: false
            referencedRelation: "creators"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "creator_merge_candidates_triggered_by_run_id_fkey"
            columns: ["triggered_by_run_id"]
            isOneToOne: false
            referencedRelation: "discovery_runs"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "creator_merge_candidates_workspace_id_fkey"
            columns: ["workspace_id"]
            isOneToOne: false
            referencedRelation: "workspaces"
            referencedColumns: ["id"]
          },
        ]
      }
      creators: {
        Row: {
          added_by: string | null
          canonical_name: string
          created_at: string | null
          display_name_variants: string[] | null
          id: string
          import_source: string | null
          known_usernames: string[] | null
          last_discovery_error: string | null
          last_discovery_run_id: string | null
          last_discovery_run_id_fk: string | null
          monetization_model:
            | Database["public"]["Enums"]["monetization_model"]
            | null
          notes: string | null
          onboarding_status:
            | Database["public"]["Enums"]["onboarding_status"]
            | null
          primary_niche: string | null
          primary_platform: Database["public"]["Enums"]["platform"] | null
          slug: string
          tags: string[] | null
          tracking_type: Database["public"]["Enums"]["tracking_type"] | null
          updated_at: string | null
          workspace_id: string
        }
        Insert: {
          added_by?: string | null
          canonical_name: string
          created_at?: string | null
          display_name_variants?: string[] | null
          id?: string
          import_source?: string | null
          known_usernames?: string[] | null
          last_discovery_error?: string | null
          last_discovery_run_id?: string | null
          last_discovery_run_id_fk?: string | null
          monetization_model?:
            | Database["public"]["Enums"]["monetization_model"]
            | null
          notes?: string | null
          onboarding_status?:
            | Database["public"]["Enums"]["onboarding_status"]
            | null
          primary_niche?: string | null
          primary_platform?: Database["public"]["Enums"]["platform"] | null
          slug: string
          tags?: string[] | null
          tracking_type?: Database["public"]["Enums"]["tracking_type"] | null
          updated_at?: string | null
          workspace_id: string
        }
        Update: {
          added_by?: string | null
          canonical_name?: string
          created_at?: string | null
          display_name_variants?: string[] | null
          id?: string
          import_source?: string | null
          known_usernames?: string[] | null
          last_discovery_error?: string | null
          last_discovery_run_id?: string | null
          last_discovery_run_id_fk?: string | null
          monetization_model?:
            | Database["public"]["Enums"]["monetization_model"]
            | null
          notes?: string | null
          onboarding_status?:
            | Database["public"]["Enums"]["onboarding_status"]
            | null
          primary_niche?: string | null
          primary_platform?: Database["public"]["Enums"]["platform"] | null
          slug?: string
          tags?: string[] | null
          tracking_type?: Database["public"]["Enums"]["tracking_type"] | null
          updated_at?: string | null
          workspace_id?: string
        }
        Relationships: [
          {
            foreignKeyName: "creators_last_discovery_run_id_fk_fkey"
            columns: ["last_discovery_run_id_fk"]
            isOneToOne: false
            referencedRelation: "discovery_runs"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "creators_workspace_id_fkey"
            columns: ["workspace_id"]
            isOneToOne: false
            referencedRelation: "workspaces"
            referencedColumns: ["id"]
          },
        ]
      }
      discovery_runs: {
        Row: {
          assets_discovered_count: number | null
          attempt_number: number | null
          completed_at: string | null
          created_at: string | null
          creator_id: string
          error_message: string | null
          funnel_edges_discovered_count: number | null
          id: string
          initiated_by: string | null
          input_handle: string | null
          input_platform_hint: Database["public"]["Enums"]["platform"] | null
          input_screenshot_path: string | null
          input_url: string | null
          merge_candidates_raised: number | null
          raw_gemini_response: Json | null
          started_at: string | null
          status: Database["public"]["Enums"]["discovery_run_status"] | null
          workspace_id: string
        }
        Insert: {
          assets_discovered_count?: number | null
          attempt_number?: number | null
          completed_at?: string | null
          created_at?: string | null
          creator_id: string
          error_message?: string | null
          funnel_edges_discovered_count?: number | null
          id?: string
          initiated_by?: string | null
          input_handle?: string | null
          input_platform_hint?: Database["public"]["Enums"]["platform"] | null
          input_screenshot_path?: string | null
          input_url?: string | null
          merge_candidates_raised?: number | null
          raw_gemini_response?: Json | null
          started_at?: string | null
          status?: Database["public"]["Enums"]["discovery_run_status"] | null
          workspace_id: string
        }
        Update: {
          assets_discovered_count?: number | null
          attempt_number?: number | null
          completed_at?: string | null
          created_at?: string | null
          creator_id?: string
          error_message?: string | null
          funnel_edges_discovered_count?: number | null
          id?: string
          initiated_by?: string | null
          input_handle?: string | null
          input_platform_hint?: Database["public"]["Enums"]["platform"] | null
          input_screenshot_path?: string | null
          input_url?: string | null
          merge_candidates_raised?: number | null
          raw_gemini_response?: Json | null
          started_at?: string | null
          status?: Database["public"]["Enums"]["discovery_run_status"] | null
          workspace_id?: string
        }
        Relationships: [
          {
            foreignKeyName: "discovery_runs_creator_id_fkey"
            columns: ["creator_id"]
            isOneToOne: false
            referencedRelation: "creators"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "discovery_runs_workspace_id_fkey"
            columns: ["workspace_id"]
            isOneToOne: false
            referencedRelation: "workspaces"
            referencedColumns: ["id"]
          },
        ]
      }
      funnel_edges: {
        Row: {
          confidence: number | null
          creator_id: string
          detected_at: string | null
          edge_type: string | null
          from_profile_id: string
          id: string
          to_profile_id: string
          workspace_id: string
        }
        Insert: {
          confidence?: number | null
          creator_id: string
          detected_at?: string | null
          edge_type?: string | null
          from_profile_id: string
          id?: string
          to_profile_id: string
          workspace_id: string
        }
        Update: {
          confidence?: number | null
          creator_id?: string
          detected_at?: string | null
          edge_type?: string | null
          from_profile_id?: string
          id?: string
          to_profile_id?: string
          workspace_id?: string
        }
        Relationships: [
          {
            foreignKeyName: "funnel_edges_creator_id_fkey"
            columns: ["creator_id"]
            isOneToOne: false
            referencedRelation: "creators"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "funnel_edges_from_profile_id_fkey"
            columns: ["from_profile_id"]
            isOneToOne: false
            referencedRelation: "profiles"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "funnel_edges_to_profile_id_fkey"
            columns: ["to_profile_id"]
            isOneToOne: false
            referencedRelation: "profiles"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "funnel_edges_workspace_id_fkey"
            columns: ["workspace_id"]
            isOneToOne: false
            referencedRelation: "workspaces"
            referencedColumns: ["id"]
          },
        ]
      }
      profile_metrics_snapshots: {
        Row: {
          avg_engagement_rate: number | null
          follower_count: number | null
          median_views: number | null
          outlier_count: number | null
          profile_id: string
          quality_score: number | null
          snapshot_date: string
        }
        Insert: {
          avg_engagement_rate?: number | null
          follower_count?: number | null
          median_views?: number | null
          outlier_count?: number | null
          profile_id: string
          quality_score?: number | null
          snapshot_date?: string
        }
        Update: {
          avg_engagement_rate?: number | null
          follower_count?: number | null
          median_views?: number | null
          outlier_count?: number | null
          profile_id?: string
          quality_score?: number | null
          snapshot_date?: string
        }
        Relationships: [
          {
            foreignKeyName: "profile_metrics_snapshots_profile_id_fkey"
            columns: ["profile_id"]
            isOneToOne: false
            referencedRelation: "profiles"
            referencedColumns: ["id"]
          },
        ]
      }
      profile_scores: {
        Row: {
          current_rank: Database["public"]["Enums"]["rank_tier"] | null
          current_score: number | null
          last_computed_at: string | null
          profile_id: string
          scored_content_count: number | null
        }
        Insert: {
          current_rank?: Database["public"]["Enums"]["rank_tier"] | null
          current_score?: number | null
          last_computed_at?: string | null
          profile_id: string
          scored_content_count?: number | null
        }
        Update: {
          current_rank?: Database["public"]["Enums"]["rank_tier"] | null
          current_score?: number | null
          last_computed_at?: string | null
          profile_id?: string
          scored_content_count?: number | null
        }
        Relationships: [
          {
            foreignKeyName: "profile_scores_profile_id_fkey"
            columns: ["profile_id"]
            isOneToOne: true
            referencedRelation: "profiles"
            referencedColumns: ["id"]
          },
        ]
      }
      profiles: {
        Row: {
          account_type: Database["public"]["Enums"]["account_type"] | null
          added_by: string | null
          analysis_version: string | null
          avatar_url: string | null
          bio: string | null
          created_at: string | null
          creator_id: string | null
          discovery_confidence: number | null
          display_name: string | null
          follower_count: number | null
          following_count: number | null
          handle: string
          id: string
          is_active: boolean | null
          is_clean: boolean | null
          is_primary: boolean
          last_scraped_at: string | null
          platform: Database["public"]["Enums"]["platform"]
          post_count: number | null
          profile_url: string | null
          tags: string[] | null
          tracking_type: Database["public"]["Enums"]["tracking_type"] | null
          updated_at: string | null
          url: string | null
          workspace_id: string | null
        }
        Insert: {
          account_type?: Database["public"]["Enums"]["account_type"] | null
          added_by?: string | null
          analysis_version?: string | null
          avatar_url?: string | null
          bio?: string | null
          created_at?: string | null
          creator_id?: string | null
          discovery_confidence?: number | null
          display_name?: string | null
          follower_count?: number | null
          following_count?: number | null
          handle: string
          id?: string
          is_active?: boolean | null
          is_clean?: boolean | null
          is_primary?: boolean
          last_scraped_at?: string | null
          platform: Database["public"]["Enums"]["platform"]
          post_count?: number | null
          profile_url?: string | null
          tags?: string[] | null
          tracking_type?: Database["public"]["Enums"]["tracking_type"] | null
          updated_at?: string | null
          url?: string | null
          workspace_id?: string | null
        }
        Update: {
          account_type?: Database["public"]["Enums"]["account_type"] | null
          added_by?: string | null
          analysis_version?: string | null
          avatar_url?: string | null
          bio?: string | null
          created_at?: string | null
          creator_id?: string | null
          discovery_confidence?: number | null
          display_name?: string | null
          follower_count?: number | null
          following_count?: number | null
          handle?: string
          id?: string
          is_active?: boolean | null
          is_clean?: boolean | null
          is_primary?: boolean
          last_scraped_at?: string | null
          platform?: Database["public"]["Enums"]["platform"]
          post_count?: number | null
          profile_url?: string | null
          tags?: string[] | null
          tracking_type?: Database["public"]["Enums"]["tracking_type"] | null
          updated_at?: string | null
          url?: string | null
          workspace_id?: string | null
        }
        Relationships: [
          {
            foreignKeyName: "profiles_creator_id_fkey"
            columns: ["creator_id"]
            isOneToOne: false
            referencedRelation: "creators"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "profiles_workspace_id_fkey"
            columns: ["workspace_id"]
            isOneToOne: false
            referencedRelation: "workspaces"
            referencedColumns: ["id"]
          },
        ]
      }
      scraped_content: {
        Row: {
          caption: string | null
          comment_count: number | null
          created_at: string | null
          engagement_rate: number | null
          hook_text: string | null
          id: string
          is_outlier: boolean | null
          like_count: number | null
          media_urls: string[] | null
          outlier_multiplier: number | null
          platform: Database["public"]["Enums"]["platform"]
          platform_metrics: Json | null
          platform_post_id: string
          post_type: Database["public"]["Enums"]["post_type"]
          post_url: string | null
          posted_at: string | null
          profile_id: string | null
          raw_apify_payload: Json | null
          save_count: number | null
          share_count: number | null
          thumbnail_url: string | null
          updated_at: string | null
          view_count: number | null
        }
        Insert: {
          caption?: string | null
          comment_count?: number | null
          created_at?: string | null
          engagement_rate?: number | null
          hook_text?: string | null
          id?: string
          is_outlier?: boolean | null
          like_count?: number | null
          media_urls?: string[] | null
          outlier_multiplier?: number | null
          platform: Database["public"]["Enums"]["platform"]
          platform_metrics?: Json | null
          platform_post_id: string
          post_type: Database["public"]["Enums"]["post_type"]
          post_url?: string | null
          posted_at?: string | null
          profile_id?: string | null
          raw_apify_payload?: Json | null
          save_count?: number | null
          share_count?: number | null
          thumbnail_url?: string | null
          updated_at?: string | null
          view_count?: number | null
        }
        Update: {
          caption?: string | null
          comment_count?: number | null
          created_at?: string | null
          engagement_rate?: number | null
          hook_text?: string | null
          id?: string
          is_outlier?: boolean | null
          like_count?: number | null
          media_urls?: string[] | null
          outlier_multiplier?: number | null
          platform?: Database["public"]["Enums"]["platform"]
          platform_metrics?: Json | null
          platform_post_id?: string
          post_type?: Database["public"]["Enums"]["post_type"]
          post_url?: string | null
          posted_at?: string | null
          profile_id?: string | null
          raw_apify_payload?: Json | null
          save_count?: number | null
          share_count?: number | null
          thumbnail_url?: string | null
          updated_at?: string | null
          view_count?: number | null
        }
        Relationships: [
          {
            foreignKeyName: "scraped_content_profile_id_fkey"
            columns: ["profile_id"]
            isOneToOne: false
            referencedRelation: "profiles"
            referencedColumns: ["id"]
          },
        ]
      }
      trend_signals: {
        Row: {
          content_id: string | null
          detected_at: string | null
          id: string
          is_dismissed: boolean | null
          metadata: Json | null
          profile_id: string | null
          score: number | null
          signal_type: Database["public"]["Enums"]["signal_type"]
          workspace_id: string | null
        }
        Insert: {
          content_id?: string | null
          detected_at?: string | null
          id?: string
          is_dismissed?: boolean | null
          metadata?: Json | null
          profile_id?: string | null
          score?: number | null
          signal_type: Database["public"]["Enums"]["signal_type"]
          workspace_id?: string | null
        }
        Update: {
          content_id?: string | null
          detected_at?: string | null
          id?: string
          is_dismissed?: boolean | null
          metadata?: Json | null
          profile_id?: string | null
          score?: number | null
          signal_type?: Database["public"]["Enums"]["signal_type"]
          workspace_id?: string | null
        }
        Relationships: [
          {
            foreignKeyName: "trend_signals_content_id_fkey"
            columns: ["content_id"]
            isOneToOne: false
            referencedRelation: "scraped_content"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "trend_signals_profile_id_fkey"
            columns: ["profile_id"]
            isOneToOne: false
            referencedRelation: "profiles"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "trend_signals_workspace_id_fkey"
            columns: ["workspace_id"]
            isOneToOne: false
            referencedRelation: "workspaces"
            referencedColumns: ["id"]
          },
        ]
      }
      workspace_members: {
        Row: {
          joined_at: string | null
          role: Database["public"]["Enums"]["workspace_role"]
          user_id: string
          workspace_id: string
        }
        Insert: {
          joined_at?: string | null
          role?: Database["public"]["Enums"]["workspace_role"]
          user_id: string
          workspace_id: string
        }
        Update: {
          joined_at?: string | null
          role?: Database["public"]["Enums"]["workspace_role"]
          user_id?: string
          workspace_id?: string
        }
        Relationships: [
          {
            foreignKeyName: "workspace_members_workspace_id_fkey"
            columns: ["workspace_id"]
            isOneToOne: false
            referencedRelation: "workspaces"
            referencedColumns: ["id"]
          },
        ]
      }
      workspaces: {
        Row: {
          created_at: string | null
          id: string
          name: string
          owner_id: string
          slug: string
        }
        Insert: {
          created_at?: string | null
          id?: string
          name: string
          owner_id: string
          slug: string
        }
        Update: {
          created_at?: string | null
          id?: string
          name?: string
          owner_id?: string
          slug?: string
        }
        Relationships: []
      }
    }
    Views: {
      [_ in never]: never
    }
    Functions: {
      calculate_rank: {
        Args: { score: number }
        Returns: Database["public"]["Enums"]["rank_tier"]
      }
      commit_discovery_result: {
        Args: {
          p_accounts: Json
          p_creator_data: Json
          p_funnel_edges: Json
          p_run_id: string
        }
        Returns: Json
      }
      flag_outliers: { Args: { p_profile_id: string }; Returns: undefined }
      is_workspace_member: { Args: { ws_id: string }; Returns: boolean }
      mark_discovery_failed: {
        Args: { p_error: string; p_run_id: string }
        Returns: undefined
      }
      merge_creators: {
        Args: {
          p_candidate_id: string
          p_keep_id: string
          p_merge_id: string
          p_resolver_id: string
        }
        Returns: undefined
      }
      normalize_handle: { Args: { h: string }; Returns: string }
      refresh_profile_score: {
        Args: { p_profile_id: string }
        Returns: undefined
      }
      retry_creator_discovery: {
        Args: { p_creator_id: string; p_user_id: string }
        Returns: string
      }
    }
    Enums: {
      account_type:
        | "social"
        | "monetization"
        | "link_in_bio"
        | "messaging"
        | "other"
      content_category:
        | "comedy_entertainment"
        | "fashion_style"
        | "fitness"
        | "lifestyle"
        | "beauty"
        | "travel"
        | "food"
        | "music"
        | "gaming"
        | "education"
        | "other"
      content_vibe:
        | "playful"
        | "girl_next_door"
        | "body_worship"
        | "wifey"
        | "luxury"
        | "edgy"
        | "wholesome"
        | "mysterious"
        | "confident"
        | "aspirational"
      discovery_run_status: "pending" | "processing" | "completed" | "failed"
      label_type:
        | "content_format"
        | "trend_pattern"
        | "hook_style"
        | "visual_style"
        | "other"
      merge_candidate_status: "pending" | "merged" | "dismissed"
      monetization_model:
        | "subscription"
        | "tips"
        | "ppv"
        | "affiliate"
        | "brand_deals"
        | "ecommerce"
        | "coaching"
        | "saas"
        | "mixed"
        | "unknown"
      onboarding_status: "processing" | "ready" | "failed" | "archived"
      platform:
        | "instagram"
        | "tiktok"
        | "youtube"
        | "patreon"
        | "twitter"
        | "linkedin"
        | "onlyfans"
        | "fanvue"
        | "fanplace"
        | "amazon_storefront"
        | "tiktok_shop"
        | "linktree"
        | "beacons"
        | "custom_domain"
        | "telegram_channel"
        | "telegram_cupidbot"
        | "facebook"
        | "other"
      post_type:
        | "reel"
        | "tiktok_video"
        | "image"
        | "carousel"
        | "story"
        | "story_highlight"
        | "youtube_short"
        | "youtube_long"
        | "other"
      rank_tier:
        | "diamond"
        | "platinum"
        | "gold"
        | "silver"
        | "bronze"
        | "plastic"
      signal_type:
        | "velocity_spike"
        | "outlier_post"
        | "emerging_archetype"
        | "hook_pattern"
        | "cadence_change"
        | "new_monetization_detected"
      tracking_type:
        | "managed"
        | "inspiration"
        | "competitor"
        | "candidate"
        | "hybrid_ai"
        | "coach"
        | "unreviewed"
      workspace_role: "owner" | "admin" | "member"
    }
    CompositeTypes: {
      [_ in never]: never
    }
  }
}

type DatabaseWithoutInternals = Omit<Database, "__InternalSupabase">

type DefaultSchema = DatabaseWithoutInternals[Extract<keyof Database, "public">]

export type Tables<
  DefaultSchemaTableNameOrOptions extends
    | keyof (DefaultSchema["Tables"] & DefaultSchema["Views"])
    | { schema: keyof DatabaseWithoutInternals },
  TableName extends DefaultSchemaTableNameOrOptions extends {
    schema: keyof DatabaseWithoutInternals
  }
    ? keyof (DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"] &
        DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Views"])
    : never = never,
> = DefaultSchemaTableNameOrOptions extends {
  schema: keyof DatabaseWithoutInternals
}
  ? (DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"] &
      DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Views"])[TableName] extends {
      Row: infer R
    }
    ? R
    : never
  : DefaultSchemaTableNameOrOptions extends keyof (DefaultSchema["Tables"] &
        DefaultSchema["Views"])
  ? (DefaultSchema["Tables"] &
      DefaultSchema["Views"])[DefaultSchemaTableNameOrOptions] extends {
      Row: infer R
    }
    ? R
    : never
  : never

export type TablesInsert<
  DefaultSchemaTableNameOrOptions extends
    | keyof DefaultSchema["Tables"]
    | { schema: keyof DatabaseWithoutInternals },
  TableName extends DefaultSchemaTableNameOrOptions extends {
    schema: keyof DatabaseWithoutInternals
  }
    ? keyof DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"]
    : never = never,
> = DefaultSchemaTableNameOrOptions extends {
  schema: keyof DatabaseWithoutInternals
}
  ? DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"][TableName] extends {
      Insert: infer I
    }
    ? I
    : never
  : DefaultSchemaTableNameOrOptions extends keyof DefaultSchema["Tables"]
  ? DefaultSchema["Tables"][DefaultSchemaTableNameOrOptions] extends {
      Insert: infer I
    }
    ? I
    : never
  : never

export type TablesUpdate<
  DefaultSchemaTableNameOrOptions extends
    | keyof DefaultSchema["Tables"]
    | { schema: keyof DatabaseWithoutInternals },
  TableName extends DefaultSchemaTableNameOrOptions extends {
    schema: keyof DatabaseWithoutInternals
  }
    ? keyof DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"]
    : never = never,
> = DefaultSchemaTableNameOrOptions extends {
  schema: keyof DatabaseWithoutInternals
}
  ? DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"][TableName] extends {
      Update: infer U
    }
    ? U
    : never
  : DefaultSchemaTableNameOrOptions extends keyof DefaultSchema["Tables"]
  ? DefaultSchema["Tables"][DefaultSchemaTableNameOrOptions] extends {
      Update: infer U
    }
    ? U
    : never
  : never

export type Enums<
  DefaultSchemaEnumNameOrOptions extends
    | keyof DefaultSchema["Enums"]
    | { schema: keyof DatabaseWithoutInternals },
  EnumName extends DefaultSchemaEnumNameOrOptions extends {
    schema: keyof DatabaseWithoutInternals
  }
    ? keyof DatabaseWithoutInternals[DefaultSchemaEnumNameOrOptions["schema"]]["Enums"]
    : never = never,
> = DefaultSchemaEnumNameOrOptions extends {
  schema: keyof DatabaseWithoutInternals
}
  ? DatabaseWithoutInternals[DefaultSchemaEnumNameOrOptions["schema"]]["Enums"][EnumName]
  : DefaultSchemaEnumNameOrOptions extends keyof DefaultSchema["Enums"]
  ? DefaultSchema["Enums"][DefaultSchemaEnumNameOrOptions]
  : never

export type CompositeTypes<
  PublicCompositeTypeNameOrOptions extends
    | keyof DefaultSchema["CompositeTypes"]
    | { schema: keyof DatabaseWithoutInternals },
  CompositeTypeName extends PublicCompositeTypeNameOrOptions extends {
    schema: keyof DatabaseWithoutInternals
  }
    ? keyof DatabaseWithoutInternals[PublicCompositeTypeNameOrOptions["schema"]]["CompositeTypes"]
    : never = never,
> = PublicCompositeTypeNameOrOptions extends {
  schema: keyof DatabaseWithoutInternals
}
  ? DatabaseWithoutInternals[PublicCompositeTypeNameOrOptions["schema"]]["CompositeTypes"][CompositeTypeName]
  : PublicCompositeTypeNameOrOptions extends keyof DefaultSchema["CompositeTypes"]
  ? DefaultSchema["CompositeTypes"][PublicCompositeTypeNameOrOptions]
  : never

export const Constants = {
  public: {
    Enums: {
      account_type: [
        "social",
        "monetization",
        "link_in_bio",
        "messaging",
        "other",
      ],
      content_category: [
        "comedy_entertainment",
        "fashion_style",
        "fitness",
        "lifestyle",
        "beauty",
        "travel",
        "food",
        "music",
        "gaming",
        "education",
        "other",
      ],
      content_vibe: [
        "playful",
        "girl_next_door",
        "body_worship",
        "wifey",
        "luxury",
        "edgy",
        "wholesome",
        "mysterious",
        "confident",
        "aspirational",
      ],
      discovery_run_status: ["pending", "processing", "completed", "failed"],
      label_type: [
        "content_format",
        "trend_pattern",
        "hook_style",
        "visual_style",
        "other",
      ],
      merge_candidate_status: ["pending", "merged", "dismissed"],
      monetization_model: [
        "subscription",
        "tips",
        "ppv",
        "affiliate",
        "brand_deals",
        "ecommerce",
        "coaching",
        "saas",
        "mixed",
        "unknown",
      ],
      onboarding_status: ["processing", "ready", "failed", "archived"],
      platform: [
        "instagram",
        "tiktok",
        "youtube",
        "patreon",
        "twitter",
        "linkedin",
        "onlyfans",
        "fanvue",
        "fanplace",
        "amazon_storefront",
        "tiktok_shop",
        "linktree",
        "beacons",
        "custom_domain",
        "telegram_channel",
        "telegram_cupidbot",
        "facebook",
        "other",
      ],
      post_type: [
        "reel",
        "tiktok_video",
        "image",
        "carousel",
        "story",
        "story_highlight",
        "youtube_short",
        "youtube_long",
        "other",
      ],
      rank_tier: ["diamond", "platinum", "gold", "silver", "bronze", "plastic"],
      signal_type: [
        "velocity_spike",
        "outlier_post",
        "emerging_archetype",
        "hook_pattern",
        "cadence_change",
        "new_monetization_detected",
      ],
      tracking_type: [
        "managed",
        "inspiration",
        "competitor",
        "candidate",
        "hybrid_ai",
        "coach",
        "unreviewed",
      ],
      workspace_role: ["owner", "admin", "member"],
    },
  },
} as const
