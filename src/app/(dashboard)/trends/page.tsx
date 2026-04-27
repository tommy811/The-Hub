export const dynamic = "force-dynamic"

import Link from "next/link"
import { AudioTrendFiltersBar } from "@/components/content/AudioTrendFiltersBar"
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
import { filterAudioTrends, parseAudioTrendFilters } from "@/lib/content-filtering"
import { getAudioTrendsForWorkspace } from "@/lib/db/queries"
import { getCurrentWorkspaceId } from "@/lib/workspace"
import { Activity, Music2 } from "lucide-react"

function formatDate(v: string | null): string {
  if (!v) return "-"
  return new Intl.DateTimeFormat("en-US", { month: "short", day: "numeric" }).format(new Date(v))
}

export default async function TrendsAndAlertsPage({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | string[] | undefined>>
}) {
  const wsId = await getCurrentWorkspaceId()
  const filters = parseAudioTrendFilters(await searchParams)
  const allTrends = await getAudioTrendsForWorkspace(wsId, 500)
  const trends = filterAudioTrends(allTrends, filters)
  const linkedPosts = trends.reduce((sum, trend) => sum + trend.usageCount, 0)

  return (
    <div className="flex flex-col gap-6 pb-10">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">Audio Trends</h1>
        <p className="text-muted-foreground mt-1 text-sm">
          Repeating platform audio detected across scraped Instagram and TikTok content.
        </p>
      </div>

      <div className="grid gap-4 md:grid-cols-3">
        <Card className="border-border/50">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">Repeat Audios</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{trends.length}</div>
            <p className="mt-1 text-xs text-muted-foreground">of {allTrends.length} tracked</p>
          </CardContent>
        </Card>
        <Card className="border-border/50">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">Linked Posts</CardTitle>
          </CardHeader>
          <CardContent className="text-2xl font-bold">{linkedPosts}</CardContent>
        </Card>
        <Card className="border-border/50">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">Top Usage</CardTitle>
          </CardHeader>
          <CardContent className="text-2xl font-bold">
            {trends[0]?.usageCount ?? 0}
          </CardContent>
        </Card>
      </div>

      <AudioTrendFiltersBar filters={filters} />

      {trends.length === 0 ? (
        <EmptyState
          icon={Music2}
          title="No audio trends match"
          description="Adjust the filters or run the audio trend extractor after scraping."
        />
      ) : (
        <Card className="border-border/50">
          <CardContent className="p-0">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Audio</TableHead>
                  <TableHead>Signature</TableHead>
                  <TableHead>Usage</TableHead>
                  <TableHead>Updated</TableHead>
                  <TableHead>Content</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {trends.map((trend) => (
                  <TableRow key={trend.id}>
                    <TableCell className="max-w-[420px]">
                      <div className="flex min-w-0 flex-col gap-1">
                        <span className="truncate font-medium">{trend.name}</span>
                        <span className="truncate text-xs text-muted-foreground">
                          {[trend.audioArtist, trend.audioTitle].filter(Boolean).join(" - ") || "Platform audio"}
                        </span>
                      </div>
                    </TableCell>
                    <TableCell className="font-mono text-xs text-muted-foreground">
                      {trend.audioSignature ?? "-"}
                    </TableCell>
                    <TableCell>{trend.usageCount}</TableCell>
                    <TableCell>{formatDate(trend.updatedAt ?? trend.createdAt)}</TableCell>
                    <TableCell>
                      <Link
                        href={`/scraped-content?scope=trended&sort=trend_usage&q=${encodeURIComponent(trend.audioSignature ?? trend.name)}`}
                        className="inline-flex items-center gap-1 text-sm font-medium text-indigo-300 hover:underline"
                      >
                        <Activity className="h-3.5 w-3.5" />
                        View posts
                      </Link>
                    </TableCell>
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
