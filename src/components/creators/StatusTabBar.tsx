// src/components/creators/StatusTabBar.tsx — Tab bar for creator onboarding status filtering
"use client";

import { cn } from "@/lib/utils";

interface StatusTabBarProps {
  counts: Record<string, number>;
  activeStatus: string;
  onStatusChange: (status: string) => void;
}

const TABS = [
  { id: "all", label: "All" },
  { id: "processing", label: "Processing" },
  { id: "ready", label: "Ready" },
  { id: "failed", label: "Failed" },
  { id: "archived", label: "Archived" },
];

export function StatusTabBar({ counts, activeStatus, onStatusChange }: StatusTabBarProps) {
  return (
    <div className="flex gap-2 p-1 bg-muted/40 rounded-xl overflow-x-auto border border-border/50 hide-scrollbar">
      {TABS.map((tab) => {
        const isActive = activeStatus === tab.id;
        const count = counts[tab.id] || 0;
        
        return (
          <button
            key={tab.id}
            onClick={() => onStatusChange(tab.id)}
            className={cn(
              "relative flex items-center justify-center gap-2 px-5 py-2.5 rounded-lg text-sm font-semibold transition-all whitespace-nowrap",
              isActive 
                ? "bg-background/80 text-foreground shadow-sm ring-1 ring-border border border-border/50" 
                : "text-muted-foreground hover:bg-muted/60 hover:text-foreground border border-transparent"
            )}
          >
            {tab.label}
            <span className={cn(
              "px-1.5 py-0.5 rounded-md text-[10px] font-bold min-w-[20px] text-center",
              isActive ? "bg-muted text-foreground" : "bg-muted/50 text-muted-foreground",
              tab.id === 'processing' && count > 0 && "bg-amber-500/20 text-amber-500 animate-pulse"
            )}>
              {count}
            </span>
          </button>
        );
      })}
    </div>
  );
}
