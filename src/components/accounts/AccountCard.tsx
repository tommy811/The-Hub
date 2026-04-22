import { Card } from "@/components/ui/card";
import { ExternalLink, RefreshCw, Archive, Edit3, MoreHorizontal, FileText } from "lucide-react";
import { cn } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";
import { RankBadge } from "./RankBadge";
import { type RankTier } from "@/lib/ranks";
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from "@/components/ui/dropdown-menu";
import { Button } from "@/components/ui/button";

export interface AccountCardProps {
  platform: 'instagram' | 'tiktok';
  handle: string;
  displayName: string;
  avatarUrl: string;
  rank: RankTier;
  score: number;
  archetype?: string;
  vibe?: string;
  category?: string;
  analysisVersion: string;
  isClean: boolean;
  followers: string;
  postCount: string;
  medianViews: string;
  outliers: number;
  fanArchetype?: string;
}

export function AccountCard(props: AccountCardProps) {
  return (
    <Card className="group relative flex flex-col overflow-hidden transition-all hover:-translate-y-1 hover:shadow-2xl hover:shadow-indigo-500/10 hover:border-indigo-500/50">
      
      {/* Top Half: Image & Insignia */}
      <div className="relative flex justify-center pt-8 pb-10 bg-gradient-to-b from-muted/30 to-background">
        
        {/* Absolute Actions Menu */}
        <div className="absolute top-3 right-3 opacity-0 group-hover:opacity-100 transition-opacity">
           <DropdownMenu>
            <DropdownMenuTrigger className="inline-flex items-center justify-center whitespace-nowrap text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-1 disabled:pointer-events-none disabled:opacity-50 h-8 w-8 rounded-full bg-background/50 backdrop-blur-sm border shadow-sm hover:bg-background/80 hover:text-accent-foreground text-foreground">
                <MoreHorizontal className="h-4 w-4" />
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="w-48">
              <DropdownMenuItem><FileText className="mr-2 h-4 w-4"/> View analysis</DropdownMenuItem>
              <DropdownMenuItem><Edit3 className="mr-2 h-4 w-4"/> Edit tracking type</DropdownMenuItem>
              <DropdownMenuItem><RefreshCw className="mr-2 h-4 w-4"/> Refresh data</DropdownMenuItem>
              <DropdownMenuItem className="text-destructive"><Archive className="mr-2 h-4 w-4"/> Archive account</DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>

        <div className="relative">
          <img 
            src={props.avatarUrl} 
            alt={props.handle} 
            className="w-24 h-24 rounded-2xl object-cover border-4 border-background shadow-lg group-hover:scale-105 transition-transform duration-500" 
          />
          {/* Rank Overlay */}
          <div className="absolute -bottom-6 left-1/2 -translate-x-1/2 scale-[0.8] origin-top">
             <RankBadge rank={props.rank} score={props.score} />
          </div>
        </div>
      </div>

      {/* Detail Half */}
      <div className="flex flex-col flex-1 p-5 pt-8 gap-4 bg-background">
        
        {/* Header Strings */}
        <div className="flex flex-col items-center text-center">
          <a href={`https://${props.platform}.com/${props.handle.replace('@','')}`} target="_blank" rel="noopener noreferrer" 
             className="flex items-center gap-1 text-lg font-bold hover:text-indigo-400 transition-colors decoration-indigo-400/30 underline-offset-4 hover:underline">
            {props.handle} <ExternalLink className="h-3.5 w-3.5 text-muted-foreground" />
          </a>
          <span className="text-xs text-muted-foreground font-medium">{props.displayName}</span>
        </div>

        {/* Tag Pills */}
        <div className="flex flex-col gap-2 w-full">
           <div className="flex items-center justify-center gap-1.5 flex-wrap">
             {props.archetype && <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-purple-500/10 text-purple-400 border border-purple-500/20 tracking-wider uppercase">{props.archetype.replace('_',' ')}</span>}
             {props.vibe && <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-fuchsia-500/10 text-fuchsia-400 border border-fuchsia-500/20 tracking-wider uppercase">{props.vibe.replace('_',' ')}</span>}
           </div>
           <div className="flex items-center justify-center gap-1.5 flex-wrap">
             <span className="px-1.5 py-0.5 rounded text-[9px] font-bold bg-green-500/10 text-green-500 border border-green-500/20 uppercase tracking-widest">{props.analysisVersion}</span>
             {props.isClean && <span className="px-1.5 py-0.5 rounded text-[9px] font-bold bg-emerald-500/10 text-emerald-500 border border-emerald-500/20 uppercase tracking-widest">CLEAN</span>}
             {props.category && <span className="px-2 py-0.5 rounded text-[9px] font-bold bg-transparent text-cyan-400 border border-cyan-500/40 uppercase tracking-widest">{props.category.replace('_','/')}</span>}
           </div>
        </div>

        {/* Stats Strip */}
        <div className="grid grid-cols-4 mt-auto pt-4 border-t border-border/50 divide-x divide-border/50">
          <StatBox label="Flw." value={props.followers} />
          <StatBox label={props.platform === 'instagram' ? 'Reels' : 'Vids'} value={props.postCount} />
          <StatBox label="Med.View" value={props.medianViews} />
          <StatBox label="Outlier" value={props.outliers} isHighlight={props.outliers > 0} />
        </div>

        {/* Footer info */}
        {props.fanArchetype && (
          <div className="flex justify-center mt-2">
            <span className="text-[10px] text-muted-foreground font-medium flex items-center gap-1">
              <span className="w-1.5 h-1.5 rounded-full bg-indigo-500/50" /> Fan: {props.fanArchetype}
            </span>
          </div>
        )}

      </div>
    </Card>
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
