# Identity Resolution Rules

## The Problem
A creator uses different usernames per platform:
- `@viking.barbie` on Instagram
- `@vikingbarbie.ttk` on TikTok
- `vikingb` on OnlyFans

If imported separately, they become 3 creators instead of 1.

## Handle Normalization
Strip `@`, `.`, `-`, `_`, whitespace → lowercase.
`viking.barbie` → `vikingbarbie`
`vikingbarbie.ttk` → `vikingbarbietk` ← NOT a match (suffix changes meaning)

Implemented in:
- Python: `normalize_handle()` in `scripts/common.py` using rapidfuzz
- SQL: `normalize_handle()` function in Supabase

## Confidence Levels

| Score | Action | Trigger |
|---|---|---|
| 1.0 | Auto-merge silently | Direct link chain (IG bio → Linktree → TikTok, both already in DB) |
| 0.7–0.99 | Raise merge candidate, surface in UI | Display name match + handle similarity, no direct link |
| < 0.7 | Log and discard | Common name, no other signals |

## Merge Candidate Evidence Signals
Stored as JSONB array in `creator_merge_candidates.evidence`:
- `handle_collision` — exact handle exists under different creator
- `handle_similarity` — rapidfuzz ratio > 0.85 after normalization
- `shared_linktree` — same Linktree destination URL found on both
- `display_name_match` — display names match after normalization

## Merge Rules
- Always keep the **older** creator record (higher data volume)
- `known_usernames[]` merges both arrays, deduplicates, keeps permanently
- All `profiles` rows migrate from merged → kept creator
- Merged creator sets `onboarding_status = 'archived'`
- Implemented via `merge_creators(keep_id, merge_id, resolver_id, candidate_id)` RPC

## Where Detection Happens
Inside `commit_discovery_result` RPC — before inserting any proposed account,
checks if that handle exists under a different creator in the workspace.
If yes: raises `creator_merge_candidates` row, skips inserting under current creator.
