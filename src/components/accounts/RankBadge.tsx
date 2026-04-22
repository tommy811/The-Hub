import * as React from "react";
import { type RankTier, RANK_THEMES } from "@/lib/ranks";
import { cn } from "@/lib/utils";

export function RankBadge({ rank, score, className }: { rank: RankTier, score?: number, className?: string }) {
  const theme = RANK_THEMES[rank];
  
  return (
    <div className={cn("relative flex flex-col items-center", className)}>
      <div className={cn("relative z-10 flex items-center justify-center w-12 h-12 rounded-lg bg-background border-2 shadow-xl", theme.border, theme.glow)}>
        <svg viewBox="0 0 100 100" className="w-8 h-8 drop-shadow-md">
          {rank === 'diamond' && (
            <path d="M50 5 L95 50 L50 95 L5 50 Z" fill="url(#diamondGrad)" stroke="#fff" strokeWidth="2" />
          )}
          {rank === 'platinum' && (
            <path d="M50 10 L85 25 L85 75 L50 90 L15 75 L15 25 Z" fill="url(#platinumGrad)" stroke="#fff" strokeWidth="2" />
          )}
          {rank === 'gold' && (
             <path d="M50 15 L80 35 L80 65 L50 85 L20 65 L20 35 Z" fill="url(#goldGrad)" stroke="#fff" strokeWidth="2" />
          )}
          {rank === 'silver' && (
            <circle cx="50" cy="50" r="35" fill="url(#silverGrad)" stroke="#fff" strokeWidth="2" />
          )}
          {rank === 'bronze' && (
            <rect x="25" y="25" width="50" height="50" rx="10" fill="url(#bronzeGrad)" stroke="#fff" strokeWidth="2" />
          )}
          {rank === 'plastic' && (
            <path d="M30 30 L70 30 L60 70 L40 70 Z" fill="url(#plasticGrad)" stroke="#fff" strokeWidth="2" />
          )}
          
          <defs>
            <linearGradient id="diamondGrad" x1="0" y1="0" x2="1" y2="1"><stop offset="0%" stopColor="#00f2fe"/><stop offset="100%" stopColor="#4facfe"/></linearGradient>
            <linearGradient id="platinumGrad" x1="0" y1="0" x2="1" y2="1"><stop offset="0%" stopColor="#2af598"/><stop offset="100%" stopColor="#009efd"/></linearGradient>
            <linearGradient id="goldGrad" x1="0" y1="0" x2="1" y2="1"><stop offset="0%" stopColor="#f6d365"/><stop offset="100%" stopColor="#fda085"/></linearGradient>
            <linearGradient id="silverGrad" x1="0" y1="0" x2="1" y2="1"><stop offset="0%" stopColor="#e2ebf0"/><stop offset="100%" stopColor="#cfd9df"/></linearGradient>
            <linearGradient id="bronzeGrad" x1="0" y1="0" x2="1" y2="1"><stop offset="0%" stopColor="#b07c65"/><stop offset="100%" stopColor="#8b5a45"/></linearGradient>
            <linearGradient id="plasticGrad" x1="0" y1="0" x2="1" y2="1"><stop offset="0%" stopColor="#868f96"/><stop offset="100%" stopColor="#596164"/></linearGradient>
          </defs>
        </svg>
      </div>
      {score !== undefined && (
        <div className="absolute -bottom-3 z-20 flex px-2 py-0.5 rounded-full bg-background border shadow-sm text-xs font-bold leading-none">
          <span className={cn("bg-clip-text text-transparent bg-gradient-to-r", theme.gradient)}>
            {score.toFixed(1)}
          </span>
        </div>
      )}
    </div>
  );
}
