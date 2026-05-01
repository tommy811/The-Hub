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
import { FileVideo } from "lucide-react"

function compact(n: number): string {
  return new Intl.NumberFormat("en-US", { notation: "compact", compactDisplay: "short" }).format(n)
}

function formatDate(v: string | null): string {
  if (!v) return "-"
  return new Intl.DateTimeFormat("en-US", { month: "short", day: "numeric" }).format(new Date(v))
}

function audioLabel(row: { audioArtist: string | null; audioTitle: string | null; audioSignature: string | null }): string {
  const name = [row.audioArtist, row.audioTitle].filter(Boolean).join(" - ")
  return name || row.audioSignature || "-"
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

export async function ScrapedContentLibraryPage({
  searchParams,
}: {
  searchParams: Record<string, string | string[] | undefined>
}) {
  const wsId = await getCurrentWorkspaceId()
  const filters = parseContentFilters(searchParams)
  const allRows = await getContentLibraryForWorkspace(wsId, { limit: 1000 })
  const rows = filterContentRows(allRows, filters)
  const rowsWithViews = rows.filter((row) => row.viewCountAvailable)
  const totalViews = rowsWithViews.reduce((sum, row) => sum + row.viewCount, 0)
  const viewCoverage = rows.length > 0 ? Math.round((rowsWithViews.length / rows.length) * 100) : 0
  const outliers = rows.filter((row) => row.isOutlier).length
  const suspicious = rows.filter((row) => row.qualityFlag === "suspicious").length
  const trended = rows.filter((row) => row.trendId).length
  const highPriority = rows.filter((row) => row.copyPriorityScore >= 70).length

  return (
    <div className="flex flex-col gap-6 pb-10">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">Scraped Content</h1>
        <p className="text-muted-foreground mt-1 text-sm">
          Latest scraped posts across tracked Instagram and TikTok profiles.
        </p>
      </div>

      <div className="grid gap-4 md:grid-cols-3 xl:grid-cols-6">
        <Card className="border-border/50">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">Posts Loaded</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{rows.length}</div>
            <p className="mt-1 text-xs text-muted-foreground">of {allRows.length} loaded</p>
          </CardContent>
        </Card>
        <Card className="border-border/50">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">View Coverage</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{viewCoverage}%</div>
            <p className="mt-1 text-xs text-muted-foreground">{rowsWithViews.length} with view counts</p>
          </CardContent>
        </Card>
        <Card className="border-border/50">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">Known Views</CardTitle>
          </CardHeader>
          <CardContent className="text-2xl font-bold">{compact(totalViews)}</CardContent>
        </Card>
        <Card className="border-border/50">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">Outliers / Review</CardTitle>
          </CardHeader>
          <CardContent className="text-2xl font-bold">
            {outliers}<span className="text-muted-foreground"> / {suspicious}</span>
          </CardContent>
        </Card>
        <Card className="border-border/50">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">Repeat Audio</CardTitle>
          </CardHeader>
          <CardContent className="text-2xl font-bold">{trended}</CardContent>
        </Card>
        <Card className="border-border/50">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">High Priority</CardTitle>
          </CardHeader>
          <CardContent className="text-2xl font-bold">{highPriority}</CardContent>
        </Card>
      </div>

      <ContentFiltersBar filters={filters} />

      {rows.length === 0 ? (
        <EmptyState
          icon={FileVideo}
          title="No scraped content yet"
          description="Run the manual content scraper for a creator or tracking type to populate this view."
        />
      ) : (
        <Card className="border-border/50">
          <CardContent className="p-0">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Post</TableHead>
                  <TableHead>Profile</TableHead>
                  <TableHead>Platform</TableHead>
                  <TableHead>Audio / Trend</TableHead>
                  <TableHead>Views</TableHead>
                  <TableHead>Priority</TableHead>
                  <TableHead>Engagement</TableHead>
                  <TableHead>Flags</TableHead>
                  <TableHead>Date</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {rows.map((row) => (
                  <TableRow key={row.id}>
                    <TableCell className="max-w-[420px]">
                      <div className="flex min-w-0 flex-col gap-1">
                        {row.postUrl ? (
                          <a
                            href={row.postUrl}
                            target="_blank"
                            rel="noreferrer"
                            className="truncate font-medium hover:text-indigo-300"
                          >
                            {row.caption || row.postType.replace(/_/g, " ")}
                          </a>
                        ) : (
                          <span className="truncate font-medium">{row.caption || row.postType}</span>
                        )}
                        <span className="truncate text-xs text-muted-foreground">
                          {row.postType.replace(/_/g, " ")}
                        </span>
                      </div>
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
                    <TableCell className="capitalize">{row.platform}</TableCell>
                    <TableCell className="max-w-[260px]">
                      <div className="flex min-w-0 flex-col gap-1">
                        <span className="truncate text-sm">{audioLabel(row)}</span>
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
                      <Badge className={priorityClass(row.copyPriorityLabel)}>
                        {row.copyPriorityLabel} {row.copyPriorityScore}
                      </Badge>
                    </TableCell>
                    <TableCell>
                      {row.engagementRate != null ? `${row.engagementRate.toFixed(1)}%` : "-"}
                    </TableCell>
                    <TableCell>
                      <div className="flex flex-wrap gap-1">
                        {row.isOutlier && <Badge className="bg-emerald-500/15 text-emerald-300">outlier</Badge>}
                        {row.trendId && <Badge className="bg-indigo-500/15 text-indigo-300">trend</Badge>}
                        {row.isPinned && <Badge variant="outline">pinned</Badge>}
                        {row.isSponsored && <Badge variant="outline">sponsored</Badge>}
                        {row.qualityFlag !== "clean" && (
                          <Badge variant="destructive">{row.qualityFlag}</Badge>
                        )}
                      </div>
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
