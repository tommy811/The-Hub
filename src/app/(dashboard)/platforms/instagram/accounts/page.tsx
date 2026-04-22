import { createServiceClient } from "@/lib/supabase/server";
import { InstagramAccountsClient } from "./InstagramAccountsClient";

export type AccountRowData = {
  id: string;
  handle: string;
  displayName: string;
  avatarUrl: string | null;
  profileUrl: string | null;
  followerCount: number | null;
  postCount: number | null;
  trackingType: string;
  isClean: boolean;
  analysisVersion: string | null;
  creatorId: string | null;
  currentScore: number | null;
  currentRank: string | null;
  scoredContentCount: number;
  medianViews: number | null;
  outlierCount: number;
  hasContent: boolean;
};

export default async function InstagramAccountsPage({
  searchParams,
}: {
  searchParams: { type?: string };
}) {
  const supabase = createServiceClient();
  const activeType = searchParams?.type ?? "all";

  const { data: ws } = await supabase
    .from("workspaces")
    .select("id")
    .limit(1)
    .single();

  if (!ws) {
    return <InstagramAccountsClient accounts={[]} activeType={activeType} />;
  }

  const wsId = ws.id;

  // Profiles + scores in one query
  const { data: rawProfiles } = await supabase
    .from("profiles")
    .select(`
      id, handle, display_name, avatar_url, profile_url,
      follower_count, post_count, tracking_type, is_clean,
      analysis_version, creator_id,
      profile_scores ( current_score, current_rank, scored_content_count )
    `)
    .eq("workspace_id", wsId)
    .eq("platform", "instagram")
    .eq("account_type", "social");

  if (!rawProfiles || rawProfiles.length === 0) {
    return <InstagramAccountsClient accounts={[]} activeType={activeType} />;
  }

  const profileIds = rawProfiles.map((p) => p.id);

  // Snapshots + scraped content in parallel
  const [snapshotsRes, contentRes] = await Promise.all([
    supabase
      .from("profile_metrics_snapshots")
      .select("profile_id, median_views, snapshot_date")
      .in("profile_id", profileIds)
      .order("snapshot_date", { ascending: false }),

    supabase
      .from("scraped_content")
      .select("profile_id, is_outlier, view_count, posted_at")
      .in("profile_id", profileIds),
  ]);

  // Latest snapshot per profile
  const snapshotMap = new Map<string, number>();
  for (const snap of snapshotsRes.data ?? []) {
    if (!snapshotMap.has(snap.profile_id)) {
      snapshotMap.set(snap.profile_id, snap.median_views);
    }
  }

  // Content stats: has_content, outlier counts, view arrays for live fallback
  const contentSet = new Set<string>();
  const outlierCountMap = new Map<string, number>();
  const viewsByProfile = new Map<string, number[]>();
  const cutoff = new Date(Date.now() - 90 * 24 * 60 * 60 * 1000);

  for (const row of contentRes.data ?? []) {
    contentSet.add(row.profile_id);
    if (row.is_outlier) {
      outlierCountMap.set(row.profile_id, (outlierCountMap.get(row.profile_id) ?? 0) + 1);
    }
    // Collect view_counts for the live median fallback (profiles missing a snapshot)
    if (!snapshotMap.has(row.profile_id) && row.view_count != null && row.posted_at) {
      if (new Date(row.posted_at) >= cutoff) {
        if (!viewsByProfile.has(row.profile_id)) viewsByProfile.set(row.profile_id, []);
        viewsByProfile.get(row.profile_id)!.push(row.view_count);
      }
    }
  }

  // Compute live median for profiles with content but no snapshot
  for (const [profileId, views] of viewsByProfile) {
    if (views.length > 0) {
      const sorted = [...views].sort((a, b) => a - b);
      const mid = Math.floor(sorted.length / 2);
      const median =
        sorted.length % 2 === 0
          ? (sorted[mid - 1] + sorted[mid]) / 2
          : sorted[mid];
      snapshotMap.set(profileId, Math.round(median));
    }
  }

  // Assemble typed rows
  const accounts: AccountRowData[] = rawProfiles.map((p) => {
    const scores = Array.isArray(p.profile_scores)
      ? (p.profile_scores[0] ?? null)
      : (p.profile_scores ?? null);

    return {
      id: p.id,
      handle: p.handle ?? "",
      displayName: p.display_name ?? p.handle ?? "",
      avatarUrl: p.avatar_url ?? null,
      profileUrl: p.profile_url ?? null,
      followerCount: p.follower_count ?? null,
      postCount: p.post_count ?? null,
      trackingType: p.tracking_type ?? "unreviewed",
      isClean: p.is_clean ?? false,
      analysisVersion: p.analysis_version ?? null,
      creatorId: p.creator_id ?? null,
      currentScore: scores?.current_score ?? null,
      currentRank: scores?.current_rank ?? null,
      scoredContentCount: scores?.scored_content_count ?? 0,
      medianViews: snapshotMap.get(p.id) ?? null,
      outlierCount: outlierCountMap.get(p.id) ?? 0,
      hasContent: contentSet.has(p.id),
    };
  });

  // Default sort: quality score desc, unscored last
  accounts.sort((a, b) => {
    if (a.currentScore === null && b.currentScore === null) return 0;
    if (a.currentScore === null) return 1;
    if (b.currentScore === null) return -1;
    return b.currentScore - a.currentScore;
  });

  return <InstagramAccountsClient accounts={accounts} activeType={activeType} />;
}
