// src/app/(dashboard)/creators/page.tsx — Creators Hub page
"use client";

import { useState } from "react";
import { Plus, Users2, Search } from "lucide-react";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { MergeAlertBanner } from "@/components/creators/MergeAlertBanner";
import { StatusTabBar } from "@/components/creators/StatusTabBar";
import { CreatorCard } from "@/components/creators/CreatorCard";
import { BulkImportDialog } from "@/components/creators/BulkImportDialog";
import { TrackingTabBar } from "@/components/accounts/TrackingTabBar";

// Mock data until Supabase realtime is hooked up
const MOCK_CREATORS = [
  {
    id: "1",
    canonicalName: "Sunny Rose",
    slug: "sunnyrose",
    avatarUrl: "https://i.pravatar.cc/300?u=sunnyrose",
    primaryPlatform: "instagram",
    status: 'ready' as const,
    trackingType: "managed",
    monetizationModel: "subscription",
    tags: ["top_tier", "fitness"],
    knownUsernames: ["@sunnyrose.ig", "@sunny.tv", "of:sunnyrose"],
    accountCounts: { social: 3, monetization: 2, link_in_bio: 1 },
    totalFollowers: "4.2M",
    updatedAgo: "2H AGO",
    hasMergeCandidate: true
  },
  {
    id: "2",
    canonicalName: "Viking Barbie",
    slug: "vikingbarbie",
    primaryPlatform: "tiktok",
    status: 'processing' as const,
    trackingType: "competitor",
    tags: ["model"],
    accountCounts: {} as Record<string, number>,
    totalFollowers: "0",
    updatedAgo: "JUST NOW",
    hasMergeCandidate: false
  },
  {
    id: "3",
    canonicalName: "Dark Knight",
    slug: "darkknight",
    primaryPlatform: "youtube",
    status: 'failed' as const,
    trackingType: "candidate",
    tags: ["gaming"],
    accountCounts: {} as Record<string, number>,
    totalFollowers: "0",
    updatedAgo: "1D AGO",
    hasMergeCandidate: false,
    errorMessage: "Could not resolve bio link domain target."
  }
];

export default function CreatorsHubPage() {
  const [activeStatus, setActiveStatus] = useState("all");
  const [trackingType, setTrackingType] = useState("all");
  
  // Realtime count mock
  const counts = {
    all: 124,
    processing: 1,
    ready: 115,
    failed: 1,
    archived: 7
  };

  const mergeCandidatesCount = 1;

  return (
    <div className="flex flex-col gap-6 pb-10">
      {/* Header Row */}
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

      <MergeAlertBanner count={mergeCandidatesCount} onReview={() => {}} onDismiss={() => {}} />

      {/* Filters */}
      <div className="flex flex-col xl:flex-row xl:items-center justify-between gap-4">
        <StatusTabBar counts={counts} activeStatus={activeStatus} onStatusChange={setActiveStatus} />
        
        {/* We reuse the generic TrackingTabBar from the accounts hub, though adapted for chips if needed. 
            For now, the existing TrackingTabBar looks good as a secondary filter. */}
        <TrackingTabBar onTabChange={setTrackingType} activeTab={trackingType} />
      </div>

      {/* Grid */}
      {MOCK_CREATORS.length > 0 ? (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6">
          {MOCK_CREATORS.map(creator => (
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
