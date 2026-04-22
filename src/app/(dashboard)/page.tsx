export const dynamic = 'force-dynamic';

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Activity, Sparkles, TrendingUp, Users, Video, Search } from "lucide-react";
import { createServiceClient } from "@/lib/supabase/server";
import Link from "next/link";

export default async function CommandCenter() {
  const supabase = createServiceClient();
  
  // Enforce workspace
  const { data: ws } = await supabase.from('workspaces').select('id').limit(1).single();
  const wsId = ws?.id;

  // Real data queries
  const { count: creatorCount } = await supabase.from('creators').select('*', { count: 'exact', head: true }).eq('workspace_id', wsId);
  const { count: postCount } = await supabase.from('scraped_content').select('*', { count: 'exact', head: true });
  
  // Pending discovery pipeline
  const { count: pendingQueue } = await supabase.from('discovery_runs')
    .select('*', { count: 'exact', head: true })
    .eq('workspace_id', wsId)
    .in('status', ['pending', 'processing']);

  return (
    <div className="flex flex-col gap-8 pb-10">
      
      <div>
        <h1 className="text-3xl font-bold tracking-tight">Command Center</h1>
        <p className="text-muted-foreground mt-1 text-sm">Your daily overview of agency performance and ingestion status.</p>
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
              <div className="text-2xl font-bold">{creatorCount || 0}</div>
              <p className="text-xs text-muted-foreground mt-1">Cross-platform profiles managed</p>
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
              <div className="text-2xl font-bold">{postCount || 0}</div>
              <p className="text-xs text-muted-foreground mt-1">Total posts in database</p>
            </CardContent>
          </Card>
        </Link>
        
        <Card className="bg-card shadow-sm border-border/50">
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Avg Quality Score</CardTitle>
            <Sparkles className="h-4 w-4 text-amber-500" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">--</div>
            <p className="text-xs text-muted-foreground mt-1">LLM scoring running in bg</p>
          </CardContent>
        </Card>
        
        <Link href="/creators?status=processing">
          <Card className="bg-card shadow-sm border-border/50 hover:bg-muted/50 transition-colors cursor-pointer h-full">
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">Discovery Queue</CardTitle>
              <Search className="h-4 w-4 text-sky-500" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{pendingQueue || 0}</div>
              <p className="text-xs text-muted-foreground mt-1">Pending AI resolution</p>
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
            <CardDescription>Posts performing &gt;3× above their median average.</CardDescription>
          </CardHeader>
          <CardContent className="flex flex-col gap-4">
            <OutlierItem handle="@viking.barbie" score="94.2" median="350K" views="1.2M" />
            <OutlierItem handle="@jessica.fit" score="81.0" median="120K" views="450K" />
            <OutlierItem handle="@luxury.life" score="65.4" median="80K" views="220K" />
          </CardContent>
        </Card>

        {/* Top Trends */}
        <Card className="col-span-1 shadow-sm border-border/50 relative overflow-hidden">
          <div className="absolute top-0 right-0 p-32 bg-indigo-500/10 blur-[100px] rounded-full point-events-none" />
          
          <CardHeader>
             <CardTitle className="text-lg flex items-center gap-2">
               <TrendingUp className="w-5 h-5 text-indigo-400" /> Top Trend Signals
             </CardTitle>
             <CardDescription>Realtime aggregate velocity across tracked accounts.</CardDescription>
          </CardHeader>
          <CardContent className="flex flex-col gap-4 relative z-10">
             <TrendItem type="outlier_post" label="Multiple Outliers" context="Comedy / Entertainment" />
             <TrendItem type="velocity_spike" label="Velocity Spike" context="Fitness" />
             <TrendItem type="hook_pattern" label="Emerging Hook" context="POV: You finally..." />
          </CardContent>
        </Card>

      </div>
    </div>
  );
}

function UsersIcon(props: any) {
  return (
    <svg {...props} xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M22 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></svg>
  );
}

function VideoIcon(props: any) {
  return (
    <svg {...props} xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="m22 8-6 4 6 4V8Z"/><rect width="14" height="12" x="2" y="6" rx="2" ry="2"/></svg>
  );
}

function OutlierItem({ handle, score, median, views }: { handle: string; score: string; median: string; views: string }) {
  return (
    <div className="flex items-center justify-between p-3 rounded-lg bg-muted/40 border border-border/50">
      <div className="flex items-center gap-3">
        <div className="w-10 h-10 rounded-full bg-muted border overflow-hidden">
          <img src={`https://i.pravatar.cc/150?u=${handle}`} alt="" className="w-full h-full object-cover" />
        </div>
        <div className="flex flex-col">
          <span className="font-semibold text-sm">{handle}</span>
          <span className="text-[10px] uppercase text-emerald-500 font-bold tracking-wider">Score {score}</span>
        </div>
      </div>
      <div className="flex flex-col items-end">
        <span className="font-bold text-amber-500">{views} Views</span>
        <span className="text-[10px] text-muted-foreground uppercase font-semibold">Median: {median}</span>
      </div>
    </div>
  );
}

function TrendItem({ type, label, context }: { type: string; label: string; context: string }) {
  return (
    <div className="flex items-center gap-4 p-3 rounded-lg border border-border/50 bg-background/50">
      <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-indigo-500/10 text-indigo-400">
        <Activity className="h-5 w-5" />
      </div>
      <div className="flex flex-col flex-1">
        <span className="font-semibold text-sm">{label}</span>
        <span className="text-xs text-muted-foreground">{context}</span>
      </div>
      <Badge variant="outline" className="text-[10px] uppercase border-indigo-500/30 text-indigo-400">
        {type.replace('_', ' ')}
      </Badge>
    </div>
  )
}
