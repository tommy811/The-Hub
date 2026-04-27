import type { AudioTrendRow, ContentLibraryRow } from "@/lib/db/queries"

export type ContentScope = "all" | "outliers" | "audio" | "trended" | "untrended" | "review"
export type ContentSort = "recent" | "views" | "engagement" | "outlier" | "trend_usage" | "profile"

export type ContentFilters = {
  q: string
  platform: "all" | "instagram" | "tiktok"
  scope: ContentScope
  sort: ContentSort
  minMultiplier: number | null
}

export type AudioTrendFilters = {
  q: string
  sort: "usage" | "name" | "recent"
  minUsage: number
}

export function parseContentFilters(input: Record<string, string | string[] | undefined>): ContentFilters {
  const platform = single(input.platform)
  const scope = single(input.scope)
  const sort = single(input.sort)
  const min = Number(single(input.min) ?? "")

  return {
    q: single(input.q)?.trim() ?? "",
    platform: platform === "instagram" || platform === "tiktok" ? platform : "all",
    scope: isContentScope(scope) ? scope : "all",
    sort: isContentSort(sort) ? sort : "recent",
    minMultiplier: Number.isFinite(min) && min > 0 ? min : null,
  }
}

export function parseAudioTrendFilters(input: Record<string, string | string[] | undefined>): AudioTrendFilters {
  const sort = single(input.sort)
  const min = Number(single(input.minUsage) ?? "")

  return {
    q: single(input.q)?.trim() ?? "",
    sort: sort === "name" || sort === "recent" ? sort : "usage",
    minUsage: Number.isFinite(min) && min > 0 ? min : 2,
  }
}

export function filterContentRows(rows: ContentLibraryRow[], filters: ContentFilters): ContentLibraryRow[] {
  const q = filters.q.toLowerCase()
  return sortContentRows(
    rows.filter((row) => {
      if (filters.platform !== "all" && row.platform !== filters.platform) return false
      if (filters.minMultiplier != null && (row.outlierMultiplier ?? 0) < filters.minMultiplier) return false
      if (filters.scope === "outliers" && !row.isOutlier) return false
      if (filters.scope === "audio" && !row.audioSignature) return false
      if (filters.scope === "trended" && !row.trendId) return false
      if (filters.scope === "untrended" && row.trendId) return false
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
    if (sort === "views") return b.viewCount - a.viewCount
    if (sort === "engagement") return (b.engagementRate ?? -1) - (a.engagementRate ?? -1)
    if (sort === "outlier") return (b.outlierMultiplier ?? -1) - (a.outlierMultiplier ?? -1)
    if (sort === "trend_usage") return (b.trendUsageCount ?? -1) - (a.trendUsageCount ?? -1)
    if (sort === "profile") return a.profileHandle.localeCompare(b.profileHandle)
    return dateValue(b.postedAt) - dateValue(a.postedAt)
  })
}

export function filterAudioTrends(rows: AudioTrendRow[], filters: AudioTrendFilters): AudioTrendRow[] {
  const q = filters.q.toLowerCase()
  return [...rows]
    .filter((row) => {
      if (row.usageCount < filters.minUsage) return false
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
      return b.usageCount - a.usageCount
    })
}

function single(value: string | string[] | undefined): string | undefined {
  return Array.isArray(value) ? value[0] : value
}

function isContentScope(value: string | undefined): value is ContentScope {
  return value === "all" || value === "outliers" || value === "audio" || value === "trended" || value === "untrended" || value === "review"
}

function isContentSort(value: string | undefined): value is ContentSort {
  return value === "recent" || value === "views" || value === "engagement" || value === "outlier" || value === "trend_usage" || value === "profile"
}

function dateValue(value: string | null): number {
  return value ? new Date(value).getTime() : 0
}
