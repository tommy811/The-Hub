import Link from "next/link";
import Image from "next/image";
import { Card } from "@/components/ui/card";
import { ExternalLink, RefreshCw, Archive, Edit3, MoreHorizontal, FileText, Unlink } from "lucide-react";
import { cn } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";
import { RankBadge } from "./RankBadge";
import { type RankTier } from "@/lib/ranks";
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from "@/components/ui/dropdown-menu";

export interface AccountCardProps {
  platform: 'instagram' | 'tiktok';
  handle: string;
  displayName: string;
  avatarUrl: string | null;
  rank: RankTier | null;
  score: number | null;
  analysisVersion: string;
  isClean: boolean;
  followers: string;
  postCount: string;
  medianViews: string;
  outliers: number;
  isUnlinked?: boolean;
  creatorSlug?: string | null;
}

export function AccountCard(props: AccountCardProps) {
  const initials = props.displayName.substring(0, 2).toUpperCase();

  return (
    <div className="relative group">
      {/* Stretched link — covers the whole card, sits below interactive elements */}
      {props.creatorSlug && (
        <Link
          href={`/creators/${props.creatorSlug}`}
          className="absolute inset-0 z-[1] rounded-xl"
          aria-label={`View ${props.displayName} creator profile`}
        />
      )}

      <Card className={cn(
        "relative flex flex-col overflow-hidden transition-all",
        props.creatorSlug && "hover:-translate-y-1 hover:shadow-2xl hover:shadow-indigo-500/10 hover:border-indigo-500/50 cursor-pointer"
      )}>

      {/* Top Half: Image & Rank */}
      <div className="relative flex justify-center pt-8 pb-10 bg-gradient-to-b from-muted/30 to-background">

        {/* Actions Menu */}
        <div className="absolute top-3 right-3 opacity-0 group-hover:opacity-100 transition-opacity z-[2]">
          <DropdownMenu>
            <DropdownMenuTrigger className="inline-flex items-center justify-center whitespace-nowrap text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-1 disabled:pointer-events-none disabled:opacity-50 h-8 w-8 rounded-full bg-background/50 backdrop-blur-sm border shadow-sm hover:bg-background/80 hover:text-accent-foreground text-foreground">
              <MoreHorizontal className="h-4 w-4" />
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="w-48">
              <DropdownMenuItem><FileText className="mr-2 h-4 w-4" /> View analysis</DropdownMenuItem>
              <DropdownMenuItem><Edit3 className="mr-2 h-4 w-4" /> Edit tracking type</DropdownMenuItem>
              <DropdownMenuItem><RefreshCw className="mr-2 h-4 w-4" /> Refresh data</DropdownMenuItem>
              <DropdownMenuItem className="text-destructive"><Archive className="mr-2 h-4 w-4" /> Archive account</DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>

        {/* Unlinked badge */}
        {props.isUnlinked && (
          <div className="absolute top-3 left-3 z-[2]">
            <Badge variant="outline" className="text-[9px] uppercase tracking-widest font-bold border-zinc-600/50 text-zinc-500 bg-zinc-500/10 flex items-center gap-1">
              <Unlink className="h-2.5 w-2.5" /> Unlinked
            </Badge>
          </div>
        )}

        <div className="relative">
          {props.avatarUrl ? (
            <Image
              src={props.avatarUrl}
              alt={props.handle}
              width={96}
              height={96}
              unoptimized
              className="w-24 h-24 rounded-2xl object-cover border-4 border-background shadow-lg group-hover:scale-105 transition-transform duration-500"
            />
          ) : (
            <div className="w-24 h-24 rounded-2xl border-4 border-background shadow-lg bg-muted flex items-center justify-center">
              <span className="text-2xl font-black text-muted-foreground">{initials}</span>
            </div>
          )}

          {/* Rank overlay */}
          <div className="absolute -bottom-6 left-1/2 -translate-x-1/2 scale-[0.8] origin-top">
            {props.rank !== null ? (
              <RankBadge rank={props.rank} score={props.score ?? undefined} />
            ) : (
              <div className="flex items-center px-2.5 py-1 rounded-full bg-background border border-border/30 shadow-sm whitespace-nowrap">
                <span className="text-[10px] font-semibold text-muted-foreground/50 uppercase tracking-wider">Not ranked</span>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Detail Half */}
      <div className="flex flex-col flex-1 p-5 pt-8 gap-4 bg-background">

        {/* Handle & display name */}
        <div className="flex flex-col items-center text-center">
          <a
            href={`https://${props.platform}.com/${props.handle.replace('@', '')}`}
            target="_blank"
            rel="noopener noreferrer"
            onClick={(e) => e.stopPropagation()}
            className="relative z-[2] flex items-center gap-1 text-lg font-bold hover:text-indigo-400 transition-colors decoration-indigo-400/30 underline-offset-4 hover:underline"
          >
            {props.handle} <ExternalLink className="h-3.5 w-3.5 text-muted-foreground" />
          </a>
          <span className="text-xs text-muted-foreground font-medium">{props.displayName}</span>
        </div>

        {/* Meta badges */}
        <div className="flex items-center justify-center gap-1.5 flex-wrap">
          <span className={cn(
            "px-1.5 py-0.5 rounded text-[9px] font-bold uppercase tracking-widest border",
            props.analysisVersion === 'V2'
              ? "bg-green-500/10 text-green-500 border-green-500/20"
              : "bg-muted/40 text-muted-foreground border-border/30"
          )}>
            {props.analysisVersion}
          </span>
          {props.isClean && (
            <span className="px-1.5 py-0.5 rounded text-[9px] font-bold bg-emerald-500/10 text-emerald-500 border border-emerald-500/20 uppercase tracking-widest">
              CLEAN
            </span>
          )}
        </div>

        {/* Stats Strip */}
        <div className="grid grid-cols-4 mt-auto pt-4 border-t border-border/50 divide-x divide-border/50">
          <StatBox label="Flw." value={props.followers} />
          <StatBox label={props.platform === 'instagram' ? 'Reels' : 'Vids'} value={props.postCount} />
          <StatBox label="Med.View" value={props.medianViews} />
          <StatBox label="Outlier" value={props.outliers} isHighlight={props.outliers > 0} />
        </div>
      </div>
    </Card>
    </div>
  );
}

function StatBox({ label, value, isHighlight }: { label: string; value: string | number; isHighlight?: boolean }) {
  return (
    <div className="flex flex-col items-center justify-center px-1">
      <span className={cn("text-[13px] font-bold tracking-tight", isHighlight ? "text-amber-500" : "text-foreground")}>
        {value}
      </span>
      <span className="text-[9px] uppercase tracking-wider text-muted-foreground font-semibold">
        {label}
      </span>
    </div>
  );
}
