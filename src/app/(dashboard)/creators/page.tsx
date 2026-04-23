// src/app/(dashboard)/creators/page.tsx
export const dynamic = "force-dynamic"

import { Users2 } from "lucide-react"
import { MergeAlertBanner } from "@/components/creators/MergeAlertBanner"
import { CreatorCard } from "@/components/creators/CreatorCard"
import { BulkImportDialog } from "@/components/creators/BulkImportDialog"
import { CreatorsFilters } from "@/components/creators/CreatorsFilters"
import { CreatorsSearchSort } from "@/components/creators/CreatorsSearchSort"
import { EmptyState } from "@/components/ui/empty-state"
import { getCurrentWorkspaceId } from "@/lib/workspace"
import {
  getCreatorsForWorkspace,
  getCreatorStatsForWorkspace,
  getMergeCandidatesForWorkspace,
} from "@/lib/db/queries"
import type { Enums } from "@/types/db"

function relativeTime(dateStr: string | null | undefined): string {
  if (!dateStr) return "—"
  const diff = Date.now() - new Date(dateStr).getTime()
  const minutes = Math.floor(diff / 60000)
  if (minutes < 1) return "just now"
  if (minutes < 60) return `${minutes}m ago`
  const hours = Math.floor(minutes / 60)
  if (hours < 24) return `${hours}h ago`
  const days = Math.floor(hours / 24)
  return `${days}d ago`
}

function formatFollowers(n: number): string {
  if (n === 0) return "—"
  return new Intl.NumberFormat("en-US", { notation: "compact", compactDisplay: "short" }).format(n)
}

type SortKey = "recently_added" | "name_asc" | "platform"

export default async function CreatorsHubPage({
  searchParams,
}: {
  searchParams: { status?: string; tracking?: string; q?: string; sort?: string }
}) {
  const wsId = await getCurrentWorkspaceId()
  const status = (searchParams?.status ?? "all") as Enums<"onboarding_status"> | "all"
  const tracking = (searchParams?.tracking ?? "all") as Enums<"tracking_type"> | "all"
  const q = searchParams?.q ?? ""
  const sort = (searchParams?.sort ?? "recently_added") as SortKey

  const [rawCreators, stats, mergeCandidates] = await Promise.all([
    getCreatorsForWorkspace(wsId, { status, tracking, q, sort }),
    getCreatorStatsForWorkspace(wsId),
    getMergeCandidatesForWorkspace(wsId),
  ])

  const mergeCount = mergeCandidates.length
  const creatorIdsWithMerge = new Set(
    mergeCandidates.flatMap((m) => [m.creator_a_id, m.creator_b_id])
  )

  const creators = rawCreators.map((c) => {
    const profiles = c.profiles ?? []
    const primaryProfile = profiles.find((p) => p.is_primary) ?? profiles[0]
    const socialProfiles = profiles.filter((p) => p.account_type === "social")
    const totalFollowerCount = socialProfiles.reduce(
      (sum, p) => sum + (Number(p.follower_count) || 0),
      0
    )
    const accountCounts: Record<string, number> = {}
    for (const p of profiles) {
      const at = p.account_type ?? "other"
      accountCounts[at] = (accountCounts[at] ?? 0) + 1
    }
    return {
      id: c.id,
      canonicalName: c.canonical_name,
      slug: c.slug,
      avatarUrl: primaryProfile?.avatar_url ?? undefined,
      primaryPlatform: c.primary_platform || "other",
      status: c.onboarding_status as "processing" | "ready" | "failed" | "archived",
      trackingType: c.tracking_type ?? "unreviewed",
      monetizationModel: c.monetization_model ?? undefined,
      tags: c.tags || [],
      knownUsernames: c.known_usernames || [],
      accountCounts,
      totalFollowers: formatFollowers(totalFollowerCount),
      updatedAgo: relativeTime(c.updated_at),
      hasMergeCandidate: creatorIdsWithMerge.has(c.id),
      errorMessage: c.last_discovery_error ?? undefined,
    }
  })

  return (
    <div className="flex flex-col gap-6 pb-10">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold tracking-tight flex items-center gap-2">
            <Users2 className="h-8 w-8 text-indigo-400" /> Creators
          </h1>
          <p className="text-muted-foreground mt-1 text-sm">
            Discover and map entire creator network footprints.
          </p>
        </div>
        <div className="flex items-center gap-3">
          <CreatorsSearchSort initialQ={q} initialSort={sort} />
          <BulkImportDialog />
        </div>
      </div>

      <MergeAlertBanner count={mergeCount} />

      <CreatorsFilters
        counts={stats.byStatus}
        trackingCounts={stats.byTracking}
        activeStatus={status}
        activeTracking={tracking}
      />

      {creators.length > 0 ? (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6">
          {creators.map((creator) => (
            <CreatorCard key={creator.id} {...creator} />
          ))}
        </div>
      ) : q || status !== "all" || tracking !== "all" ? (
        <EmptyState
          icon={Users2}
          title="No creators match those filters"
          description="Adjust the filters or clear the search to see more."
        />
      ) : (
        <EmptyState
          icon={Users2}
          title="Import your first creators"
          description="Our AI will scan their primary profile, follow link-in-bio traces, and build out their full cross-platform network footprint."
          action={<BulkImportDialog />}
        />
      )}
    </div>
  )
}
