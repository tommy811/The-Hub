"use client";

import { useState } from "react";
import { StatCardRow } from "@/components/accounts/StatCardRow";
import { TrackingTabBar } from "@/components/accounts/TrackingTabBar";
import { RankFilterChips } from "@/components/accounts/RankFilterChips";
import { AccountCard } from "@/components/accounts/AccountCard";
import { AddAccountDialog } from "@/components/accounts/AddAccountDialog";
import { type RankTier } from "@/lib/ranks";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Input } from "@/components/ui/input";
import { Search, SlidersHorizontal } from "lucide-react";

const MOCK_DATA = [
  {
    id: '1', handle: '@viking.barbie', displayName: 'Viking Barbie', avatarUrl: 'https://i.pravatar.cc/300?u=viking',
    rank: 'diamond' as RankTier, score: 92.4, archetype: 'the_rebel', vibe: 'edgy', category: 'comedy_entertainment',
    analysisVersion: 'V2', isClean: true, followers: '1.2M', postCount: '450', medianViews: '350K', outliers: 3, fanArchetype: 'the_admirer'
  },
  {
    id: '2', handle: '@jessica.fit', displayName: 'Jessica Fitness', avatarUrl: 'https://i.pravatar.cc/300?u=jess',
    rank: 'platinum' as RankTier, score: 78.1, archetype: 'the_hero', vibe: 'body_worship', category: 'fitness',
    analysisVersion: 'V2', isClean: true, followers: '850K', postCount: '210', medianViews: '120K', outliers: 0, fanArchetype: 'the_learner'
  },
  {
    id: '3', handle: '@luxury.life', displayName: 'Lux Lifestyle', avatarUrl: 'https://i.pravatar.cc/300?u=lux',
    rank: 'gold' as RankTier, score: 65.0, vibe: 'luxury', category: 'lifestyle',
    analysisVersion: 'V1', isClean: false, followers: '2.5M', postCount: '1.1K', medianViews: '80K', outliers: 1
  },
  {
    id: '4', handle: '@kitchen.hacks', displayName: 'Chef Dave', avatarUrl: 'https://i.pravatar.cc/300?u=chef',
    rank: 'silver' as RankTier, score: 45.5, archetype: 'the_sage', category: 'food',
    analysisVersion: 'V2', isClean: true, followers: '120K', postCount: '80', medianViews: '15K', outliers: 0
  },
  {
    id: '5', handle: '@crypto.bro', displayName: 'Web3 Dave', avatarUrl: 'https://i.pravatar.cc/300?u=web3',
    rank: 'plastic' as RankTier, score: 12.0, archetype: 'the_jester', vibe: 'confident', category: 'education',
    analysisVersion: 'V2', isClean: false, followers: '15K', postCount: '400', medianViews: '2K', outliers: 0
  }
];

export default function InstagramAccountsPage() {
  const [activeTab, setActiveTab] = useState("all");
  const [selectedRanks, setSelectedRanks] = useState<RankTier[]>([]);
  
  const handleRankToggle = (rank: RankTier | 'all') => {
    if (rank === 'all') {
      setSelectedRanks([]);
    } else {
      setSelectedRanks(prev => 
        prev.includes(rank) ? prev.filter(r => r !== rank) : [...prev, rank]
      );
    }
  };

  const rankCounts = { all: 142, diamond: 4, platinum: 18, gold: 45, silver: 40, bronze: 22, plastic: 13 };

  return (
    <div className="flex flex-col gap-8 pb-10">
      
      {/* Header Row */}
      <div className="flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Instagram Accounts</h1>
          <p className="text-muted-foreground mt-1 text-sm">Manage tracking types, ranks, and intelligent routing for IG profiles.</p>
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
              <SelectItem value="recent">Recently Scraped</SelectItem>
            </SelectContent>
          </Select>
        </div>
      </div>

      <StatCardRow />

      <div className="flex flex-col gap-5 mt-2">
        <TrackingTabBar activeTab={activeTab} onTabChange={setActiveTab} />
        <RankFilterChips selectedRanks={selectedRanks} counts={rankCounts} onToggle={handleRankToggle} />
      </div>

      {/* Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6 mt-4">
        {MOCK_DATA.map((account) => (
          <AccountCard key={account.id} platform="instagram" {...account} />
        ))}
      </div>

      <AddAccountDialog />
    </div>
  );
}
