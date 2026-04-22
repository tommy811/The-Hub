"use client";

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { cn } from '@/lib/utils';
import { 
  BarChart, Boxes, Calendar, FileText, LayoutDashboard, Settings, 
  Users, Video, MessagesSquare, Wallet, Camera, MonitorPlay, HeartHandshake, FileBadge, Activity
} from 'lucide-react';
import { Badge } from '@/components/ui/badge';
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
          
          {/* DAILY */}
          <div className="flex flex-col gap-1">
            <h4 className="px-2 text-[10px] font-bold uppercase tracking-widest text-muted-foreground/70 mb-1">Daily</h4>
            <NavItem href="/" icon={LayoutDashboard} label="Command Center" currentPath={currentPath} />
            <NavItem href="#" icon={Wallet} label="Revenue Center" disabled />
            <NavItem href="#" icon={HeartHandshake} label="Fan Intel Hub" disabled />
            <NavItem href="#" icon={MessagesSquare} label="Chatter Workspace" disabled />
            <NavItem href="/content" icon={Video} label="Content Hub" currentPath={currentPath} />
            <NavItem href="#" icon={FileBadge} label="Tasks" disabled />
            <NavItem href="#" icon={FileText} label="Customs" disabled />
            <NavItem href="#" icon={Calendar} label="Shift Center" disabled />
          </div>

          {/* ANALYZE */}
          <div className="flex flex-col gap-1">
            <h4 className="px-2 text-[10px] font-bold uppercase tracking-widest text-muted-foreground/70 mb-1">Analyze</h4>
            <NavItem href="#" icon={Users} label="Fan Analytics" disabled />
            <NavItem href="#" icon={BarChart} label="Revenue" disabled />
            <NavItem href="/content" icon={Video} label="Content" currentPath={currentPath} />
            <NavItem href="/trends" icon={Activity} label="Trends & Alerts" currentPath={currentPath} />
            <NavItem href="#" icon={Wallet} label="Finance" disabled />
          </div>

          {/* CREATORS */}
          <div className="flex flex-col gap-1 mb-4">
            <h4 className="px-2 text-[10px] font-bold uppercase tracking-widest text-muted-foreground/70 mb-1">Creators</h4>
            <NavItem href="/creators" icon={Users} label="All Creators" currentPath={currentPath} badgeCount={2} badgeLabel="Discovering" />
            <NavItem href="/creators?type=managed" icon={Users} label="Managed" currentPath={currentPath} />
            <NavItem href="/creators?type=candidate" icon={Users} label="Candidates" currentPath={currentPath} />
            <NavItem href="/creators?type=competitor" icon={Users} label="Competitors" currentPath={currentPath} />
            <NavItem href="/creators?type=inspiration" icon={Users} label="Inspiration" currentPath={currentPath} />
          </div>

          {/* PLATFORMS */}
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
                <SubNavItem href="/platforms/instagram/classification" label="Classification" currentPath={currentPath} />
                <SubNavItem href="/platforms/instagram/analytics" label="Analytics" currentPath={currentPath} />
              </div>
            </div>

            {/* Expanded section for TikTok Intel */}
            <div className="flex flex-col mb-2 opacity-50">
               <div className="flex items-center gap-2.5 px-3 py-2 text-sm font-medium text-foreground rounded-md">
                <MonitorPlay className="h-4 w-4" />
                <span>TikTok Intel</span>
              </div>
            </div>
            
            <NavItem href="#" icon={Video} label="YouTube" disabled />
            <NavItem href="#" icon={HeartHandshake} label="Patreon" disabled />
          </div>

          {/* OPS */}
          <div className="flex flex-col gap-1 mb-8">
            <h4 className="px-2 text-[10px] font-bold uppercase tracking-widest text-muted-foreground/70 mb-1">Ops</h4>
            <NavItem href="/admin" icon={Settings} label="Admin" currentPath={currentPath} />
          </div>

        </nav>
      </ScrollArea>
    </div>
  );
}

function NavItem({ href, icon: Icon, label, disabled, currentPath, badgeCount, badgeLabel }: { href: string; icon: any; label: string; disabled?: boolean; currentPath?: string; badgeCount?: number; badgeLabel?: string }) {
  const isActive = currentPath === href && !disabled;
  
  if (disabled) {
    return (
      <div className="flex items-center justify-between px-3 py-2 text-sm font-medium text-muted-foreground/50 opacity-60 cursor-not-allowed">
        <div className="flex items-center gap-2.5">
          <Icon className="h-4 w-4" />
          <span>{label}</span>
        </div>
        <Badge variant="outline" className="text-[8px] h-4 px-1 py-0 uppercase border-muted-foreground/30 text-muted-foreground/60 font-semibold bg-transparent">Soon</Badge>
      </div>
    );
  }

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
      {badgeCount !== undefined && badgeCount > 0 && (
         <div className="flex items-center gap-1.5">
           {badgeLabel && <span className="text-[10px] font-bold uppercase tracking-widest text-indigo-400 opacity-70 group-hover:opacity-100 transition-opacity">{badgeLabel}</span>}
           <Badge className="h-5 px-1.5 bg-indigo-500/20 text-indigo-400 hover:bg-indigo-500/30 border-indigo-500/30 font-bold tabular-nums">
             {badgeCount}
           </Badge>
         </div>
      )}
    </Link>
  );
}

function SubNavItem({ href, label, currentPath }: { href: string; label: string; currentPath?: string }) {
  const isActive = currentPath === href;
  return (
    <Link 
      href={href} 
      className={cn(
        "flex items-center px-4 py-1.5 text-[13px] rounded-md transition-all relative",
        isActive ? "text-primary font-semibold" : "text-muted-foreground hover:text-primary hover:bg-muted/50"
      )}
    >
      {isActive && <div className="absolute -left-[5px] w-2 h-2 rounded-full border-[2px] border-background bg-indigo-500" />}
      {label}
    </Link>
  );
}
