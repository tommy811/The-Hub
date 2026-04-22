import { cn } from "@/lib/utils";
import { type RankTier, RANK_THEMES } from "@/lib/ranks";
import { Badge } from "@/components/ui/badge";

interface RankFilterChipsProps {
  selectedRanks: RankTier[];
  counts: Record<string, number>;
  onToggle: (rank: RankTier | 'all') => void;
}

const ALL_RANKS: RankTier[] = ['diamond', 'platinum', 'gold', 'silver', 'bronze', 'plastic'];

export function RankFilterChips({ selectedRanks, counts, onToggle }: RankFilterChipsProps) {
  const isAll = selectedRanks.length === 0;

  return (
    <div className="flex flex-wrap items-center gap-2">
      <button
        onClick={() => onToggle('all')}
        className={cn(
          "px-3 py-1.5 text-sm font-medium rounded-full border transition-all",
          isAll ? "bg-primary text-primary-foreground border-primary" : "bg-card text-muted-foreground border-border hover:border-muted-foreground/30"
        )}
      >
        All Ranks <span className="opacity-60 ml-1 font-normal">{counts['all'] || 0}</span>
      </button>

      {ALL_RANKS.map((rank) => {
        const theme = RANK_THEMES[rank];
        const isSelected = selectedRanks.includes(rank);
        
        return (
          <button
            key={rank}
            onClick={() => onToggle(rank)}
            className={cn(
              "flex items-center gap-2 px-3 py-1.5 text-sm font-semibold rounded-full border transition-all relative overflow-hidden group",
              isSelected 
                ? [theme.border, theme.bg, theme.glow, "ring-1 ring-inset", `ring-[${theme.text}]`]
                : "bg-card border-border hover:border-muted-foreground/30 text-muted-foreground hover:text-foreground"
            )}
          >
            {/* Very minimal inline representation of the SVG rank for the chip */}
            <div className={cn("w-2 h-2 rounded-full", `bg-gradient-to-r ${theme.gradient}`)} />
            
            <span className={cn("capitalize tracking-tight", isSelected ? theme.text : "")}>
              {rank}
            </span>
            
            <Badge 
               variant="outline" 
               className={cn("h-5 px-1.5 min-w-5 justify-center py-0 text-[10px] bg-background/50 backdrop-blur-sm ml-1", isSelected ? theme.text : "")}
            >
              {counts[rank] || 0}
            </Badge>
          </button>
        );
      })}
    </div>
  );
}
