# PROJECT_STATE.md
**Agency Command Center**

## Schema Overview
- **workspaces & workspace_members**: Tenancy routing and role-based access logic (`owner`, `admin`, `member`).
- **profiles**: Core entities tracked across platforms.
- **scraped_content**: Unique posts. Upsert logic depends on `(platform, platform_post_id)`.
- **content_metrics_snapshots & profile_metrics_snapshots**: Time-series tables tracking daily velocity and metric shifts.
- **content_analysis**: LLM-generated output, linked strictly 1:1 with scraped content.
- **profile_scores**: Continuously aggregated view of a profile's average quality, assigning a rank.
- **trend_signals & alerts**: Core event bus for spikes and outliers. 

## Enum Values
* **platform**: `instagram`, `tiktok`, `youtube`, `patreon`, `twitter`, `linkedin`
* **tracking_type**: `managed`, `inspiration`, `competitor`, `candidate`, `hybrid_ai`, `coach`, `unreviewed`
* **rank_tier**: `diamond`, `platinum`, `gold`, `silver`, `bronze`, `plastic`
* **post_type**: `reel`, `tiktok_video`, `image`, `carousel`, `story`
* *(Note: content_archetype enum removed as per user request, will use TEXT for flexible identification).*
* **content_vibe**: `playful`, `girl_next_door`, `body_worship`, `wifey`, `luxury`, `edgy`, `wholesome`, `mysterious`, `confident`, `aspirational`
* **content_category**: `comedy_entertainment`, `fashion_style`, `fitness`, `lifestyle`, `beauty`, `travel`, `food`, `music`, `gaming`, `education`, `other`
* **workspace_role**: `owner`, `admin`, `member`
* **signal_type**: `velocity_spike`, `outlier_post`, `emerging_archetype`, `hook_pattern`, `cadence_change`

## RLS Model
User data isolated by `workspace_id`. `is_workspace_member()` performs the check. `profiles` allows INSERT/UPDATE to enable tracking new accounts from the UI frontend.

## Environment Variables
Must be present in `.env.local`:
- `NEXT_PUBLIC_SUPABASE_URL`
- `NEXT_PUBLIC_SUPABASE_ANON_KEY`
- `SUPABASE_SERVICE_ROLE_KEY` (Python)
- `APIFY_TOKEN` (Python)
- `GEMINI_API_KEY` (Python)
- `RESEND_API_KEY` (Python)
