# Migration Log

## 20240101000000_initial_schema

Base platform schema: workspaces, workspace_members, profiles, scraped_content,

content_metrics_snapshots, profile_metrics_snapshots, content_analysis,

profile_scores.

Functions: calculate_rank, flag_outliers, refresh_profile_score, is_workspace_member.

## 20240102000000_creator_layer

Creator entity + discovery pipeline + identity resolution.

New tables: creators, discovery_runs, creator_merge_candidates, funnel_edges,

content_labels, content_label_assignments, creator_brand_analyses.

New columns on profiles: creator_id, account_type, url, discovery_confidence, updated_at.

New RPCs: commit_discovery_result, mark_discovery_failed, retry_creator_discovery, merge_creators.

Realtime enabled: creators, discovery_runs, creator_merge_candidates.
