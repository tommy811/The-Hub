// src/components/creators/CreatorCard.tsx — Creator grid card
"use client";

import { type ReactNode } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { useRouter } from "next/navigation";
import { useTransition } from "react";
import { MoreHorizontal, FileText, Edit3, Archive, Loader2, AlertCircle, RefreshCw, Users } from "lucide-react";
import { toast } from "sonner";
import { retryCreatorDiscovery } from "@/app/(dashboard)/creators/actions";
import { Card } from "@/components/ui/card";
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from "@/components/ui/dropdown-menu";
import { PlatformIcon } from "@/components/accounts/PlatformIcon";
import { AvatarWithFallback } from "@/components/creators/AvatarWithFallback";
import { Badge } from "@/components/ui/badge";
import Link from "next/link";
import { cn } from "@/lib/utils";

interface CreatorCardProps {
  id: string;
  canonicalName: string;
  slug: string;
  avatarUrl?: string;
  primaryPlatform: string;
  status: 'processing' | 'ready' | 'failed' | 'archived';
  trackingType: string;
  monetizationModel?: string;
  tags: string[];
  knownUsernames?: string[];
  accountCounts: Record<string, number>;
  totalFollowers: string;
  updatedAgo: string;
  hasMergeCandidate: boolean;
  errorMessage?: string;
}

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

function CreatorCardContainer({
  children,
  className,
  onClick,
}: {
  children: ReactNode;
  className?: string;
  onClick?: () => void;
}) {
  return (
    <Card
      onClick={onClick}
      className={cn(
        "group relative flex flex-col min-h-[260px] overflow-hidden transition-all border border-border/50 bg-[#13131A] rounded-xl",
        onClick && "cursor-pointer hover:-translate-y-1 hover:shadow-2xl hover:shadow-indigo-500/10",
        className
      )}
    >
      {children}
    </Card>
  );
}

function CreatorCardAvatar({
  avatarUrl,
  canonicalName,
  gradient,
}: {
  avatarUrl?: string;
  canonicalName: string;
  gradient: string;
}) {
  return (
    <AvatarWithFallback
      avatarUrl={avatarUrl ?? null}
      name={canonicalName}
      gradient={gradient}
      className="w-20 h-20 rounded-2xl border-4 border-background shadow-xl shrink-0"
      textClassName="text-2xl tracking-tight"
    />
  );
}

export function CreatorCard({
  id, canonicalName, slug, avatarUrl, primaryPlatform, status,
  trackingType, monetizationModel, tags, knownUsernames = [],
  accountCounts, totalFollowers, updatedAgo, hasMergeCandidate, errorMessage
}: CreatorCardProps) {
  const router = useRouter();
  const [isPending, startTransition] = useTransition();
  const gradient = getGradient(canonicalName);

  const handleRerun = () => {
    startTransition(async () => {
      const r = await retryCreatorDiscovery(id);
      if (!r.ok) {
        toast.error("Re-run discovery failed", { description: r.error });
        return;
      }
      toast.success("Discovery re-queued");
      router.refresh();
    });
  };
  const totalAccounts = Object.values(accountCounts).reduce((s, n) => s + n, 0);
  const primaryHandle = knownUsernames[0] || canonicalName.toLowerCase().replace(/\s+/g, '');

  return (
    <AnimatePresence mode="wait">
      {status === 'processing' && (
        <motion.div key="processing" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
          <CreatorCardContainer className="opacity-60 pointer-events-none">
            <div className="absolute top-4 right-4 text-indigo-400">
              <Loader2 className="h-5 w-5 animate-spin" />
            </div>
            <div className="flex flex-col items-center justify-center p-6 pt-10 gap-4 flex-1">
              <div className={cn("w-20 h-20 rounded-2xl bg-gradient-to-br animate-pulse", gradient)} />
              <div className="flex flex-col items-center gap-2 w-full">
                <div className="h-5 w-3/4 bg-muted/40 animate-pulse rounded" />
                <div className="h-3 w-1/2 bg-muted/30 animate-pulse rounded" />
              </div>
              <div className="text-xs text-indigo-400/80 font-medium">Discovering {canonicalName}…</div>
            </div>
            <div className="p-4 border-t border-border/30 flex gap-2">
              <div className="h-4 w-1/4 bg-muted/30 animate-pulse rounded" />
              <div className="h-4 w-1/4 bg-muted/30 animate-pulse rounded" />
            </div>
          </CreatorCardContainer>
        </motion.div>
      )}

      {status === 'failed' && (
        <motion.div key="failed" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
          <CreatorCardContainer className="border-red-900/60 shadow-lg shadow-red-900/10">
            <div className="absolute top-4 right-4 text-red-500">
              <AlertCircle className="h-5 w-5" />
            </div>
            <div className="flex flex-col items-center p-6 pt-10 gap-4 flex-1">
              <div className="w-20 h-20 rounded-2xl bg-red-900/20 flex items-center justify-center border border-red-900/50">
                <PlatformIcon platform={primaryPlatform} size={24} className="text-red-500 opacity-50" />
              </div>
              <div className="text-center">
                <div className="font-semibold text-lg">{canonicalName}</div>
                <div className="text-xs text-red-400/80 mt-2 max-w-[200px] line-clamp-2" title={errorMessage}>
                  {errorMessage || "Discovery failed"}
                </div>
              </div>
            </div>
            <div className="p-4 border-t border-red-900/30 flex justify-center">
              <button
                onClick={handleRerun}
                disabled={isPending}
                className="flex items-center gap-2 text-xs font-semibold text-red-400 hover:text-red-300 border border-red-900/50 rounded-full px-4 py-1.5 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
              >
                <RefreshCw className={`h-3 w-3 ${isPending ? 'animate-spin' : ''}`} /> {isPending ? 'Retrying…' : 'Re-run Discovery'}
              </button>
            </div>
          </CreatorCardContainer>
        </motion.div>
      )}

      {status === 'ready' && (
        <motion.div key="ready" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
          <CreatorCardContainer className="hover:border-indigo-500/50" onClick={() => router.push(`/creators/${slug}`)}>
            {hasMergeCandidate && (
              <div className="absolute top-3 right-3 z-10">
                <Badge className="bg-amber-500/20 text-amber-500 hover:bg-amber-500/30 border-amber-500/30 font-bold uppercase tracking-widest text-[9px]">
                  ⚠ Duplicate?
                </Badge>
              </div>
            )}

            <div className="absolute top-3 left-3 opacity-0 group-hover:opacity-100 transition-opacity z-10" onClick={e => e.stopPropagation()}>
              <DropdownMenu>
                <DropdownMenuTrigger className="inline-flex items-center justify-center h-8 w-8 rounded-full bg-background/80 backdrop-blur-sm border border-border/50 shadow-sm hover:bg-background text-foreground">
                  <MoreHorizontal className="h-4 w-4" />
                </DropdownMenuTrigger>
                <DropdownMenuContent align="start" className="w-48">
                  <DropdownMenuItem className="p-0">
                    <Link href={`/creators/${slug}`} className="cursor-pointer flex w-full items-center px-2 py-1.5">
                      <FileText className="mr-2 h-4 w-4" /> View Profile
                    </Link>
                  </DropdownMenuItem>
                  <DropdownMenuItem><Edit3 className="mr-2 h-4 w-4" /> Edit Tracking</DropdownMenuItem>
                  <DropdownMenuItem onClick={handleRerun} disabled={isPending}>
                    <RefreshCw className={`mr-2 h-4 w-4 ${isPending ? 'animate-spin' : ''}`} /> Re-run Discovery
                  </DropdownMenuItem>
                  <DropdownMenuItem className="text-red-500 focus:bg-red-500/10 focus:text-red-500">
                    <Archive className="mr-2 h-4 w-4" /> Archive
                  </DropdownMenuItem>
                </DropdownMenuContent>
              </DropdownMenu>
            </div>

            {/* Avatar + name */}
            <div className="flex flex-col items-center px-6 pt-8 pb-4">
              <CreatorCardAvatar
                avatarUrl={avatarUrl}
                canonicalName={canonicalName}
                gradient={gradient}
              />
              <div className="mt-3 font-bold text-lg text-center leading-snug">{canonicalName}</div>
              <div className="flex items-center gap-1 mt-1 text-muted-foreground">
                <PlatformIcon platform={primaryPlatform} size={12} />
                <span className="text-[11px]">@{primaryHandle}</span>
              </div>
            </div>

            {/* Badges + tags */}
            <div className="px-5 flex flex-col gap-2 flex-1">
              <div className="flex justify-center gap-1.5 flex-wrap">
                <Badge variant="outline" className={cn(
                  "text-[10px] uppercase font-bold",
                  trackingType === 'managed' ? "text-indigo-400 border-indigo-400/30 bg-indigo-500/10" :
                  trackingType === 'competitor' ? "text-rose-400 border-rose-400/30 bg-rose-500/10" :
                  trackingType === 'candidate' ? "text-amber-400 border-amber-400/30 bg-amber-500/10" :
                  "text-violet-400 border-violet-400/30 bg-violet-500/10"
                )}>
                  {trackingType.replace(/_/g, ' ')}
                </Badge>
                {monetizationModel && monetizationModel !== 'unknown' && (
                  <Badge variant="outline" className="text-[10px] uppercase font-bold text-muted-foreground border-border/50">
                    {monetizationModel.replace(/_/g, ' ')}
                  </Badge>
                )}
              </div>

              {tags.length > 0 && (
                <div className="flex flex-wrap items-center justify-center gap-1">
                  {tags.slice(0, 3).map((t, i) => (
                    <span key={i} className="text-[10px] text-muted-foreground bg-muted/40 px-1.5 py-0.5 rounded">{t}</span>
                  ))}
                  {tags.length > 3 && <span className="text-[10px] text-muted-foreground bg-muted/40 px-1.5 py-0.5 rounded">+{tags.length - 3}</span>}
                </div>
              )}
            </div>

            {/* Footer */}
            <div className="mt-4 p-3 px-5 bg-muted/10 border-t border-border/50 flex items-center justify-between text-xs">
              <div className="flex items-center gap-1.5 font-medium">
                <Users className="h-3.5 w-3.5 text-muted-foreground" />
                <span>{totalFollowers}</span>
              </div>
              <div className="flex items-center gap-1.5 text-muted-foreground">
                <span>{totalAccounts} account{totalAccounts !== 1 ? 's' : ''}</span>
                <span className="opacity-40">·</span>
                <span className="text-[10px] uppercase tracking-widest font-semibold">{updatedAgo}</span>
              </div>
            </div>
          </CreatorCardContainer>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
