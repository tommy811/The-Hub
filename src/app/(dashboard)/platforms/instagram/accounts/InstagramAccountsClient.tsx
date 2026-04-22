"use client";

import { useState, useMemo } from "react";
import { useRouter, usePathname, useSearchParams } from "next/navigation";
import { StatCardRow } from "@/components/accounts/StatCardRow";
import { TrackingTabBar } from "@/components/accounts/TrackingTabBar";
import { RankFilterChips } from "@/components/accounts/RankFilterChips";
import { AccountCard } from "@/components/accounts/AccountCard";
import { type RankTier } from "@/lib/ranks";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Input } from "@/components/ui/input";
import { Search, SlidersHorizontal, Camera } from "lucide-react";
import Link from "next/link";
import type { AccountRowData } from "./page";

function formatNumber(n: number | null | undefined): string {
  if (n == null) return "—";
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${Math.round(n / 1_000)}K`;
  return n.toLocaleString();
}

type SortKey = "quality" | "followers" | "outliers";

interface Props {
  accounts: AccountRowData[];
  activeType: string;
}

export function InstagramAccountsClient({ accounts }: Props) {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();

  const activeTab = searchParams.get("type") ?? "all";

  const [selectedRanks, setSelectedRanks] = useState<RankTier[]>([]);
  const [sortKey, setSortKey] = useState<SortKey>("quality");
  const [search, setSearch] = useState("");

  const handleTabChange = (tab: string) => {
    const params = new URLSearchParams(searchParams.toString());
    if (tab === "all") params.delete("type");
    else params.set("type", tab);
    const qs = params.toString();
    router.push(qs ? `${pathname}?${qs}` : pathname);
  };

  const handleRankToggle = (rank: RankTier | "all") => {
    if (rank === "all") setSelectedRanks([]);
    else
      setSelectedRanks((prev) =>
        prev.includes(rank) ? prev.filter((r) => r !== rank) : [...prev, rank]
      );
  };

  // Tab + search filtered — used for rank chip counts
  const tabFiltered = useMemo(() => {
    let result = accounts;
    if (activeTab !== "all") result = result.filter((a) => a.trackingType === activeTab);
    if (search.trim()) {
      const q = search.toLowerCase();
      result = result.filter(
        (a) =>
          a.handle.toLowerCase().includes(q) ||
          a.displayName.toLowerCase().includes(q)
      );
    }
    return result;
  }, [accounts, activeTab, search]);

  // Fully filtered + sorted
  const filtered = useMemo(() => {
    let result = tabFiltered;
    if (selectedRanks.length > 0) {
      result = result.filter(
        (a) => a.currentRank && selectedRanks.includes(a.currentRank as RankTier)
      );
    }
    return [...result].sort((a, b) => {
      if (sortKey === "followers") return (b.followerCount ?? -1) - (a.followerCount ?? -1);
      if (sortKey === "outliers") return b.outlierCount - a.outlierCount;
      // quality score, nulls last
      if (a.currentScore === null && b.currentScore === null) return 0;
      if (a.currentScore === null) return 1;
      if (b.currentScore === null) return -1;
      return b.currentScore - a.currentScore;
    });
  }, [tabFiltered, selectedRanks, sortKey]);

  // Tracking tab counts (full dataset)
  const trackingCounts = useMemo(() => {
    const counts: Record<string, number> = { all: accounts.length };
    for (const a of accounts) {
      counts[a.trackingType] = (counts[a.trackingType] ?? 0) + 1;
    }
    return counts;
  }, [accounts]);

  // Rank chip counts (tab+search filtered, before rank filter)
  const rankCounts = useMemo(() => {
    const counts: Record<string, number> = { all: tabFiltered.length };
    for (const a of tabFiltered) {
      if (a.currentRank) counts[a.currentRank] = (counts[a.currentRank] ?? 0) + 1;
    }
    return counts;
  }, [tabFiltered]);

  // Stat cards computed from fully filtered set
  const stats = useMemo(() => {
    const total = filtered.length;
    const withContent = filtered.filter((a) => a.hasContent).length;
    const withFollowers = filtered.filter((a) => a.followerCount !== null);
    const avgRaw =
      withFollowers.length > 0
        ? withFollowers.reduce((s, a) => s + a.followerCount!, 0) / withFollowers.length
        : null;
    const llmScored = filtered.filter((a) => a.scoredContentCount > 0).length;
    return {
      total,
      withContent,
      avgFollowers: formatNumber(avgRaw !== null ? Math.round(avgRaw) : null),
      llmScored,
    };
  }, [filtered]);

  // Empty workspace state
  if (accounts.length === 0) {
    return (
      <div className="flex flex-col gap-8 pb-10">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Instagram Accounts</h1>
          <p className="text-muted-foreground mt-1 text-sm">
            Manage tracking types, ranks, and intelligent routing for IG profiles.
          </p>
        </div>
        <div className="flex flex-col items-center justify-center p-20 text-center border border-dashed border-border/50 rounded-xl bg-muted/10 mt-8">
          <Camera className="h-16 w-16 text-muted-foreground/30 mb-4" />
          <h3 className="text-xl font-bold">No Instagram accounts tracked yet</h3>
          <p className="text-muted-foreground mt-2 max-w-md">
            Add creators from the{" "}
            <Link href="/creators" className="text-indigo-400 hover:underline">
              Creators page
            </Link>{" "}
            — their Instagram profiles will appear here once discovered.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-8 pb-10">
      {/* Header */}
      <div className="flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Instagram Accounts</h1>
          <p className="text-muted-foreground mt-1 text-sm">
            Manage tracking types, ranks, and intelligent routing for IG profiles.
          </p>
        </div>
        <div className="flex items-center gap-3">
          <div className="relative w-64">
            <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
            <Input
              type="search"
              placeholder="Filter handles..."
              className="pl-9 bg-card border-border/50"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
          </div>
          <Select value={sortKey} onValueChange={(v) => setSortKey(v as SortKey)}>
            <SelectTrigger className="w-[180px] bg-card border-border/50">
              <SlidersHorizontal className="w-4 h-4 mr-2" />
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="quality">Quality Score</SelectItem>
              <SelectItem value="followers">Followers</SelectItem>
              <SelectItem value="outliers">Outlier Count</SelectItem>
            </SelectContent>
          </Select>
        </div>
      </div>

      <StatCardRow
        total={stats.total}
        withContent={stats.withContent}
        avgFollowers={stats.avgFollowers}
        llmScored={stats.llmScored}
      />

      <div className="flex flex-col gap-5 mt-2">
        <TrackingTabBar activeTab={activeTab} onTabChange={handleTabChange} counts={trackingCounts} />
        <RankFilterChips selectedRanks={selectedRanks} counts={rankCounts} onToggle={handleRankToggle} />
      </div>

      {filtered.length === 0 ? (
        <div className="flex flex-col items-center justify-center p-16 text-center border border-dashed border-border/50 rounded-xl bg-muted/10">
          <p className="text-muted-foreground font-medium">No accounts match the current filters.</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6 mt-4">
          {filtered.map((account) => (
            <AccountCard
              key={account.id}
              platform="instagram"
              handle={account.handle.startsWith("@") ? account.handle : `@${account.handle}`}
              displayName={account.displayName}
              avatarUrl={account.avatarUrl}
              rank={account.currentRank as RankTier | null}
              score={account.currentScore}
              analysisVersion={account.analysisVersion ?? "V1"}
              isClean={account.isClean}
              followers={formatNumber(account.followerCount)}
              postCount={formatNumber(account.postCount)}
              medianViews={formatNumber(account.medianViews)}
              outliers={account.outlierCount}
              isUnlinked={account.creatorId === null}
            />
          ))}
        </div>
      )}
    </div>
  );
}
