"use client";

// TikTok accounts page — still mock data; wiring to live Supabase is a future session.
// Matches the same shell as Instagram but with placeholder values until the pipeline runs.

import { useState } from "react";
import { StatCardRow } from "@/components/accounts/StatCardRow";
import { TrackingTabBar } from "@/components/accounts/TrackingTabBar";
import { RankFilterChips } from "@/components/accounts/RankFilterChips";
import { AccountCard } from "@/components/accounts/AccountCard";
import { type RankTier } from "@/lib/ranks";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Input } from "@/components/ui/input";
import { Search, SlidersHorizontal } from "lucide-react";

export default function TikTokAccountsPage() {
  const [activeTab, setActiveTab] = useState("all");
  const [selectedRanks, setSelectedRanks] = useState<RankTier[]>([]);

  const handleRankToggle = (rank: RankTier | "all") => {
    if (rank === "all") setSelectedRanks([]);
    else setSelectedRanks((prev) =>
      prev.includes(rank) ? prev.filter((r) => r !== rank) : [...prev, rank]
    );
  };

  const rankCounts = { all: 1, diamond: 1, platinum: 0, gold: 0, silver: 0, bronze: 0, plastic: 0 };

  return (
    <div className="flex flex-col gap-8 pb-10">
      <div className="flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">TikTok Accounts</h1>
          <p className="text-muted-foreground mt-1 text-sm">
            Manage tracking types, ranks, and intelligent routing for TikTok profiles.
          </p>
        </div>
        <div className="flex items-center gap-3">
          <div className="relative w-64">
            <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
            <Input type="search" placeholder="Filter handles..." className="pl-9 bg-card border-border/50" />
          </div>
          <Select defaultValue="quality">
            <SelectTrigger className="w-[180px] bg-card border-border/50">
              <SlidersHorizontal className="w-4 h-4 mr-2" />
              <SelectValue placeholder="Sort by" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="quality">Quality Score</SelectItem>
              <SelectItem value="followers">Followers</SelectItem>
              <SelectItem value="outliers">Outlier Count</SelectItem>
            </SelectContent>
          </Select>
        </div>
      </div>

      <StatCardRow total={1} withContent={1} avgFollowers="21M" llmScored={1} />

      <div className="flex flex-col gap-5 mt-2">
        <TrackingTabBar activeTab={activeTab} onTabChange={setActiveTab} />
        <RankFilterChips selectedRanks={selectedRanks} counts={rankCounts} onToggle={handleRankToggle} />
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6 mt-4">
        <AccountCard
          platform="tiktok"
          handle="@hype.house"
          displayName="Hype House"
          avatarUrl="https://i.pravatar.cc/300?u=hype"
          rank="diamond"
          score={88.2}
          analysisVersion="V2"
          isClean={true}
          followers="21M"
          postCount="1.2K"
          medianViews="2M"
          outliers={5}
        />
      </div>
    </div>
  );
}
