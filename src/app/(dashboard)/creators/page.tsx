// src/app/(dashboard)/creators/page.tsx — Creators Hub page
export const dynamic = 'force-dynamic';

import { Users2, Search } from "lucide-react";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { MergeAlertBanner } from "@/components/creators/MergeAlertBanner";
import { CreatorCard } from "@/components/creators/CreatorCard";
import { BulkImportDialog } from "@/components/creators/BulkImportDialog";
import { createServiceClient } from "@/lib/supabase/server";
import { CreatorsFilters } from "@/components/creators/CreatorsFilters";

function relativeTime(dateStr: string | null | undefined): string {
  if (!dateStr) return "—";
  const diff = Date.now() - new Date(dateStr).getTime();
  const minutes = Math.floor(diff / 60000);
  if (minutes < 1) return "just now";
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  return `${days}d ago`;
}

function formatFollowers(n: number): string {
  if (n === 0) return "—";
  return new Intl.NumberFormat('en-US', { notation: "compact", compactDisplay: "short" }).format(n);
}

export default async function CreatorsHubPage({ searchParams }: { searchParams: { status?: string, tracking?: string } }) {
  const supabase = createServiceClient();
  const activeStatus = searchParams?.status || "all";
  const activeTracking = searchParams?.tracking || "all";

  const { data: ws } = await supabase.from('workspaces').select('id').limit(1).single();
  const wsId = ws?.id;

  let query = supabase.from('creators').select(`
    *,
    profiles!creator_id(id, avatar_url, platform, account_type, follower_count, is_primary, handle, display_name, discovery_confidence)
  `).eq('workspace_id', wsId);

  if (activeStatus !== "all") query = query.eq('onboarding_status', activeStatus);
  if (activeTracking !== "all") query = query.eq('tracking_type', activeTracking);

  const [creatorsResult, statsResult, mergeCountResult, mergeCandidatesResult] = await Promise.all([
    query.order('created_at', { ascending: false }),
    supabase.from('creators').select('onboarding_status, tracking_type').eq('workspace_id', wsId),
    supabase.from('creator_merge_candidates').select('*', { count: 'exact', head: true }).eq('workspace_id', wsId).eq('status', 'pending'),
    supabase.from('creator_merge_candidates').select('creator_a_id, creator_b_id').eq('workspace_id', wsId).eq('status', 'pending'),
  ]);

  const rawCreators = creatorsResult.data;
  const allStats = statsResult.data;
  const mergeCount = mergeCountResult.count || 0;
  const mergeCandidates = mergeCandidatesResult.data || [];

  const counts = {
    all: allStats?.length || 0,
    processing: allStats?.filter(c => c.onboarding_status === 'processing').length || 0,
    ready: allStats?.filter(c => c.onboarding_status === 'ready').length || 0,
    failed: allStats?.filter(c => c.onboarding_status === 'failed').length || 0,
    archived: allStats?.filter(c => c.onboarding_status === 'archived').length || 0,
  };

  const trackingCounts = {
    all: allStats?.length || 0,
    managed: allStats?.filter(c => c.tracking_type === 'managed').length || 0,
    inspiration: allStats?.filter(c => c.tracking_type === 'inspiration').length || 0,
    competitor: allStats?.filter(c => c.tracking_type === 'competitor').length || 0,
    candidate: allStats?.filter(c => c.tracking_type === 'candidate').length || 0,
    hybrid_ai: allStats?.filter(c => c.tracking_type === 'hybrid_ai').length || 0,
    coach: allStats?.filter(c => c.tracking_type === 'coach').length || 0,
    unreviewed: allStats?.filter(c => c.tracking_type === 'unreviewed').length || 0,
  };

  const creatorIdsWithMerge = new Set([
    ...mergeCandidates.map(m => m.creator_a_id),
    ...mergeCandidates.map(m => m.creator_b_id),
  ]);

  const creators = (rawCreators || []).map(c => {
    const profiles: any[] = Array.isArray(c.profiles) ? c.profiles : [];
    const primaryProfile = profiles.find(p => p.is_primary) ?? profiles[0];
    const socialProfiles = profiles.filter(p => p.account_type === 'social');
    const totalFollowerCount = socialProfiles.reduce((sum, p) => sum + (p.follower_count || 0), 0);

    const accountCounts: Record<string, number> = {};
    for (const p of profiles) {
      accountCounts[p.account_type] = (accountCounts[p.account_type] || 0) + 1;
    }

    return {
      id: c.id,
      canonicalName: c.canonical_name,
      slug: c.slug,
      avatarUrl: primaryProfile?.avatar_url ?? undefined,
      primaryPlatform: c.primary_platform || 'other',
      status: c.onboarding_status as 'processing' | 'ready' | 'failed' | 'archived',
      trackingType: c.tracking_type,
      monetizationModel: c.monetization_model,
      tags: c.tags || [],
      knownUsernames: c.known_usernames || [],
      accountCounts,
      totalFollowers: formatFollowers(totalFollowerCount),
      updatedAgo: relativeTime(c.updated_at),
      hasMergeCandidate: creatorIdsWithMerge.has(c.id),
      errorMessage: c.last_discovery_error,
    };
  });

  return (
    <div className="flex flex-col gap-6 pb-10">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold tracking-tight flex items-center gap-2">
            <Users2 className="h-8 w-8 text-indigo-400" /> Creators
          </h1>
          <p className="text-muted-foreground mt-1 text-sm">Discover and map entire creator network footprints.</p>
        </div>
        <div className="flex items-center gap-3">
          <div className="relative">
            <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
            <Input placeholder="Search creators..." className="pl-9 w-[250px] bg-background/50 border-border/50 focus-visible:ring-indigo-500 rounded-lg" />
          </div>
          <Select defaultValue="recently_added">
            <SelectTrigger className="w-[180px] bg-background/50 border-border/50 rounded-lg">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="recently_added">Recently Added</SelectItem>
              <SelectItem value="name_asc">Name (A-Z)</SelectItem>
              <SelectItem value="platform">Primary Platform</SelectItem>
            </SelectContent>
          </Select>
          <BulkImportDialog />
        </div>
      </div>

      <MergeAlertBanner count={mergeCount} />

      <CreatorsFilters counts={counts} trackingCounts={trackingCounts} activeStatus={activeStatus} activeTracking={activeTracking} />

      {creators.length > 0 ? (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6">
          {creators.map(creator => (
            <CreatorCard key={creator.id} {...creator} />
          ))}
        </div>
      ) : (
        <div className="flex flex-col items-center justify-center p-20 text-center border border-dashed border-border/50 rounded-xl bg-muted/10 mt-8">
          <Users2 className="h-16 w-16 text-muted-foreground/30 mb-4" />
          <h3 className="text-xl font-bold">Import your first creators</h3>
          <p className="text-muted-foreground mt-2 max-w-md">Our AI will automatically scan their primary profile, follow link-in-bio traces, and build out their entire cross-platform network footprint.</p>
          <div className="mt-6"><BulkImportDialog /></div>
        </div>
      )}
    </div>
  );
}
