// src/app/(dashboard)/creators/[slug]/page.tsx — Creator deep dive details
import { notFound } from "next/navigation";
import { PlatformIcon } from "@/components/accounts/PlatformIcon";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { AccountRow } from "@/components/accounts/AccountRow";
import { Network, RefreshCw, AlertCircle } from "lucide-react";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";

// In real implementation, this would fetch from Supabase
const creatorMock = {
  id: "1",
  canonical_name: "Sunny Rose",
  slug: "sunnyrose",
  primary_platform: "instagram",
  avatarUrl: "https://i.pravatar.cc/300?u=sunnyrose",
  onboarding_status: "ready", // ready | processing | failed
  tracking_type: "managed",
  tags: ["fitness", "top_tier", "model"],
  last_discovery_error: null,
  hasMergeCandidate: true,
  isMergeCandidateWith: "Sunny R.",
  network: [
    { id: "p1", platform: "instagram", handle: "sunnyrose", url: "https://instagram.com/sunnyrose", followerCount: 1200000, accountType: "social", discoveryConfidence: 1, isPrimary: true },
    { id: "p2", platform: "tiktok", handle: "sunny.tv", url: "https://tiktok.com/@sunny.tv", followerCount: 3000000, accountType: "social", discoveryConfidence: 0.95 },
    { id: "p3", platform: "onlyfans", handle: "sunnyrose", url: "https://onlyfans.com/sunnyrose", accountType: "monetization", discoveryConfidence: 0.98 },
    { id: "p4", platform: "amazon_storefront", handle: "sunny", accountType: "monetization", discoveryConfidence: 0.75 },
    { id: "p5", platform: "linktree", handle: "sunnyrose", accountType: "link_in_bio", discoveryConfidence: 0.99 },
  ],
  funnelEdgesCount: 4
};

export default function CreatorDetailPage({ params }: { params: { slug: string } }) {
  const creator = creatorMock;

  if (!creator) return notFound();

  const socialAccounts = creator.network.filter(a => a.accountType === 'social');
  const monetizationAccounts = creator.network.filter(a => a.accountType === 'monetization');
  const linkInBioAccounts = creator.network.filter(a => a.accountType === 'link_in_bio');
  const messagingAccounts = creator.network.filter(a => a.accountType === 'messaging');

  return (
    <div className="flex flex-col gap-6 max-w-6xl mx-auto w-full pb-10">
      
      {/* Pending Merge Alert */}
      {creator.hasMergeCandidate && (
        <Alert className="bg-amber-500/10 border-amber-500/30 text-amber-500 mt-2">
          <AlertCircle className="h-4 w-4" color="currentColor" />
          <AlertTitle className="font-bold flex items-center justify-between">
            <span>Possible Duplicate Detected</span>
            <div className="flex gap-2">
              <Button size="sm" variant="outline" className="h-7 text-xs border-amber-500/30 hover:bg-amber-500/20 text-amber-500">Not the same person</Button>
              <Button size="sm" className="h-7 text-xs bg-amber-500 hover:bg-amber-400 text-amber-950 font-bold">Merge: Keep {creator.canonical_name}</Button>
            </div>
          </AlertTitle>
          <AlertDescription className="text-amber-500/80">
            This creator may be the same person as <strong>{creator.isMergeCandidateWith}</strong>. Evidence: Exact avatar match, identical link-in-bio URL found in both discoveries.
          </AlertDescription>
        </Alert>
      )}

      {/* Header Profile Section */}
      <div className="flex items-start gap-6 border-b border-border/50 pb-6 pt-2">
        <div className="w-28 h-28 rounded-3xl border-4 border-background shadow-xl overflow-hidden bg-muted flex flex-col items-center justify-center shrink-0">
          {creator.avatarUrl ? (
            <img src={creator.avatarUrl} alt="" className="w-full h-full object-cover" />
          ) : (
            <span className="text-3xl font-black text-muted-foreground">{creator.canonical_name.substring(0, 2).toUpperCase()}</span>
          )}
        </div>
        
        <div className="flex flex-col gap-2 flex-1 mt-1">
          <div className="flex items-center justify-between">
            <h1 className="text-3xl font-bold tracking-tight hover:text-indigo-400 transition-colors cursor-pointer" title="Click to edit canonical name">
              {creator.canonical_name}
            </h1>
            <Button variant="outline" size="sm" disabled={creator.onboarding_status === 'processing'} className="h-8">
              <RefreshCw className={`h-4 w-4 mr-2 ${creator.onboarding_status === 'processing' ? 'animate-spin' : ''}`} />
              Re-run Discovery
            </Button>
          </div>
          
          <div className="flex items-center gap-3 text-sm text-muted-foreground font-medium">
             <span className="font-mono text-xs opacity-60">@{creator.slug}</span>
             <PlatformIcon platform={creator.primary_platform} showLabel />
             <div className="flex flex-wrap gap-1">
               {creator.tags.map(t => <span key={t} className="bg-muted px-2 py-0.5 rounded text-[10px] uppercase font-bold tracking-widest">{t}</span>)}
             </div>
          </div>
        </div>
      </div>

      {/* Banners */}
      {creator.onboarding_status === 'processing' && (
        <div className="bg-indigo-500/10 border border-indigo-500/30 p-4 rounded-xl text-indigo-400 flex items-center justify-center gap-3">
           <RefreshCw className="h-5 w-5 animate-spin" />
           <span className="font-medium">Discovering network footprint... Accounts will appear below as they're mapped.</span>
        </div>
      )}

      {creator.onboarding_status === 'failed' && (
        <div className="bg-red-900/10 border border-red-900/30 p-4 rounded-xl text-red-500 flex items-center justify-between gap-3">
           <div className="flex items-center gap-3">
             <AlertCircle className="h-5 w-5" />
             <span className="font-medium">{creator.last_discovery_error || "Discovery run failed abruptly."}</span>
           </div>
           <Button size="sm" variant="outline" className="border-red-900/50 hover:bg-red-900/20 text-red-400">Retry</Button>
        </div>
      )}

      {/* Tabs */}
      <Tabs defaultValue="network" className="w-full">
        <TabsList className="w-full justify-start bg-transparent border-b border-border/50 rounded-none h-auto p-0 gap-6">
          <TabsTrigger value="network" className="rounded-none data-[state=active]:border-b-2 data-[state=active]:border-indigo-500 data-[state=active]:bg-transparent px-0 pb-3 pt-2">Network Mapping</TabsTrigger>
          <TabsTrigger value="funnel" className="rounded-none data-[state=active]:border-b-2 data-[state=active]:border-indigo-500 data-[state=active]:bg-transparent px-0 pb-3 pt-2">Funnel Analysis</TabsTrigger>
          <TabsTrigger value="content" disabled className="rounded-none px-0 pb-3 pt-2">Content <Badge variant="outline" className="ml-2 text-[8px] uppercase tracking-widest bg-transparent">Soon</Badge></TabsTrigger>
          <TabsTrigger value="branding" disabled className="rounded-none px-0 pb-3 pt-2">Branding <Badge variant="outline" className="ml-2 text-[8px] uppercase tracking-widest bg-transparent">Soon</Badge></TabsTrigger>
          <TabsTrigger value="monetization" disabled className="rounded-none px-0 pb-3 pt-2">Monetization <Badge variant="outline" className="ml-2 text-[8px] uppercase tracking-widest bg-transparent">Soon</Badge></TabsTrigger>
        </TabsList>
        
        <TabsContent value="network" className="mt-8 space-y-8">
           {/* Section: Social */}
           <div className="space-y-3">
             <div className="flex items-center justify-between">
                <h3 className="text-lg font-bold tracking-tight">Social & Media <span className="text-muted-foreground/50 ml-2 font-mono text-sm">{socialAccounts.length}</span></h3>
                <Button variant="ghost" size="sm" className="text-xs text-indigo-400 hover:text-indigo-300">Add manually</Button>
             </div>
             <div className="flex flex-col gap-2">
               {socialAccounts.length === 0 ? <p className="text-sm text-muted-foreground italic">None discovered.</p> : socialAccounts.map(a => <AccountRow key={a.id} {...a} />)}
             </div>
           </div>

           {/* Section: Link In Bio */}
           <div className="space-y-3">
             <div className="flex items-center justify-between">
                <h3 className="text-lg font-bold tracking-tight">Traffic Hubs (Link-in-Bio) <span className="text-muted-foreground/50 ml-2 font-mono text-sm">{linkInBioAccounts.length}</span></h3>
                <Button variant="ghost" size="sm" className="text-xs text-indigo-400 hover:text-indigo-300">Add manually</Button>
             </div>
             <div className="flex flex-col gap-2">
               {linkInBioAccounts.length === 0 ? <p className="text-sm text-muted-foreground italic">None discovered.</p> : linkInBioAccounts.map(a => <AccountRow key={a.id} {...a} />)}
             </div>
           </div>

           {/* Section: Monetization */}
           <div className="space-y-3">
             <div className="flex items-center justify-between">
                <h3 className="text-lg font-bold tracking-tight">Monetization <span className="text-muted-foreground/50 ml-2 font-mono text-sm">{monetizationAccounts.length}</span></h3>
                <Button variant="ghost" size="sm" className="text-xs text-indigo-400 hover:text-indigo-300">Add manually</Button>
             </div>
             <div className="flex flex-col gap-2">
               {monetizationAccounts.length === 0 ? <p className="text-sm text-muted-foreground italic">None discovered.</p> : monetizationAccounts.map(a => <AccountRow key={a.id} {...a} />)}
             </div>
           </div>

           {/* Section: Messaging */}
           <div className="space-y-3">
             <div className="flex items-center justify-between">
                <h3 className="text-lg font-bold tracking-tight">Messaging & Communities <span className="text-muted-foreground/50 ml-2 font-mono text-sm">{messagingAccounts.length}</span></h3>
                <Button variant="ghost" size="sm" className="text-xs text-indigo-400 hover:text-indigo-300">Add manually</Button>
             </div>
             <div className="flex flex-col gap-2">
               {messagingAccounts.length === 0 ? <p className="text-sm text-muted-foreground italic">None discovered.</p> : messagingAccounts.map(a => <AccountRow key={a.id} {...a} />)}
             </div>
           </div>
        </TabsContent>

        <TabsContent value="funnel" className="mt-8">
           <div className="flex flex-col justify-center items-center h-64 border border-dashed border-border/50 rounded-xl bg-muted/10 text-center">
              <Network className="h-10 w-10 text-indigo-500/50 mb-3" />
              <h3 className="text-lg font-bold">Funnel visualization</h3>
              <p className="text-muted-foreground mt-1 max-w-sm">Coming soon. {creator.funnelEdgesCount} traffic connections mapped between platforms so far.</p>
           </div>
        </TabsContent>
      </Tabs>

    </div>
  );
}
