// src/app/(dashboard)/creators/[slug]/page.tsx
export const dynamic = 'force-dynamic';

import { notFound } from "next/navigation";
import { PlatformIcon } from "@/components/accounts/PlatformIcon";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { AccountRow } from "@/components/accounts/AccountRow";
import { RefreshCw, AlertCircle, Users, Globe, DollarSign, Link2, MessageCircle } from "lucide-react";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { RerunDiscoveryButton } from "@/components/creators/RerunDiscoveryButton";
import { AddAccountDialog } from "@/components/creators/AddAccountDialog";
import { AvatarWithFallback } from "@/components/creators/AvatarWithFallback";
import { MergeBannerActions } from "@/components/creators/MergeBannerActions";
import { FailedRetryButton } from "@/components/creators/FailedRetryButton";
import { getCurrentWorkspaceId } from "@/lib/workspace";
import {
  getCreatorBySlugForWorkspace,
  getProfilesForCreator,
  getMergeCandidatesForCreator,
  getCreatorNameById,
} from "@/lib/db/queries";
import { ComingSoon } from "@/components/shared/ComingSoon";

const GRADIENTS = [
  "from-violet-500 to-indigo-600",
  "from-rose-500 to-pink-600",
  "from-amber-400 to-orange-500",
  "from-emerald-500 to-teal-600",
  "from-blue-500 to-cyan-600",
  "from-fuchsia-500 to-purple-600",
  "from-red-500 to-rose-600",
  "from-lime-500 to-green-600",
];

function getGradient(name: string): string {
  let hash = 0;
  for (let i = 0; i < name.length; i++) hash = (hash * 31 + name.charCodeAt(i)) >>> 0;
  return GRADIENTS[hash % GRADIENTS.length];
}

function formatNumber(n: number | null | undefined): string {
  if (!n) return '—';
  return new Intl.NumberFormat('en-US', { notation: 'compact', compactDisplay: 'short' }).format(n);
}

interface StatPanelProps {
  label: string;
  value: string | number;
  icon: React.ElementType;
  sub?: string;
}

function StatPanel({ label, value, icon: Icon, sub }: StatPanelProps) {
  return (
    <div className="flex flex-col gap-1 bg-muted/10 border border-border/40 rounded-xl p-4">
      <div className="flex items-center gap-2 text-muted-foreground text-xs font-semibold uppercase tracking-widest">
        <Icon className="h-3.5 w-3.5" />
        {label}
      </div>
      <div className="text-2xl font-bold mt-1">{value}</div>
      {sub && <div className="text-xs text-muted-foreground">{sub}</div>}
    </div>
  );
}

export default async function CreatorDetailPage({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  const wsId = await getCurrentWorkspaceId();
  const creator = await getCreatorBySlugForWorkspace(wsId, slug);
  if (!creator) return notFound();

  const [profiles, mergeCandidates] = await Promise.all([
    getProfilesForCreator(creator.id),
    getMergeCandidatesForCreator(creator.id),
  ]);

  let mergeWith: string | null = null;
  if (mergeCandidates.length > 0) {
    const mc = mergeCandidates[0];
    const otherId = mc.creator_a_id === creator.id ? mc.creator_b_id : mc.creator_a_id;
    mergeWith = await getCreatorNameById(otherId);
  }

  const primaryProfile = profiles.find(p => p.is_primary) ?? profiles[0];
  const avatarUrl = primaryProfile?.avatar_url ?? null;
  const gradient = getGradient(creator.canonical_name);

  const socialAccounts = profiles.filter(p => p.account_type === 'social');
  const monetizationAccounts = profiles.filter(p => p.account_type === 'monetization');
  const linkInBioAccounts = profiles.filter(p => p.account_type === 'link_in_bio');
  const messagingAccounts = profiles.filter(p => p.account_type === 'messaging');

  const totalFollowers = socialAccounts.reduce((sum, p) => sum + (p.follower_count || 0), 0);

  const hasMergeCandidate = mergeCandidates.length > 0;

  return (
    <div className="flex flex-col gap-6 max-w-5xl mx-auto w-full pb-10">

      {hasMergeCandidate && (
        <Alert className="bg-amber-500/10 border-amber-500/30 text-amber-500 mt-2">
          <AlertCircle className="h-4 w-4" color="currentColor" />
          <AlertTitle className="font-bold flex items-center justify-between">
            <span>Possible Duplicate Detected</span>
            <MergeBannerActions
              candidateId={mergeCandidates[0].id}
              keepId={creator.id}
              mergeId={
                mergeCandidates[0].creator_a_id === creator.id
                  ? mergeCandidates[0].creator_b_id
                  : mergeCandidates[0].creator_a_id
              }
              keepLabel={creator.canonical_name}
            />
          </AlertTitle>
          <AlertDescription className="text-amber-500/80">
            This creator may be the same person as <strong>{mergeWith || "another creator"}</strong>.
            {(() => {
              const ev = mergeCandidates[0]?.evidence as { summary?: string } | null | undefined;
              return ev?.summary ? ` ${ev.summary}` : null;
            })()}
          </AlertDescription>
        </Alert>
      )}

      {/* Header */}
      <div className="flex items-start gap-5 pt-2">
        <AvatarWithFallback
          avatarUrl={avatarUrl}
          name={creator.canonical_name}
          gradient={gradient}
          className="w-24 h-24 rounded-2xl border-4 border-background shadow-xl shrink-0"
          textClassName="text-3xl"
        />

        <div className="flex flex-col gap-1.5 flex-1 min-w-0 mt-1">
          <div className="flex items-start justify-between gap-4">
            <h1 className="text-2xl font-bold tracking-tight leading-none">{creator.canonical_name}</h1>
            <RerunDiscoveryButton creatorId={creator.id} isProcessing={creator.onboarding_status === 'processing'} />
          </div>

          <div className="flex items-center gap-2 text-sm text-muted-foreground flex-wrap">
            <span className="font-mono text-xs opacity-70">@{primaryProfile?.handle || creator.slug}</span>
            <span className="text-border">·</span>
            <PlatformIcon platform={creator.primary_platform || 'other'} showLabel />
            {creator.tracking_type && (
              <Badge variant="outline" className="text-[10px] uppercase font-bold text-muted-foreground">
                {creator.tracking_type.replace(/_/g, ' ')}
              </Badge>
            )}
          </div>

          {primaryProfile?.bio && (
            <p className="text-sm text-muted-foreground leading-snug line-clamp-2 max-w-xl mt-0.5">
              {primaryProfile.bio}
            </p>
          )}

          {(creator.tags?.length ?? 0) > 0 && (
            <div className="flex flex-wrap gap-1 mt-0.5">
              {(creator.tags ?? []).map((t: string) => (
                <span key={t} className="bg-muted px-2 py-0.5 rounded text-[10px] uppercase font-bold tracking-widest text-muted-foreground">{t}</span>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Stats strip */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <StatPanel
          label="Total Reach"
          value={totalFollowers > 0 ? formatNumber(totalFollowers) : '—'}
          icon={Users}
          sub={socialAccounts.length > 1 ? `across ${socialAccounts.length} platforms` : socialAccounts[0]?.platform || undefined}
        />
        <StatPanel
          label="Social"
          value={socialAccounts.length}
          icon={Globe}
          sub={socialAccounts.length > 0 ? socialAccounts.map(a => a.platform).join(', ') : 'none linked'}
        />
        <StatPanel
          label="Monetization"
          value={monetizationAccounts.length}
          icon={DollarSign}
          sub={monetizationAccounts.length > 0 ? monetizationAccounts.map(a => a.platform).join(', ') : 'none linked'}
        />
        <StatPanel
          label="Link-in-Bio"
          value={linkInBioAccounts.length}
          icon={Link2}
          sub={linkInBioAccounts.length > 0 ? linkInBioAccounts.map(a => a.handle).join(', ') : 'none linked'}
        />
      </div>

      {/* Status banners */}
      {creator.onboarding_status === 'processing' && (
        <div className="bg-indigo-500/10 border border-indigo-500/30 p-4 rounded-xl text-indigo-400 flex items-center gap-3">
          <RefreshCw className="h-4 w-4 animate-spin shrink-0" />
          <span className="text-sm font-medium">Discovering network footprint… Accounts will appear below as they&apos;re mapped.</span>
        </div>
      )}

      {creator.onboarding_status === 'failed' && (
        <div className="bg-red-900/10 border border-red-900/30 p-4 rounded-xl text-red-500 flex items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            <AlertCircle className="h-4 w-4 shrink-0" />
            <span className="text-sm font-medium">{creator.last_discovery_error || "Discovery run failed."}</span>
          </div>
          <FailedRetryButton creatorId={creator.id} />
        </div>
      )}

      {/* Tabs */}
      <Tabs defaultValue="network" className="w-full">
        <TabsList className="w-full justify-start bg-transparent border-b border-border/50 rounded-none h-auto p-0 gap-6">
          <TabsTrigger value="network" className="rounded-none data-[state=active]:border-b-2 data-[state=active]:border-indigo-500 data-[state=active]:bg-transparent px-0 pb-3 pt-2 text-sm">
            Network Mapping
          </TabsTrigger>
          <TabsTrigger value="funnel" className="rounded-none data-[state=active]:border-b-2 data-[state=active]:border-indigo-500 data-[state=active]:bg-transparent px-0 pb-3 pt-2 text-sm">
            Funnel
          </TabsTrigger>
          <TabsTrigger value="content" disabled className="rounded-none px-0 pb-3 pt-2 text-sm">
            Content <Badge variant="outline" className="ml-1.5 text-[8px] uppercase tracking-widest bg-transparent py-0">Soon</Badge>
          </TabsTrigger>
          <TabsTrigger value="branding" disabled className="rounded-none px-0 pb-3 pt-2 text-sm">
            Branding <Badge variant="outline" className="ml-1.5 text-[8px] uppercase tracking-widest bg-transparent py-0">Soon</Badge>
          </TabsTrigger>
        </TabsList>

        <TabsContent value="network" className="mt-6 space-y-6">
          <NetworkSection title="Social & Media" icon={Globe} accounts={socialAccounts} creatorId={creator.id} />
          <NetworkSection title="Link-in-Bio" icon={Link2} accounts={linkInBioAccounts} creatorId={creator.id} />
          <NetworkSection title="Monetization" icon={DollarSign} accounts={monetizationAccounts} creatorId={creator.id} />
          <NetworkSection title="Messaging & Communities" icon={MessageCircle} accounts={messagingAccounts} creatorId={creator.id} />
        </TabsContent>

        <TabsContent value="funnel" className="mt-6">
          <ComingSoon
            phase={4}
            feature="Funnel visualization"
            description="Visualize how traffic flows across this creator's network."
          />
        </TabsContent>
      </Tabs>
    </div>
  );
}

function NetworkSection({ title, icon: Icon, accounts, creatorId }: { title: string, icon: React.ElementType, accounts: any[], creatorId: string }) {
  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Icon className="h-4 w-4 text-muted-foreground" />
          <h3 className="font-semibold text-sm">
            {title}
          </h3>
          <span className="text-muted-foreground/50 font-mono text-xs">{accounts.length}</span>
        </div>
        <AddAccountDialog creatorId={creatorId} />
      </div>
      <div className="flex flex-col gap-1.5">
        {accounts.length === 0 ? (
          <p className="text-xs text-muted-foreground italic py-3 pl-1">None discovered.</p>
        ) : (
          accounts.map(a => (
            <AccountRow
              key={a.id}
              id={a.id}
              platform={a.platform}
              handle={a.handle}
              displayName={a.display_name}
              url={a.url}
              followerCount={a.follower_count}
              accountType={a.account_type}
              discoveryConfidence={a.discovery_confidence ?? 1}
              isPrimary={a.is_primary}
              lastScrapedAt={a.updated_at}
            />
          ))
        )}
      </div>
    </div>
  );
}
