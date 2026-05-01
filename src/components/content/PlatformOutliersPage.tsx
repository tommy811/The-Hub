import Link from "next/link"
import { Badge } from "@/components/ui/badge"
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { EmptyState } from "@/components/ui/empty-state"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { ContentFiltersBar } from "@/components/content/ContentFiltersBar"
import { filterContentRows, parseContentFilters } from "@/lib/content-filtering"
import { getContentLibraryForWorkspace } from "@/lib/db/queries"
import { getCurrentWorkspaceId } from "@/lib/workspace"
import { Sparkles } from "lucide-react"

function compact(n: number): string {
  return new Intl.NumberFormat("en-US", { notation: "compact", compactDisplay: "short" }).format(n)
}

function formatDate(v: string | null): string {
  if (!v) return "-"
  return new Intl.DateTimeFormat("en-US", { month: "short", day: "numeric" }).format(new Date(v))
}

function viewLabel(row: { viewCount: number; viewCountAvailable: boolean }): string {
  return row.viewCountAvailable ? compact(row.viewCount) : "Unavailable"
}

function priorityClass(label: "high" | "strong" | "watch" | "scan"): string {
  if (label === "high") return "bg-emerald-500/15 text-emerald-300"
  if (label === "strong") return "bg-indigo-500/15 text-indigo-300"
  if (label === "watch") return "bg-amber-500/15 text-amber-300"
  return "bg-muted text-muted-foreground"
}

export async function PlatformOutliersPage({
  platform,
  title,
  searchParams,
}: {
  platform: "instagram" | "tiktok"
  title: string
  searchParams: Record<string, string | string[] | undefined>
}) {
  const wsId = await getCurrentWorkspaceId()
  const parsedFilters = parseContentFilters({ ...searchParams, platform })
  const filters = {
    ...parsedFilters,
    platform,
    scope: parsedFilters.scope === "all" ? "outliers" as const : parsedFilters.scope,
    sort: searchParams.sort ? parsedFilters.sort : "outlier" as const,
  }
  const allRows = await getContentLibraryForWorkspace(wsId, {
    platform,
    outliersOnly: true,
    limit: 500,
  })
  const rows = filterContentRows(allRows, filters)
  const top = rows[0]?.outlierMultiplier ?? null
  const trended = rows.filter((row) => row.trendId).length
  const rowsWithViews = rows.filter((row) => row.viewCountAvailable).length
  const highPriority = rows.filter((row) => row.copyPriorityScore >= 70).length

  return (
    <div className="flex flex-col gap-6 pb-10">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">{title} Outliers</h1>
        <p className="text-muted-foreground mt-1 text-sm">
          Posts currently flagged at 3x or more above each profile&apos;s median baseline.
        </p>
      </div>

      <div className="grid gap-4 md:grid-cols-5">
        <Card className="border-border/50">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">Outlier Posts</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{rows.length}</div>
            <p className="mt-1 text-xs text-muted-foreground">of {allRows.length} flagged</p>
          </CardContent>
        </Card>
        <Card className="border-border/50">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">Top Multiplier</CardTitle>
          </CardHeader>
          <CardContent className="text-2xl font-bold">
            {top != null ? `${top.toFixed(1)}x` : "-"}
          </CardContent>
        </Card>
        <Card className="border-border/50">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">Repeat Audio</CardTitle>
          </CardHeader>
          <CardContent className="text-2xl font-bold">
            {trended}
          </CardContent>
        </Card>
        <Card className="border-border/50">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">View Coverage</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{rows.length > 0 ? Math.round((rowsWithViews / rows.length) * 100) : 0}%</div>
            <p className="mt-1 text-xs text-muted-foreground">{rowsWithViews} with view counts</p>
          </CardContent>
        </Card>
        <Card className="border-border/50">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">High Priority</CardTitle>
          </CardHeader>
          <CardContent className="text-2xl font-bold">{highPriority}</CardContent>
        </Card>
      </div>

      <ContentFiltersBar filters={filters} fixedPlatform={platform} outliersOnly />

      {rows.length === 0 ? (
        <EmptyState
          icon={Sparkles}
          title="No outliers yet"
          description="Run the manual scraper on enough recent posts for median baselines to activate."
        />
      ) : (
        <Card className="border-border/50">
          <CardContent className="p-0">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Post</TableHead>
                  <TableHead>Profile</TableHead>
                  <TableHead>Multiplier</TableHead>
                  <TableHead>Audio / Trend</TableHead>
                  <TableHead>Views</TableHead>
                  <TableHead>Priority</TableHead>
                  <TableHead>Engagement</TableHead>
                  <TableHead>Date</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {rows.map((row) => (
                  <TableRow key={row.id}>
                    <TableCell className="max-w-[460px]">
                      {row.postUrl ? (
                        <a
                          href={row.postUrl}
                          target="_blank"
                          rel="noreferrer"
                          className="block truncate font-medium hover:text-indigo-300"
                        >
                          {row.caption || row.postType.replace(/_/g, " ")}
                        </a>
                      ) : (
                        <span className="block truncate font-medium">{row.caption || row.postType}</span>
                      )}
                    </TableCell>
                    <TableCell>
                      <Badge className={priorityClass(row.copyPriorityLabel)}>
                        {row.copyPriorityLabel} {row.copyPriorityScore}
                      </Badge>
                    </TableCell>
                    <TableCell>
                      <div className="flex flex-col">
                        <span className="font-medium">@{row.profileHandle}</span>
                        {row.creatorSlug && (
                          <Link href={`/creators/${row.creatorSlug}`} className="text-xs text-indigo-300 hover:underline">
                            {row.creatorName ?? "Creator"}
                          </Link>
                        )}
                      </div>
                    </TableCell>
                    <TableCell>
                      <Badge className="bg-emerald-500/15 text-emerald-300">
                        {(row.outlierMultiplier ?? 0).toFixed(1)}x
                      </Badge>
                    </TableCell>
                    <TableCell className="max-w-[260px]">
                      <div className="flex min-w-0 flex-col gap-1">
                        <span className="truncate text-sm">
                          {[row.audioArtist, row.audioTitle].filter(Boolean).join(" - ") || row.audioSignature || "-"}
                        </span>
                        {row.trendId ? (
                          <Link
                            href={`/scraped-content?scope=trended&sort=trend_usage&q=${encodeURIComponent(row.audioSignature ?? row.trendName ?? "")}`}
                            className="truncate text-xs text-indigo-300 hover:underline"
                          >
                            {row.trendName ?? "Repeat audio"} ({row.trendUsageCount ?? 0} posts, {row.trendCreatorCount ?? 0} creators)
                          </Link>
                        ) : row.audioSignature ? (
                          <span className="text-xs text-muted-foreground">single-use audio</span>
                        ) : (
                          <span className="text-xs text-muted-foreground">no audio</span>
                        )}
                      </div>
                    </TableCell>
                    <TableCell>
                      {row.viewCountAvailable ? (
                        compact(row.viewCount)
                      ) : (
                        <span className="text-xs text-muted-foreground">{viewLabel(row)}</span>
                      )}
                    </TableCell>
                    <TableCell>
                      {row.engagementRate != null ? `${row.engagementRate.toFixed(1)}%` : "-"}
                    </TableCell>
                    <TableCell>{formatDate(row.postedAt)}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      )}
    </div>
  )
}
