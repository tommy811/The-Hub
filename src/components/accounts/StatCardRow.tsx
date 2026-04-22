import { Card } from "@/components/ui/card";
import { Users, Video, Activity, FileText } from "lucide-react";
import { cn } from "@/lib/utils";

interface StatCardProps {
  label: string;
  value: string | number;
  icon: any;
  colorClass: string;
}

export function StatCardRow() {
  return (
    <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
      <StatCard 
        label="In This Tab" 
        value="142" 
        icon={Users} 
        colorClass="text-indigo-500 bg-indigo-500/10 border-indigo-500/20" 
      />
      <StatCard 
        label="With Reels" 
        value="87" 
        icon={Video} 
        colorClass="text-emerald-500 bg-emerald-500/10 border-emerald-500/20" 
      />
      <StatCard 
        label="Avg Followers" 
        value="450K" 
        icon={Activity} 
        colorClass="text-blue-500 bg-blue-500/10 border-blue-500/20" 
      />
      <StatCard 
        label="LLM Scored" 
        value="112" 
        icon={FileText} 
        colorClass="text-amber-500 bg-amber-500/10 border-amber-500/20" 
      />
    </div>
  );
}

function StatCard({ label, value, icon: Icon, colorClass }: StatCardProps) {
  return (
    <Card className="flex items-center gap-4 p-4 hover:bg-muted/10 transition-colors cursor-default border-border/50 shadow-sm">
      <div className={cn("flex h-12 w-12 shrink-0 items-center justify-center rounded-xl border", colorClass)}>
        <Icon className="h-5 w-5" />
      </div>
      <div className="flex flex-col">
        <span className="text-2xl font-bold tracking-tight">{value}</span>
        <span className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">{label}</span>
      </div>
    </Card>
  );
}
