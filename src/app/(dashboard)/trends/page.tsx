"use client";

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Switch } from "@/components/ui/switch";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Plus, Settings2, BellRing, Activity, AlertTriangle, Play, ChevronRight, TrendingUp } from "lucide-react";
import { ScrollArea } from "@/components/ui/scroll-area";
import { cn } from "@/lib/utils";

// Mock Data
const LIVE_SIGNALS = [
  { id: "1", type: "velocity_spike", user: "@viking.barbie", desc: "Velocity spike detected: +450% above baseline.", time: "2m ago", severity: "high" },
  { id: "2", type: "outlier_post", user: "@jessica.fit", desc: "New outlier flagged (3.5x median views).", time: "15m ago", severity: "medium" },
  { id: "3", type: "emerging_archetype", user: "@luxury.life", desc: "AI detected shift to 'The Sovereign' archetype.", time: "1h ago", severity: "low" },
  { id: "4", type: "hook_pattern", user: "@crypto.bro", desc: "Hook pattern 'POV: you're...' highly re-occuring.", time: "3h ago", severity: "medium" },
  { id: "5", type: "cadence_change", user: "@kitchen.hacks", desc: "Posting cadence dropped by 45% this week.", time: "5h ago", severity: "medium" },
];

const ALERT_CONFIGS = [
  { id: "1", name: "Velocity Threshold: >200%", rule: "velocity_spike", enabled: true, targets: "All Managed" },
  { id: "2", name: "Outlier Posts (Competitors)", rule: "outlier_post", enabled: true, targets: "Competitors Only" },
  { id: "3", name: "Quality Score Drop < 60", rule: "score_drop", enabled: false, targets: "All Managed" },
  { id: "4", name: "New 'Body Worship' Post", rule: "vibe_match", enabled: true, targets: "Specific List" },
];

export default function TrendsAndAlertsPage() {
  return (
    <div className="flex flex-col gap-8 pb-10 h-[calc(100vh-6rem)]">
      
      {/* Header */}
      <div className="flex flex-col gap-4 md:flex-row md:items-end md:justify-between shrink-0">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Trends & Alerts</h1>
          <p className="text-muted-foreground mt-1 text-sm">Realtime event bus for velocity spikes, outliers, and automated notifications.</p>
        </div>
        <Button className="bg-indigo-600 hover:bg-indigo-500 font-semibold shadow-md hover:shadow-indigo-500/20">
          <Plus className="mr-2 h-4 w-4" /> New Alert Rule
        </Button>
      </div>

      {/* Two Column Layout */}
      <div className="grid grid-cols-1 lg:grid-cols-5 gap-8 min-h-0">
        
        {/* LEFT COLUMN: Live Signals Feed */}
        <div className="lg:col-span-3 flex flex-col gap-4 min-h-0 border rounded-2xl p-5 bg-card/50 shadow-sm relative overflow-hidden">
          {/* Subtle background glow */}
          <div className="absolute -top-40 -right-40 w-96 h-96 bg-indigo-500/10 rounded-full blur-[100px] pointer-events-none" />
          
          <div className="flex items-center justify-between z-10 shrink-0">
            <h2 className="text-lg font-bold flex items-center gap-2">
              <Activity className="h-5 w-5 text-indigo-400" /> Live Signal Feed
              <Badge variant="secondary" className="ml-2 bg-indigo-500/20 text-indigo-400 hover:bg-indigo-500/30 font-bold px-1.5 uppercase tracking-widest text-[10px]">Realtime</Badge>
            </h2>
            <Button variant="ghost" size="sm" className="h-8 text-xs text-muted-foreground">Dismiss All</Button>
          </div>
          
          <ScrollArea className="flex-1 -mx-2 px-2 z-10">
            <div className="flex flex-col gap-3 pb-4">
              {LIVE_SIGNALS.map((signal) => (
                <div key={signal.id} className="group relative flex items-start gap-4 p-4 rounded-xl border border-border/40 bg-background/60 hover:bg-background transition-colors hover:border-border/80">
                  
                  {/* Severity Indicator Line */}
                  <div className={cn(
                    "absolute left-0 top-3 bottom-3 w-[3px] rounded-r-md",
                    signal.severity === 'high' ? "bg-rose-500" : signal.severity === 'medium' ? "bg-amber-500" : "bg-blue-500"
                  )} />

                  {/* Icon mapped by type */}
                  <div className={cn(
                    "flex h-10 w-10 shrink-0 items-center justify-center rounded-full border",
                    signal.type === 'velocity_spike' ? "bg-rose-500/10 border-rose-500/20 text-rose-500" :
                    signal.type === 'outlier_post' ? "bg-amber-500/10 border-amber-500/20 text-amber-500" :
                    "bg-indigo-500/10 border-indigo-500/20 text-indigo-400"
                  )}>
                    {signal.type === 'velocity_spike' ? <TrendingUp className="h-4 w-4" /> :
                     signal.type === 'outlier_post' ? <AlertTriangle className="h-4 w-4" /> :
                     <Activity className="h-4 w-4" />}
                  </div>

                  {/* Content */}
                  <div className="flex flex-col flex-1 gap-1">
                    <div className="flex items-center justify-between">
                      <span className="font-semibold text-sm">{signal.user}</span>
                      <span className="text-xs text-muted-foreground font-medium">{signal.time}</span>
                    </div>
                    <p className="text-sm text-foreground/80 leading-snug">{signal.desc}</p>
                    
                    <div className="flex items-center gap-3 mt-2">
                       <span className="text-[10px] uppercase font-bold tracking-wider text-muted-foreground bg-muted px-2 py-0.5 rounded">
                         {signal.type.replace('_', ' ')}
                       </span>
                       <button className="text-xs font-semibold flex items-center gap-1 text-indigo-400 hover:text-indigo-300 transition-colors">
                         View Source <ChevronRight className="h-3 w-3" />
                       </button>
                    </div>
                  </div>
                  
                  {/* Right Action */}
                  <Button variant="ghost" size="icon" className="h-8 w-8 opacity-0 group-hover:opacity-100 transition-opacity absolute right-2 top-2">
                    <span className="text-lg font-light leading-none">×</span>
                  </Button>
                </div>
              ))}
            </div>
          </ScrollArea>
        </div>

        {/* RIGHT COLUMN: Alert Rules config */}
        <div className="lg:col-span-2 flex flex-col gap-4 min-h-0">
          <Card className="flex-1 flex flex-col min-h-0 bg-transparent border-none shadow-none">
            <CardHeader className="px-0 pt-0 shrink-0">
               <CardTitle className="text-lg flex items-center gap-2">
                 <BellRing className="h-5 w-5 text-foreground/70" /> Alert Configurations
               </CardTitle>
               <CardDescription>Rules run automatically every 15 minutes during ingestion.</CardDescription>
            </CardHeader>
            <CardContent className="px-0 flex-1 overflow-y-auto pr-2 pb-4 flex flex-col gap-4">
               {ALERT_CONFIGS.map((config) => (
                 <div key={config.id} className="flex flex-col p-4 rounded-xl border bg-card hover:bg-card/80 transition-colors">
                    <div className="flex items-center justify-between mb-3">
                      <h3 className="font-semibold text-sm">{config.name}</h3>
                      <Switch defaultChecked={config.enabled} className="data-[state=checked]:bg-indigo-500" />
                    </div>
                    
                    <div className="flex flex-col gap-2">
                      <div className="flex items-center justify-between text-xs">
                        <span className="text-muted-foreground font-medium">Target:</span>
                        <span className="font-semibold">{config.targets}</span>
                      </div>
                      <div className="flex items-center justify-between text-xs">
                        <span className="text-muted-foreground font-medium">Rule Type:</span>
                        <span className="font-mono text-[10px] bg-muted px-1.5 py-0.5 rounded text-muted-foreground">
                          {config.rule.toUpperCase()}
                        </span>
                      </div>
                    </div>

                    <div className="flex items-center gap-2 mt-4 pt-3 border-t border-border/50">
                       <Button variant="outline" size="sm" className="h-7 text-xs flex-1"><Settings2 className="mr-1.5 h-3 w-3"/> Edit Rule</Button>
                       <Button variant="secondary" size="icon" className="h-7 w-7"><Play className="h-3 w-3"/></Button>
                    </div>
                 </div>
               ))}
               
               <Button variant="outline" className="w-full mt-2 border-dashed h-12 text-muted-foreground hover:text-foreground">
                  View All Rules
               </Button>
            </CardContent>
          </Card>
        </div>

      </div>

    </div>
  );
}
