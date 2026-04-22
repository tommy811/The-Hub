// src/components/creators/CreatorCard.tsx — Creator grid card
"use client";

import { type ReactNode } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { MoreHorizontal, FileText, Edit3, Archive, Loader2, AlertCircle, RefreshCw } from "lucide-react";
import { Card } from "@/components/ui/card";
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from "@/components/ui/dropdown-menu";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";
import { PlatformIcon } from "@/components/accounts/PlatformIcon";
import { Badge } from "@/components/ui/badge";
import Link from "next/link";
import { cn } from "@/lib/utils";

interface CreatorCardProps {
  id: string;
  canonicalName: string;
  slug: string;
  avatarUrl?: string;
  primaryPlatform: string;
  status: 'processing' | 'ready' | 'failed';
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

export function CreatorCard({
  id, canonicalName, slug, avatarUrl, primaryPlatform, status, 
  trackingType, monetizationModel, tags, knownUsernames = [],
  accountCounts, totalFollowers, updatedAgo, hasMergeCandidate, errorMessage
}: CreatorCardProps) {
  
  // Shared base layout container
  const Container = ({ children, className }: { children: ReactNode, className?: string }) => (
    <Card className={cn(
      "group relative flex flex-col h-[320px] overflow-hidden transition-all hover:-translate-y-1 hover:shadow-2xl hover:shadow-indigo-500/10 border border-border/50 bg-[#13131A] rounded-xl",
      className
    )}>
      {children}
    </Card>
  );

  return (
    <AnimatePresence mode="wait">
      {status === 'processing' && (
        <motion.div key="processing" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
          <Container className="opacity-60 pointer-events-none">
             <div className="absolute top-4 right-4 text-indigo-400">
               <Loader2 className="h-5 w-5 animate-spin" />
             </div>
             <div className="flex flex-col items-center justify-center p-6 pt-10 gap-4">
                <div className="w-20 h-20 rounded-xl bg-muted/30 animate-pulse" />
                <div className="flex flex-col items-center gap-2 w-full">
                  <div className="h-5 w-3/4 bg-muted/40 animate-pulse rounded" />
                  <div className="h-3 w-1/2 bg-muted/30 animate-pulse rounded" />
                </div>
                <div className="text-xs text-indigo-400/80 font-medium mt-4">Discovering {canonicalName}…</div>
             </div>
             <div className="mt-auto p-4 border-t border-border/30 flex gap-2">
               <div className="h-4 w-1/4 bg-muted/30 animate-pulse rounded" />
               <div className="h-4 w-1/4 bg-muted/30 animate-pulse rounded" />
             </div>
          </Container>
        </motion.div>
      )}

      {status === 'failed' && (
        <motion.div key="failed" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
          <Container className="border-red-900/60 shadow-lg shadow-red-900/10">
             <div className="absolute top-4 right-4 text-red-500">
               <AlertCircle className="h-5 w-5" />
             </div>
             <div className="flex flex-col items-center p-6 pt-10 gap-4">
                <div className="w-20 h-20 rounded-xl bg-red-900/20 flex items-center justify-center border border-red-900/50">
                   <PlatformIcon platform={primaryPlatform} size={24} className="text-red-500 opacity-50" />
                </div>
                <div className="text-center">
                  <div className="font-semibold text-lg">{canonicalName}</div>
                  <div className="text-xs text-red-400/80 mt-2 truncate w-full max-w-[200px]" title={errorMessage}>
                    {errorMessage || "Discovery failed"}
                  </div>
                </div>
             </div>
             <div className="mt-auto p-4 border-t border-red-900/30 flex justify-center">
               <button className="flex items-center gap-2 text-xs font-semibold text-red-400 hover:text-red-300 border border-red-900/50 rounded-full px-4 py-1.5 transition-colors">
                 <RefreshCw className="h-3 w-3" /> Retry Discovery
               </button>
             </div>
          </Container>
        </motion.div>
      )}

      {status === 'ready' && (
        <motion.div key="ready" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
          <Container className="hover:border-indigo-500/50">
            {hasMergeCandidate && (
              <div className="absolute top-3 right-3 z-10">
                <Badge className="bg-amber-500/20 text-amber-500 hover:bg-amber-500/30 border-amber-500/30 font-bold uppercase tracking-widest text-[9px]">
                  ⚠ Duplicate?
                </Badge>
              </div>
            )}
            
            <div className="absolute top-3 left-3 opacity-0 group-hover:opacity-100 transition-opacity z-10">
               <DropdownMenu>
                <DropdownMenuTrigger className="inline-flex items-center justify-center h-8 w-8 rounded-full bg-background/80 backdrop-blur-sm border border-border/50 shadow-sm hover:bg-background text-foreground">
                    <MoreHorizontal className="h-4 w-4" />
                </DropdownMenuTrigger>
                <DropdownMenuContent align="start" className="w-48">
                  <DropdownMenuItem className="p-0">
                    <Link href={`/creators/${slug}`} className="cursor-pointer flex w-full items-center px-2 py-1.5">
                      <FileText className="mr-2 h-4 w-4"/> View Profile
                    </Link>
                  </DropdownMenuItem>
                  <DropdownMenuItem><Edit3 className="mr-2 h-4 w-4"/> Edit Tracking</DropdownMenuItem>
                  <DropdownMenuItem><RefreshCw className="mr-2 h-4 w-4"/> Re-run Discovery</DropdownMenuItem>
                  <DropdownMenuItem className="text-red-500 focus:bg-red-500/10 focus:text-red-500"><Archive className="mr-2 h-4 w-4"/> Archive</DropdownMenuItem>
                </DropdownMenuContent>
              </DropdownMenu>
            </div>

            <div className="flex flex-col items-center p-6 pb-2 relative">
              <div className="w-20 h-20 rounded-2xl border-4 border-background shadow-xl overflow-hidden bg-muted flex items-center justify-center shrink-0">
                {avatarUrl ? (
                  <img src={avatarUrl} alt="" className="w-full h-full object-cover" />
                ) : (
                  <span className="text-xl font-black text-muted-foreground">{canonicalName.substring(0, 2).toUpperCase()}</span>
                )}
              </div>
              
              <Link href={`/creators/${slug}`} className="mt-3 font-bold text-lg hover:text-indigo-400 transition-colors">
                {canonicalName}
              </Link>
              
              {knownUsernames.length > 0 && (
                <div className="text-[10px] text-muted-foreground/70 mt-1 uppercase tracking-widest max-w-[200px] truncate text-center">
                  also: {knownUsernames.slice(0, 2).join(', ')} {knownUsernames.length > 2 && `+${knownUsernames.length - 2} more`}
                </div>
              )}
            </div>

            <div className="px-5 flex flex-col gap-3 flex-1">
              <div className="flex justify-center -mt-1 gap-1">
                <Badge variant="outline" className={cn(
                  "text-[10px] uppercase font-bold",
                  trackingType === 'managed' ? "text-indigo-400 border-indigo-400/30 bg-indigo-500/10" :
                  trackingType === 'competitor' ? "text-rose-400 border-rose-400/30 bg-rose-500/10" :
                  trackingType === 'candidate' ? "text-amber-400 border-amber-400/30 bg-amber-500/10" :
                  "text-violet-400 border-violet-400/30 bg-violet-500/10"
                )}>
                  {trackingType.replace('_', ' ')}
                </Badge>
                {monetizationModel && monetizationModel !== 'unknown' && (
                  <Badge variant="outline" className="text-[10px] uppercase font-bold text-muted-foreground border-border/50">
                    {monetizationModel.replace('_', ' ')}
                  </Badge>
                )}
              </div>
              
              {tags.length > 0 && (
                <div className="flex flex-wrap items-center justify-center gap-1">
                  {tags.slice(0, 3).map((t, i) => (
                    <span key={i} className="text-[10px] text-muted-foreground bg-muted/40 px-1.5 rounded">{t}</span>
                  ))}
                  {tags.length > 3 && <span className="text-[10px] text-muted-foreground bg-muted/40 px-1.5 rounded">+{tags.length - 3}</span>}
                </div>
              )}
              
              <div className="mt-auto grid grid-cols-4 gap-1 mb-2">
                 <TooltipProvider>
                   {Object.entries({
                     Social: accountCounts.social || 0,
                     Monetization: accountCounts.monetization || 0,
                     Links: accountCounts.link_in_bio || 0,
                     Msg: accountCounts.messaging || 0
                   }).map(([label, count], i) => (
                      <Tooltip key={i}>
                        <TooltipTrigger className={cn(
                            "flex flex-col items-center justify-center p-1 rounded-md border text-center transition-colors cursor-default outline-none",
                            count > 0 ? "bg-muted/30 border-border/50 text-foreground" : "border-transparent text-muted-foreground/50"
                          )}>
                            <span className="text-[10px] uppercase tracking-wider font-bold opacity-70 mb-0.5">{label}</span>
                            <span className="text-xs font-semibold">{count}</span>
                        </TooltipTrigger>
                        <TooltipContent side="bottom" className="text-xs">
                          {count} {label} account(s) found
                        </TooltipContent>
                      </Tooltip>
                   ))}
                 </TooltipProvider>
              </div>
            </div>

            <div className="p-3 bg-muted/10 border-t border-border/50 flex items-center justify-between text-xs px-5">
              <div className="flex items-center gap-1.5 font-medium">
                <PlatformIcon platform={primaryPlatform} size={14} className="text-muted-foreground" />
                <span className="text-foreground">{totalFollowers} flwrs</span>
              </div>
              <span className="text-muted-foreground/60 text-[10px] uppercase tracking-widest font-semibold">{updatedAgo}</span>
            </div>
          </Container>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
