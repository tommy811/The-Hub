"use client";

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { cn } from '@/lib/utils';
import {
  Boxes, LayoutDashboard,
  Users, Camera, MonitorPlay, Activity, Library
} from 'lucide-react';
import { ScrollArea } from '@/components/ui/scroll-area';

export function Sidebar() {
  const currentPath = usePathname();
  
  return (
    <div className="flex h-full w-[260px] flex-col border-r bg-card/50 backdrop-blur-sm">
      <div className="flex h-14 items-center pl-6 pr-4 shrink-0 mt-2">
        <Link href="/" className="flex items-center gap-2 font-bold tracking-tight text-primary hover:text-primary/80 transition-colors">
          <Boxes className="h-5 w-5" />
          <span>Agency CØMMAND</span>
        </Link>
      </div>

      <ScrollArea className="flex-1 overflow-y-auto mt-4 pb-12">
        <nav className="flex flex-col gap-6 px-4">
          
          <div className="flex flex-col gap-1">
            <h4 className="px-2 text-[10px] font-bold uppercase tracking-widest text-muted-foreground/70 mb-1">Command</h4>
            <NavItem href="/" icon={LayoutDashboard} label="Command Center" currentPath={currentPath} />
            <NavItem href="/creators" icon={Users} label="Creators" currentPath={currentPath} />
          </div>

          <div className="flex flex-col gap-1">
            <h4 className="px-2 text-[10px] font-bold uppercase tracking-widest text-muted-foreground/70 mb-1">Content Intel</h4>
            <NavItem href="/scraped-content" icon={Library} label="Content Library" currentPath={currentPath} />
            <NavItem href="/trends" icon={Activity} label="Audio Trends" currentPath={currentPath} />
          </div>

          <div className="flex flex-col gap-1">
            <h4 className="px-2 text-[10px] font-bold uppercase tracking-widest text-muted-foreground/70 mb-1">Platforms</h4>
            
            {/* Expanded section for Instagram Intel */}
            <div className="flex flex-col mb-2">
              <div className="flex items-center gap-2.5 px-3 py-2 text-sm font-medium text-foreground rounded-md">
                <Camera className="h-4 w-4" />
                <span>Instagram Intel</span>
              </div>
              <div className="ml-[26px] flex flex-col pl-2 border-l border-border/50 gap-1 mt-1">
                <SubNavItem href="/platforms/instagram/accounts" label="Accounts" currentPath={currentPath} />
                <SubNavItem href="/platforms/instagram/outliers" label="Outliers" currentPath={currentPath} />
              </div>
            </div>

            {/* Expanded section for TikTok Intel */}
            <div className="flex flex-col mb-2">
              <div className="flex items-center gap-2.5 px-3 py-2 text-sm font-medium text-foreground rounded-md">
                <MonitorPlay className="h-4 w-4" />
                <span>TikTok Intel</span>
              </div>
              <div className="ml-[26px] flex flex-col pl-2 border-l border-border/50 gap-1 mt-1">
                <SubNavItem href="/platforms/tiktok/accounts" label="Accounts" currentPath={currentPath} />
                <SubNavItem href="/platforms/tiktok/outliers" label="Outliers" currentPath={currentPath} />
              </div>
            </div>
          </div>

        </nav>
      </ScrollArea>
    </div>
  );
}

function NavItem({ href, icon: Icon, label, currentPath }: { href: string; icon: any; label: string; currentPath?: string }) {
  const isActive = currentPath === href;

  return (
    <Link 
      href={href} 
      className={cn(
        "flex items-center justify-between px-3 py-2 text-sm font-medium rounded-md transition-all group relative",
        isActive ? "text-primary bg-primary/10" : "text-muted-foreground hover:text-primary hover:bg-muted"
      )}
    >
      {isActive && <div className="absolute left-0 top-1 bottom-1 w-[3px] bg-indigo-500 rounded-r-full" />}
      <div className="flex items-center gap-2.5">
        <Icon className={cn("h-4 w-4", isActive ? "text-indigo-400" : "group-hover:text-foreground")} />
        <span className={isActive ? "font-semibold" : ""}>{label}</span>
      </div>
    </Link>
  );
}

function SubNavItem({
  href,
  label,
  currentPath,
}: {
  href: string
  label: string
  currentPath?: string
}) {
  const isActive = currentPath === href
  return (
    <Link
      href={href}
      className={cn(
        "flex items-center justify-between px-4 py-1.5 text-[13px] rounded-md transition-all relative",
        isActive
          ? "text-primary font-semibold"
          : "text-muted-foreground hover:text-primary hover:bg-muted/50"
      )}
    >
      {isActive && (
        <div className="absolute -left-[5px] w-2 h-2 rounded-full border-[2px] border-background bg-indigo-500" />
      )}
      <span>{label}</span>
    </Link>
  )
}
