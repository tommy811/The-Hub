// src/components/accounts/AccountRow.tsx — Network tab account row component
"use client";

import { PlatformIcon } from "./PlatformIcon";
import { AccountRowMenu } from "./AccountRowMenu";
import { Badge } from "@/components/ui/badge";
import { ExternalLink, Star } from "lucide-react";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";
import { cn } from "@/lib/utils";

interface AccountRowProps {
  id: string;
  platform: string;
  handle: string;
  url?: string;
  displayName?: string;
  followerCount?: number;
  accountType: string;
  discoveryConfidence: number;
  isPrimary?: boolean;
  lastScrapedAt?: string;
}

// Inline relative-date helper. "today" / "Nd ago" up to 30 days, then a
// short month/day. Deliberately not extracted to a util — we have exactly
// one caller and the logic is small.
function formatRelative(iso: string | undefined): string | null {
  if (!iso) return null;
  const then = new Date(iso);
  if (Number.isNaN(then.getTime())) return null;
  const now = Date.now();
  const diffMs = now - then.getTime();
  const oneDay = 86_400_000;
  const days = Math.floor(diffMs / oneDay);
  if (days <= 0) return "today";
  if (days === 1) return "1d ago";
  if (days < 30) return `${days}d ago`;
  return new Intl.DateTimeFormat("en-US", { month: "short", day: "numeric" }).format(then);
}

export function AccountRow({
  id, platform, handle, url, displayName, followerCount, accountType, discoveryConfidence, isPrimary, lastScrapedAt
}: AccountRowProps) {

  const hasFollowers = followerCount !== undefined && followerCount !== null && followerCount > 0;
  const formattedFollowers = hasFollowers
    ? new Intl.NumberFormat('en-US', { notation: "compact", compactDisplay: "short" }).format(followerCount as number)
    : '—';

  const confidenceColor =
    discoveryConfidence >= 0.9 ? "bg-emerald-500" :
    discoveryConfidence >= 0.7 ? "bg-amber-500" : "bg-rose-500";

  const relativeUpdated = formatRelative(lastScrapedAt);

  return (
    <div className="flex items-center justify-between p-3 rounded-lg border border-border/50 bg-background/50 hover:bg-muted/30 transition-colors group">

      <div className="flex items-center gap-4 flex-1">
        <div className="flex items-center gap-2 w-[200px] shrink-0">
          <PlatformIcon platform={platform} size={16} />
          {url ? (
            <a href={url} target="_blank" rel="noopener noreferrer" className="font-semibold text-sm hover:text-indigo-400 transition-colors flex items-center gap-1">
              {handle} <ExternalLink className="h-3 w-3 opacity-50" />
            </a>
          ) : (
            <span className="font-semibold text-sm">{handle}</span>
          )}
          {isPrimary && (
            <TooltipProvider>
              <Tooltip>
                <TooltipTrigger className="inline-flex outline-none focus:outline-none bg-transparent border-0 p-0">
                   <Star className="h-3 w-3 text-amber-500 fill-amber-500 shrink-0" />
                </TooltipTrigger>
                <TooltipContent>Primary Profile</TooltipContent>
              </Tooltip>
            </TooltipProvider>
          )}
        </div>

        <div className="text-sm text-foreground/80 w-[200px] truncate">
          {displayName || <span className="text-muted-foreground italic">No display name</span>}
        </div>

        <div className="text-sm font-medium w-[100px]">
          {formattedFollowers} {hasFollowers && <span className="text-xs text-muted-foreground font-normal">flwrs</span>}
        </div>

        <div className="flex items-center gap-2 w-[150px]">
           <Badge variant="outline" className="text-[10px] uppercase font-bold text-muted-foreground bg-background">
             {accountType.replaceAll('_', ' ')}
           </Badge>
        </div>
      </div>

      <div className="flex items-center gap-6 shrink-0">
        <div className="flex items-center gap-2">
           <TooltipProvider>
            <Tooltip>
              <TooltipTrigger className="flex items-center gap-1.5 px-2 py-1 bg-muted/40 rounded-full border border-border/50 cursor-help outline-none">
                <div className={cn("w-2 h-2 rounded-full", confidenceColor)} />
                <span className="text-[10px] uppercase font-bold text-muted-foreground">
                  {(discoveryConfidence * 100).toFixed(0)}%
                </span>
              </TooltipTrigger>
              <TooltipContent>AI Discovery Confidence</TooltipContent>
            </Tooltip>
           </TooltipProvider>
           {relativeUpdated && (
             <span className="text-[10px] text-muted-foreground uppercase font-bold tracking-widest hidden lg:block">
               Updated {relativeUpdated}
             </span>
           )}
        </div>

        <AccountRowMenu profileId={id} handle={handle} />
      </div>

    </div>
  );
}
