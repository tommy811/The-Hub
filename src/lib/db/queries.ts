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

export async function getCreatorNameById(
  creatorId: string
): Promise<string | null> {
  const supabase = createServiceClient()
  const { data, error } = await supabase
    .from('creators')
    .select('canonical_name')
    .eq('id', creatorId)
    .maybeSingle()
  if (error) throw new Error(`getCreatorNameById: ${error.message}`)
  return data?.canonical_name ?? null
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
    .eq('is_active', true)
    .order('is_primary', { ascending: false })
  if (error) throw new Error(`getProfilesForCreator: ${error.message}`)
  return (data ?? []) as ProfileForCreator[]
}

// ---------- platform-account list (Instagram/TikTok pages) ----------

export type PlatformAccountRow = {
  id: string
  handle: string
  displayName: string
  avatarUrl: string | null
  profileUrl: string | null
  followerCount: number | null
  postCount: number | null
  trackingType: string
  isClean: boolean
  analysisVersion: string | null
  creatorId: string | null
  creatorSlug: string | null
  currentScore: number | null
  currentRank: string | null
  scoredContentCount: number
  medianViews: number | null
  outlierCount: number
  hasContent: boolean
}

export async function getPlatformAccountsForWorkspace(
  wsId: string,
  args: {
    platform: Enums<'platform'>
    accountType?: Enums<'account_type'>
  }
): Promise<PlatformAccountRow[]> {
  const supabase = createServiceClient()

  const { data: rawProfiles, error: pErr } = await supabase
    .from('profiles')
    .select(`
      id, handle, display_name, avatar_url, profile_url,
      follower_count, post_count, tracking_type, is_clean,
      analysis_version, creator_id,
      profile_scores ( current_score, current_rank, scored_content_count ),
      creators!creator_id ( slug )
    `)
    .eq('workspace_id', wsId)
    .eq('platform', args.platform)
    .eq('account_type', args.accountType ?? 'social')

  if (pErr) throw new Error(`getPlatformAccountsForWorkspace.profiles: ${pErr.message}`)
  if (!rawProfiles || rawProfiles.length === 0) return []

  const profileIds = rawProfiles.map((p) => p.id)

  const [snapshotsRes, contentRes] = await Promise.all([
    supabase
      .from('profile_metrics_snapshots')
      .select('profile_id, median_views, snapshot_date')
      .in('profile_id', profileIds)
      .order('snapshot_date', { ascending: false }),
    supabase
      .from('scraped_content')
      .select('profile_id, is_outlier, view_count, posted_at')
      .in('profile_id', profileIds),
  ])

  if (snapshotsRes.error) {
    throw new Error(`getPlatformAccountsForWorkspace.snapshots: ${snapshotsRes.error.message}`)
  }
  if (contentRes.error) {
    throw new Error(`getPlatformAccountsForWorkspace.content: ${contentRes.error.message}`)
  }

  // Latest snapshot per profile
  const snapshotMap = new Map<string, number>()
  for (const snap of snapshotsRes.data ?? []) {
    if (!snapshotMap.has(snap.profile_id)) {
      snapshotMap.set(snap.profile_id, Number(snap.median_views))
    }
  }

  // Live median fallback for profiles missing a snapshot
  const contentSet = new Set<string>()
  const outlierCountMap = new Map<string, number>()
  const viewsByProfile = new Map<string, number[]>()
  const cutoff = new Date(Date.now() - 90 * 24 * 60 * 60 * 1000)

  for (const row of contentRes.data ?? []) {
    contentSet.add(row.profile_id!)
    if (row.is_outlier) {
      outlierCountMap.set(row.profile_id!, (outlierCountMap.get(row.profile_id!) ?? 0) + 1)
    }
    if (
      !snapshotMap.has(row.profile_id!) &&
      row.view_count != null &&
      row.posted_at &&
      new Date(row.posted_at) >= cutoff
    ) {
      const arr = viewsByProfile.get(row.profile_id!) ?? []
      arr.push(Number(row.view_count))
      viewsByProfile.set(row.profile_id!, arr)
    }
  }

  for (const [profileId, views] of viewsByProfile) {
    if (views.length > 0) {
      const sorted = [...views].sort((a, b) => a - b)
      const mid = Math.floor(sorted.length / 2)
      const median =
        sorted.length % 2 === 0
          ? (sorted[mid - 1] + sorted[mid]) / 2
          : sorted[mid]
      snapshotMap.set(profileId, Math.round(median))
    }
  }

  const accounts: PlatformAccountRow[] = rawProfiles.map((p) => {
    const scores = Array.isArray(p.profile_scores)
      ? p.profile_scores[0] ?? null
      : (p.profile_scores ?? null)
    const creator = Array.isArray(p.creators)
      ? p.creators[0] ?? null
      : (p.creators ?? null)

    return {
      id: p.id,
      handle: p.handle ?? '',
      displayName: p.display_name ?? p.handle ?? '',
      avatarUrl: p.avatar_url ?? null,
      profileUrl: p.profile_url ?? null,
      followerCount: p.follower_count != null ? Number(p.follower_count) : null,
      postCount: p.post_count != null ? Number(p.post_count) : null,
      trackingType: p.tracking_type ?? 'unreviewed',
      isClean: p.is_clean ?? false,
      analysisVersion: p.analysis_version ?? null,
      creatorId: p.creator_id ?? null,
      creatorSlug: (creator as { slug?: string } | null)?.slug ?? null,
      currentScore: scores?.current_score != null ? Number(scores.current_score) : null,
      currentRank: scores?.current_rank ?? null,
      scoredContentCount: scores?.scored_content_count ?? 0,
      medianViews: snapshotMap.get(p.id) ?? null,
      outlierCount: outlierCountMap.get(p.id) ?? 0,
      hasContent: contentSet.has(p.id),
    }
  })

  // Default sort: quality score desc, unscored last
  accounts.sort((a, b) => {
    if (a.currentScore === null && b.currentScore === null) return 0
    if (a.currentScore === null) return 1
    if (b.currentScore === null) return -1
    return b.currentScore - a.currentScore
  })

  return accounts
}

// ---------- Command Center ----------

export async function getCommandCenterStats(wsId: string): Promise<{
  creatorCount: number
  postCount: number
  pendingDiscoveryCount: number
  avgQualityScore: number | null
}> {
  const supabase = createServiceClient()

  const [creatorsRes, pendingRes, contentCountRes, scoresRes] = await Promise.all([
    supabase
      .from('creators')
      .select('*', { count: 'exact', head: true })
      .eq('workspace_id', wsId),
    supabase
      .from('discovery_runs')
      .select('*', { count: 'exact', head: true })
      .eq('workspace_id', wsId)
      .in('status', ['pending', 'processing']),
    // scraped_content has no workspace_id — scope via profile_id IN (workspace profiles)
    supabase
      .from('scraped_content')
      .select('profiles!inner(workspace_id)', { count: 'exact', head: true })
      .eq('profiles.workspace_id', wsId),
    supabase
      .from('profile_scores')
      .select('current_score, profiles!inner(workspace_id)')
      .eq('profiles.workspace_id', wsId),
  ])

  const scores = (scoresRes.data ?? [])
    .map((r) => Number(r.current_score))
    .filter((n) => !Number.isNaN(n) && n > 0)
  const avg =
    scores.length > 0 ? scores.reduce((a, b) => a + b, 0) / scores.length : null

  return {
    creatorCount: creatorsRes.count ?? 0,
    postCount: contentCountRes.count ?? 0,
    pendingDiscoveryCount: pendingRes.count ?? 0,
    avgQualityScore: avg !== null ? Math.round(avg * 10) / 10 : null,
  }
}

export async function getRecentOutliersForWorkspace(
  wsId: string,
  limit = 5
): Promise<Array<{
  profileHandle: string
  outlierMultiplier: number | null
  viewCount: number
  postUrl: string | null
}>> {
  const supabase = createServiceClient()
  const { data, error } = await supabase
    .from('scraped_content')
    .select(`
      view_count, outlier_multiplier, post_url,
      profiles!inner ( handle, workspace_id )
    `)
    .eq('profiles.workspace_id', wsId)
    .eq('is_outlier', true)
    .order('outlier_multiplier', { ascending: false, nullsFirst: false })
    .limit(limit)
  if (error) throw new Error(`getRecentOutliersForWorkspace: ${error.message}`)
  return (data ?? []).map((r: any) => ({
    profileHandle: r.profiles?.handle ?? '',
    outlierMultiplier: r.outlier_multiplier != null ? Number(r.outlier_multiplier) : null,
    viewCount: Number(r.view_count ?? 0),
    postUrl: r.post_url ?? null,
  }))
}

export async function getActiveTrendSignalsForWorkspace(
  wsId: string,
  limit = 5
): Promise<Array<{
  signalType: Enums<'signal_type'>
  score: number | null
  metadata: Record<string, unknown>
  detectedAt: string | null
}>> {
  const supabase = createServiceClient()
  const { data, error } = await supabase
    .from('trend_signals')
    .select('signal_type, score, metadata, detected_at')
    .eq('workspace_id', wsId)
    .eq('is_dismissed', false)
    .order('detected_at', { ascending: false })
    .limit(limit)
  if (error) throw new Error(`getActiveTrendSignalsForWorkspace: ${error.message}`)
  return (data ?? []).map((r) => ({
    signalType: r.signal_type as Enums<'signal_type'>,
    score: r.score != null ? Number(r.score) : null,
    metadata: (r.metadata as Record<string, unknown>) ?? {},
    detectedAt: r.detected_at,
  }))
}

// ---------- merge candidates ----------

export async function getMergeCandidatesForWorkspace(
  wsId: string
): Promise<Tables<'creator_merge_candidates'>[]> {
  const supabase = createServiceClient()
  const { data, error } = await supabase
    .from('creator_merge_candidates')
    .select('*')
    .eq('workspace_id', wsId)
    .eq('status', 'pending')
  if (error) throw new Error(`getMergeCandidatesForWorkspace: ${error.message}`)
  return data ?? []
}

export async function getMergeCandidatesForCreator(
  creatorId: string
): Promise<Tables<'creator_merge_candidates'>[]> {
  const supabase = createServiceClient()
  const { data, error } = await supabase
    .from('creator_merge_candidates')
    .select('*')
    .eq('status', 'pending')
    .or(`creator_a_id.eq.${creatorId},creator_b_id.eq.${creatorId}`)
  if (error) throw new Error(`getMergeCandidatesForCreator: ${error.message}`)
  return data ?? []
}
