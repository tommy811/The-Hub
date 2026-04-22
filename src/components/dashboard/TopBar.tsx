import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { Search } from "lucide-react";
import { Input } from "@/components/ui/input";

export function TopBar() {
  return (
    <header className="flex h-16 shrink-0 items-center gap-4 border-b bg-background px-6 justify-between z-10 sticky top-0">
      
      <div className="flex flex-1 items-center gap-4">
        <div className="relative w-full max-w-sm">
          <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
          <Input 
            type="search" 
            placeholder="Search username..." 
            className="w-full bg-muted/50 pl-9 border-none focus-visible:ring-1 focus-visible:ring-indigo-500/50" 
          />
        </div>
      </div>

      <div className="flex items-center gap-4 pl-4 border-l border-border/50">
        
        {/* Workspace Team Pills */}
        <div className="flex -space-x-2">
           <Avatar className="h-8 w-8 ring-2 ring-background border border-border">
             <AvatarImage src="https://i.pravatar.cc/150?u=1" />
             <AvatarFallback>AN</AvatarFallback>
           </Avatar>
           <Avatar className="h-8 w-8 ring-2 ring-background border border-border">
             <AvatarImage src="https://i.pravatar.cc/150?u=2" />
             <AvatarFallback>JA</AvatarFallback>
           </Avatar>
        </div>

        <div className="flex items-center gap-2 cursor-pointer hover:bg-muted/50 py-1.5 px-3 rounded-full transition-colors border border-transparent hover:border-border">
           <Avatar className="h-7 w-7 border border-indigo-500/50">
             <AvatarImage src="https://i.pravatar.cc/150?u=3" />
             <AvatarFallback className="bg-indigo-500/20 text-indigo-400">FR</AvatarFallback>
           </Avatar>
           <div className="flex flex-col">
              <span className="text-[10px] font-bold uppercase tracking-wider text-muted-foreground leading-none">Admin</span>
              <span className="text-xs font-semibold leading-none mt-1">Franklin</span>
           </div>
        </div>

      </div>
      
    </header>
  );
}
