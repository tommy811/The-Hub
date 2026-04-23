// src/lib/db/queries.ts
// Workspace-scoped read helpers. Pages NEVER call .from() directly — they call helpers from here.
// This makes the workspace_id requirement structural (typed, not convention).
// If this file grows past ~300 lines, split by domain (creators.ts, profiles.ts, content.ts).

import { createServiceClient } from '@/lib/supabase/server'
import type { Tables, Enums } from '@/types/db'

// ---------- creators ----------

export type CreatorWithProfiles = Tables<'creators'> & {
  profiles: Pick<
    Tables<'profiles'>,
    | 'id'
    | 'avatar_url'
    | 'platform'
    | 'account_type'
    | 'follower_count'
    | 'is_primary'
    | 'handle'
    | 'display_name'
    | 'discovery_confidence'
  >[]
}

export type CreatorListFilters = {
  status?: Enums<'onboarding_status'> | 'all'
  tracking?: Enums<'tracking_type'> | 'all'
  q?: string
  sort?: 'recently_added' | 'name_asc' | 'platform'
}

export async function getCreatorsForWorkspace(
  wsId: string,
  filters: CreatorListFilters = {}
): Promise<CreatorWithProfiles[]> {
  const supabase = createServiceClient()
  let query = supabase
    .from('creators')
    .select(`
      *,
      profiles!creator_id (
        id, avatar_url, platform, account_type, follower_count,
        is_primary, handle, display_name, discovery_confidence
      )
    `)
    .eq('workspace_id', wsId)

  if (filters.status && filters.status !== 'all') {
    query = query.eq('onboarding_status', filters.status)
  }
  if (filters.tracking && filters.tracking !== 'all') {
    query = query.eq('tracking_type', filters.tracking)
  }
  if (filters.q && filters.q.trim().length > 0) {
    query = query.ilike('canonical_name', `%${filters.q.trim()}%`)
  }

  switch (filters.sort) {
    case 'name_asc':
      query = query.order('canonical_name', { ascending: true })
      break
    case 'platform':
      query = query.order('primary_platform', { ascending: true, nullsFirst: false })
      break
    case 'recently_added':
    default:
      query = query.order('created_at', { ascending: false })
  }

  const { data, error } = await query
  if (error) throw new Error(`getCreatorsForWorkspace: ${error.message}`)
  return (data ?? []) as CreatorWithProfiles[]
}

export async function getCreatorBySlugForWorkspace(
  wsId: string,
  slug: string
): Promise<Tables<'creators'> | null> {
  const supabase = createServiceClient()
  const { data, error } = await supabase
    .from('creators')
    .select('*')
    .eq('workspace_id', wsId)
    .eq('slug', slug)
    .maybeSingle()
  if (error) throw new Error(`getCreatorBySlugForWorkspace: ${error.message}`)
  return data
}

export async function getCreatorStatsForWorkspace(
  wsId: string
): Promise<{
  byStatus: Record<Enums<'onboarding_status'> | 'all', number>
  byTracking: Record<Enums<'tracking_type'> | 'all', number>
}> {
  const supabase = createServiceClient()
  const { data, error } = await supabase
    .from('creators')
    .select('onboarding_status, tracking_type')
    .eq('workspace_id', wsId)
  if (error) throw new Error(`getCreatorStatsForWorkspace: ${error.message}`)

  const rows = data ?? []
  const byStatus: Record<string, number> = { all: rows.length }
  const byTracking: Record<string, number> = { all: rows.length }
  for (const r of rows) {
    if (r.onboarding_status) byStatus[r.onboarding_status] = (byStatus[r.onboarding_status] ?? 0) + 1
    if (r.tracking_type) byTracking[r.tracking_type] = (byTracking[r.tracking_type] ?? 0) + 1
  }
  return { byStatus: byStatus as any, byTracking: byTracking as any }
}

// ---------- profiles ----------

export type ProfileForCreator = Pick<
  Tables<'profiles'>,
  | 'id'
  | 'platform'
  | 'handle'
  | 'display_name'
  | 'url'
  | 'follower_count'
  | 'following_count'
  | 'post_count'
  | 'bio'
  | 'account_type'
  | 'discovery_confidence'
  | 'is_primary'
  | 'updated_at'
  | 'avatar_url'
>

export async function getProfilesForCreator(
  creatorId: string
): Promise<ProfileForCreator[]> {
  const supabase = createServiceClient()
  const { data, error } = await supabase
    .from('profiles')
    .select(
      'id, platform, handle, display_name, url, follower_count, following_count, post_count, bio, account_type, discovery_confidence, is_primary, updated_at, avatar_url'
    )
    .eq('creator_id', creatorId)
    .order('is_primary', { ascending: false })
  if (error) throw new Error(`getProfilesForCreator: ${error.message}`)
  return (data ?? []) as ProfileForCreator[]
}
