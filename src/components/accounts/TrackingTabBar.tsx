import { cn } from "@/lib/utils";

// 'managed', 'inspiration', 'competitor', 'candidate', 'hybrid_ai', 'coach', 'unreviewed'
export type TrackingType = 'managed' | 'inspiration' | 'competitor' | 'candidate' | 'hybrid_ai' | 'coach' | 'unreviewed' | 'scored';

const TABS: { id: TrackingType | 'all'; label: string; count: number; color?: string }[] = [
  { id: 'all', label: 'All', count: 142 },
  { id: 'managed', label: 'Managed', count: 4, color: 'bg-indigo-500' },
  { id: 'inspiration', label: 'Inspiration', count: 38, color: 'bg-blue-500' },
  { id: 'competitor', label: 'Competitor', count: 12, color: 'bg-rose-500' },
  { id: 'candidate', label: 'Candidate', count: 24, color: 'bg-amber-500' },
  { id: 'hybrid_ai', label: 'Hybrid AI', count: 6, color: 'bg-emerald-500' },
  { id: 'coach', label: 'Coach', count: 3, color: 'bg-teal-500' },
  { id: 'unreviewed', label: 'Unreviewed', count: 55, color: 'bg-slate-500' },
  { id: 'scored', label: 'Scored', count: 87, color: 'bg-cyan-500' },
];

interface TrackingTabBarProps {
  activeTab: string;
  onTabChange: (tab: string) => void;
}

export function TrackingTabBar({ activeTab, onTabChange }: TrackingTabBarProps) {
  return (
    <div className="flex items-center gap-1 border-b border-border/60 pb-px overflow-x-auto no-scrollbar mask-edges">
      {TABS.map((tab) => {
        const isActive = activeTab === tab.id;
        
        return (
          <button
            key={tab.id}
            onClick={() => onTabChange(tab.id)}
            className={cn(
              "flex flex-col items-center gap-1.5 px-4 pt-3 pb-2.5 min-w-max relative transition-all",
              isActive ? "text-foreground" : "text-muted-foreground hover:text-foreground/80 hover:bg-muted/30"
            )}
          >
            <div className="flex items-center gap-2">
              <span className="text-[13px] font-semibold">{tab.label}</span>
              <span className={cn(
                "flex items-center justify-center h-4 px-1.5 rounded text-[10px] font-bold tracking-tight text-white/90",
                isActive ? (tab.color || "bg-primary text-primary-foreground") : "bg-muted-foreground/30 text-muted-foreground"
              )}>
                {tab.count}
              </span>
            </div>
            
            {isActive && (
              <div className={cn("absolute bottom-0 left-0 right-0 h-[2px] rounded-t-full", tab.color || "bg-primary")} />
            )}
          </button>
        );
      })}
    </div>
  );
}
