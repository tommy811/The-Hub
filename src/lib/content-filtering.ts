import type { AudioTrendRow, ContentLibraryRow } from "@/lib/db/queries"

export type ContentScope =
  | "all"
  | "outliers"
  | "audio"
  | "trended"
  | "untrended"
  | "with_views"
  | "missing_views"
  | "pinned"
  | "sponsored"
  | "review"
export type ContentSort =
  | "copy_priority"
  | "recent"
  | "views"
  | "engagement"
  | "outlier"
  | "trend_usage"
  | "likes"
  | "comments"
  | "shares"
  | "saves"
  | "profile"
export type ContentPostType = "all" | "reel" | "tiktok_video" | "image" | "carousel"

export type ContentFilters = {
  q: string
  platform: "all" | "instagram" | "tiktok"
  scope: ContentScope
  sort: ContentSort
  postType: ContentPostType
  minMultiplier: number | null
}

export type AudioTrendFilters = {
  q: string
  sort: "usage" | "creators" | "name" | "recent"
  minUsage: number
  minCreators: number
}

export function parseContentFilters(input: Record<string, string | string[] | undefined>): ContentFilters {
  const platform = single(input.platform)
  const scope = single(input.scope)
  const sort = single(input.sort)
  const postType = single(input.type)
  const min = Number(single(input.min) ?? "")

  return {
    q: single(input.q)?.trim() ?? "",
    platform: platform === "instagram" || platform === "tiktok" ? platform : "all",
    scope: isContentScope(scope) ? scope : "all",
    sort: isContentSort(sort) ? sort : "recent",
    postType: isContentPostType(postType) ? postType : "all",
    minMultiplier: Number.isFinite(min) && min > 0 ? min : null,
  }
}

export function parseAudioTrendFilters(input: Record<string, string | string[] | undefined>): AudioTrendFilters {
  const sort = single(input.sort)
  const min = Number(single(input.minUsage) ?? "")
  const minCreators = Number(single(input.minCreators) ?? "")

  return {
    q: single(input.q)?.trim() ?? "",
    sort: sort === "name" || sort === "recent" || sort === "creators" ? sort : "usage",
    minUsage: Number.isFinite(min) && min > 0 ? min : 2,
    minCreators: Number.isFinite(minCreators) && minCreators > 0 ? minCreators : 1,
  }
}

export function filterContentRows(rows: ContentLibraryRow[], filters: ContentFilters): ContentLibraryRow[] {
  const q = filters.q.toLowerCase()
  return sortContentRows(
    rows.filter((row) => {
      if (filters.platform !== "all" && row.platform !== filters.platform) return false
      if (filters.postType !== "all" && row.postType !== filters.postType) return false
      if (filters.minMultiplier != null && (row.outlierMultiplier ?? 0) < filters.minMultiplier) return false
      if (filters.scope === "outliers" && !row.isOutlier) return false
      if (filters.scope === "audio" && !row.audioSignature) return false
      if (filters.scope === "trended" && !row.trendId) return false
      if (filters.scope === "untrended" && row.trendId) return false
      if (filters.scope === "with_views" && !row.viewCountAvailable) return false
      if (filters.scope === "missing_views" && row.viewCountAvailable) return false
      if (filters.scope === "pinned" && !row.isPinned) return false
      if (filters.scope === "sponsored" && !row.isSponsored) return false
      if (filters.scope === "review" && row.qualityFlag === "clean") return false
      if (!q) return true

      return [
        row.caption,
        row.profileHandle,
        row.creatorName,
        row.platform,
        row.postType,
        row.audioArtist,
        row.audioTitle,
        row.audioSignature,
        row.trendName,
      ].some((value) => value?.toLowerCase().includes(q))
    }),
    filters.sort
  )
}

export function sortContentRows(rows: ContentLibraryRow[], sort: ContentSort): ContentLibraryRow[] {
  return [...rows].sort((a, b) => {
    if (sort === "copy_priority") return b.copyPriorityScore - a.copyPriorityScore
    if (sort === "views") return sortNullableMetric(viewMetric(b), viewMetric(a))
    if (sort === "engagement") return (b.engagementRate ?? -1) - (a.engagementRate ?? -1)
    if (sort === "outlier") return (b.outlierMultiplier ?? -1) - (a.outlierMultiplier ?? -1)
    if (sort === "trend_usage") return (b.trendUsageCount ?? -1) - (a.trendUsageCount ?? -1)
    if (sort === "likes") return b.likeCount - a.likeCount
    if (sort === "comments") return b.commentCount - a.commentCount
    if (sort === "shares") return sortNullableMetric(b.shareCount, a.shareCount)
    if (sort === "saves") return sortNullableMetric(b.saveCount, a.saveCount)
    if (sort === "profile") return a.profileHandle.localeCompare(b.profileHandle)
    return dateValue(b.postedAt) - dateValue(a.postedAt)
  })
}

export function filterAudioTrends(rows: AudioTrendRow[], filters: AudioTrendFilters): AudioTrendRow[] {
  const q = filters.q.toLowerCase()
  return [...rows]
    .filter((row) => {
      if (row.usageCount < filters.minUsage) return false
      if (row.creatorCount < filters.minCreators) return false
      if (!q) return true
      return [
        row.name,
        row.audioArtist,
        row.audioTitle,
        row.audioSignature,
      ].some((value) => value?.toLowerCase().includes(q))
    })
    .sort((a, b) => {
      if (filters.sort === "name") return a.name.localeCompare(b.name)
      if (filters.sort === "recent") return dateValue(b.updatedAt ?? b.createdAt) - dateValue(a.updatedAt ?? a.createdAt)
      if (filters.sort === "creators") return b.creatorCount - a.creatorCount
      return b.usageCount - a.usageCount
    })
}

function single(value: string | string[] | undefined): string | undefined {
  return Array.isArray(value) ? value[0] : value
}

function isContentScope(value: string | undefined): value is ContentScope {
  return (
    value === "all" ||
    value === "outliers" ||
    value === "audio" ||
    value === "trended" ||
    value === "untrended" ||
    value === "with_views" ||
    value === "missing_views" ||
    value === "pinned" ||
    value === "sponsored" ||
    value === "review"
  )
}

function isContentSort(value: string | undefined): value is ContentSort {
  return (
    value === "copy_priority" ||
    value === "recent" ||
    value === "views" ||
    value === "engagement" ||
    value === "outlier" ||
    value === "trend_usage" ||
    value === "likes" ||
    value === "comments" ||
    value === "shares" ||
    value === "saves" ||
    value === "profile"
  )
}

function isContentPostType(value: string | undefined): value is ContentPostType {
  return (
    value === "all" ||
    value === "reel" ||
    value === "tiktok_video" ||
    value === "image" ||
    value === "carousel"
  )
}

function dateValue(value: string | null): number {
  return value ? new Date(value).getTime() : 0
}

function viewMetric(row: ContentLibraryRow): number | null {
  return row.viewCountAvailable ? row.viewCount : null
}

function sortNullableMetric(a: number | null, b: number | null): number {
  if (a == null && b == null) return 0
  if (a == null) return -1
  if (b == null) return 1
  return a - b
}
