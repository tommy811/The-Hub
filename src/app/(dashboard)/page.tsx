export const dynamic = "force-dynamic"

import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Activity, Sparkles, TrendingUp, Users, Video, Search } from "lucide-react"
import Link from "next/link"
import { getCurrentWorkspaceId } from "@/lib/workspace"
import {
  getCommandCenterStats,
  getRecentOutliersForWorkspace,
  getActiveTrendSignalsForWorkspace,
} from "@/lib/db/queries"
import { EmptyState } from "@/components/ui/empty-state"

export default async function CommandCenter() {
  const wsId = await getCurrentWorkspaceId()
  const [stats, outliers, signals] = await Promise.all([
    getCommandCenterStats(wsId),
    getRecentOutliersForWorkspace(wsId, 5),
    getActiveTrendSignalsForWorkspace(wsId, 5),
  ])

  return (
    <div className="flex flex-col gap-8 pb-10">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">Command Center</h1>
        <p className="text-muted-foreground mt-1 text-sm">
          Your daily overview of agency performance and ingestion status.
        </p>
      </div>

      {/* Stats Row */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        <Link href="/creators">
          <Card className="bg-card shadow-sm border-border/50 hover:bg-muted/50 transition-colors cursor-pointer h-full">
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">Tracked Creators</CardTitle>
              <Users className="h-4 w-4 text-indigo-500" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{stats.creatorCount}</div>
              <p className="text-xs text-muted-foreground mt-1">
                Cross-platform profiles managed
              </p>
            </CardContent>
          </Card>
        </Link>

        <Link href="/content">
          <Card className="bg-card shadow-sm border-border/50 hover:bg-muted/50 transition-colors cursor-pointer h-full">
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">Posts Ingested</CardTitle>
              <Video className="h-4 w-4 text-emerald-500" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{stats.postCount}</div>
              <p className="text-xs text-muted-foreground mt-1">
                Total posts in workspace
              </p>
            </CardContent>
          </Card>
        </Link>

        <Card className="bg-card shadow-sm border-border/50">
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Avg Quality Score</CardTitle>
            <Sparkles className="h-4 w-4 text-amber-500" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {stats.avgQualityScore !== null ? stats.avgQualityScore : "—"}
            </div>
            <p className="text-xs text-muted-foreground mt-1">
              {stats.avgQualityScore !== null
                ? "Across scored profiles"
                : "No scores yet"}
            </p>
          </CardContent>
        </Card>

        <Link href="/creators?status=processing">
          <Card className="bg-card shadow-sm border-border/50 hover:bg-muted/50 transition-colors cursor-pointer h-full">
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">Discovery Queue</CardTitle>
              <Search className="h-4 w-4 text-sky-500" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{stats.pendingDiscoveryCount}</div>
              <p className="text-xs text-muted-foreground mt-1">
                Pending AI resolution
              </p>
            </CardContent>
          </Card>
        </Link>
      </div>

      {/* Main Content Area */}
      <div className="grid gap-6 md:grid-cols-2">
        {/* Outliers Feed */}
        <Card className="col-span-1 shadow-sm border-border/50">
          <CardHeader>
            <CardTitle className="text-lg">Recent Outliers</CardTitle>
            <CardDescription>
              Posts performing &gt;3× above their median average.
            </CardDescription>
          </CardHeader>
          <CardContent className="flex flex-col gap-4">
            {outliers.length === 0 ? (
              <EmptyState
                icon={Sparkles}
                title="No outliers yet"
                description="Phase 2 will populate this once scraping is live."
              />
            ) : (
              outliers.map((o, i) => (
                <OutlierItem
                  key={i}
                  handle={"@" + o.profileHandle}
                  multiplier={o.outlierMultiplier ?? 0}
                  views={o.viewCount}
                  url={o.postUrl ?? undefined}
                />
              ))
            )}
          </CardContent>
        </Card>

        {/* Top Trend Signals */}
        <Card className="col-span-1 shadow-sm border-border/50 relative overflow-hidden">
          <div className="absolute top-0 right-0 p-32 bg-indigo-500/10 blur-[100px] rounded-full pointer-events-none" />
          <CardHeader>
            <CardTitle className="text-lg flex items-center gap-2">
              <TrendingUp className="w-5 h-5 text-indigo-400" /> Top Trend Signals
            </CardTitle>
            <CardDescription>
              Realtime aggregate velocity across tracked accounts.
            </CardDescription>
          </CardHeader>
          <CardContent className="flex flex-col gap-4 relative z-10">
            {signals.length === 0 ? (
              <EmptyState
                icon={Activity}
                title="No active signals"
                description="Phase 2–3 will populate this when trend detection is live."
              />
            ) : (
              signals.map((s, i) => (
                <TrendItem
                  key={i}
                  type={s.signalType}
                  label={(s.metadata.label as string) ?? formatLabel(s.signalType)}
                  context={(s.metadata.context as string) ?? "—"}
                />
              ))
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  )
}

function formatLabel(t: string): string {
  return t.split("_").map((w) => w[0].toUpperCase() + w.slice(1)).join(" ")
}

function compact(n: number): string {
  return new Intl.NumberFormat("en-US", { notation: "compact", compactDisplay: "short" }).format(n)
}

function OutlierItem({
  handle,
  multiplier,
  views,
  url,
}: {
  handle: string
  multiplier: number
  views: number
  url?: string
}) {
  const inner = (
    <div className="flex items-center justify-between p-3 rounded-lg bg-muted/40 border border-border/50">
      <div className="flex flex-col">
        <span className="font-semibold text-sm">{handle}</span>
        <span className="text-[10px] uppercase text-emerald-500 font-bold tracking-wider">
          {multiplier.toFixed(1)}× above median
        </span>
      </div>
      <span className="font-bold text-amber-500">{compact(views)} views</span>
    </div>
  )
  return url ? (
    <a href={url} target="_blank" rel="noreferrer">
      {inner}
    </a>
  ) : (
    inner
  )
}

function TrendItem({
  type,
  label,
  context,
}: {
  type: string
  label: string
  context: string
}) {
  return (
    <div className="flex items-center gap-4 p-3 rounded-lg border border-border/50 bg-background/50">
      <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-indigo-500/10 text-indigo-400">
        <Activity className="h-5 w-5" />
      </div>
      <div className="flex flex-col flex-1">
        <span className="font-semibold text-sm">{label}</span>
        <span className="text-xs text-muted-foreground">{context}</span>
      </div>
      <Badge
        variant="outline"
        className="text-[10px] uppercase border-indigo-500/30 text-indigo-400"
      >
        {type.replace(/_/g, " ")}
      </Badge>
    </div>
  )
}
