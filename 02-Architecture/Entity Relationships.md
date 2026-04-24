# Entity Relationships

## Cardinalities

| From | To | Type | Notes |
|---|---|---|---|
| workspace | creators | 1:many | All creators belong to one workspace |
| workspace | workspace_members | 1:many | 2-5 members per workspace |
| workspace | trend_signals | 1:many | Signals scoped to workspace |
| workspace | alerts_config | 1:many | Alert rules scoped to workspace |
| workspace | alerts_feed | 1:many | Alert notifications scoped to workspace |
| workspace | trends | 1:many | Trend registry scoped per workspace |
| creator | profiles | 1:many | One creator has many accounts (social, OF, Linktree, etc.) |
| creator | discovery_runs | 1:many | Multiple attempts possible (retries) |
| creator | creator_merge_candidates | many:many | A creator can appear in multiple candidate pairs |
| creator | funnel_edges | 1:many | Creator owns all traffic edges between their accounts |
| creator | creator_brand_analyses | 1:many | Versioned analyses over time |
| creator | creator_label_assignments | 1:many | Creator-level niche tagging |
| profile | scraped_content | 1:many | One account has many posts |
| profile | profile_metrics_snapshots | 1:many | Daily snapshots |
| profile | trend_signals | 1:many | Signals linked to specific profile |
| scraped_content | content_metrics_snapshots | 1:many | Daily view/engagement snapshots |
| scraped_content | content_analysis | 1:1 | One Gemini analysis per post |
| scraped_content | content_label_assignments | 1:many | Multiple labels per post |
| scraped_content | trend_signals | 1:many | Signals linked to specific post |
| scraped_content | alerts_feed | 1:many | Alert notifications for specific post |
| trends | scraped_content | 1:many | Trend links to all posts participating in it |
| content_labels | content_label_assignments | 1:many | One label assigned to many posts |
| content_labels | creator_label_assignments | 1:many | One label assigned to many creators |
| content_labels | content_labels | self | merged_into_id for deduplication |
| alerts_config | alerts_feed | 1:many | Each rule can fire many notifications |

## Key FKs to Know
- `profiles.creator_id` → `creators.id` (nullable — existing profiles without a creator)
- `discovery_runs.creator_id` → `creators.id` (NOT nullable)
- `creators.last_discovery_run_id` → `discovery_runs.id` (nullable, ON DELETE SET NULL)
- `creator_merge_candidates.creator_a_id < creator_b_id` (enforced CHECK — prevents duplicate pairs)
- `funnel_edges.from_profile_id` ≠ `to_profile_id` (enforced CHECK)
- `scraped_content.trend_id` → `trends.id` (nullable, ON DELETE SET NULL — applied 2026-04-24)
- `trends`: UNIQUE `(workspace_id, audio_signature)` WHERE `audio_signature IS NOT NULL` — prevents double-registering a track per workspace
