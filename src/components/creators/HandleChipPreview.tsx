// src/components/creators/HandleChipPreview.tsx — Renders parsed handle state for bulk import preview
import { X, AlertCircle } from "lucide-react";
import { type ParsedHandle } from "@/lib/handleParser";
import { PLATFORMS } from "@/lib/platforms";
import { PlatformIcon } from "@/components/accounts/PlatformIcon";

interface HandleChipPreviewProps {
  handle: ParsedHandle;
  onPlatformAssign: (platform: string) => void;
  onRemove?: () => void;
}

export function HandleChipPreview({ handle, onPlatformAssign, onRemove }: HandleChipPreviewProps) {
  if (handle.isDuplicate) {
    return (
      <div className="inline-flex items-center gap-2 rounded-full border border-red-900/50 bg-red-900/10 px-3 py-1 text-sm text-red-500/70 line-through">
        <span className="truncate max-w-[200px]">{handle.handle || handle.rawInput}</span>
        <span className="text-xs ml-1">— already in workspace</span>
        {onRemove && (
          <button onClick={onRemove} className="ml-1 hover:text-red-400">
            <X className="h-3 w-3" />
          </button>
        )}
      </div>
    );
  }

  if (handle.needsPlatformHint) {
    return (
      <div className="inline-flex items-center gap-2 rounded-full border border-amber-500/50 bg-amber-500/10 px-3 py-1 text-sm text-amber-500">
        <AlertCircle className="h-3 w-3 shrink-0" />
        <span className="truncate max-w-[150px] font-medium">{handle.handle || handle.rawInput}</span>
        
        {/* Simple inline native select since shadcn Select might be too heavy for many chips */}
        <select 
          className="ml-2 bg-transparent text-xs text-amber-500 outline-none w-[100px] cursor-pointer"
          onChange={(e) => onPlatformAssign(e.target.value)}
          defaultValue=""
        >
          <option value="" disabled>Select platform...</option>
          {Object.entries(PLATFORMS).map(([key, meta]) => (
            <option key={key} value={key} className="bg-background text-foreground">{meta.label}</option>
          ))}
        </select>
        
        {onRemove && (
          <button onClick={onRemove} className="ml-1 hover:text-amber-400">
            <X className="h-3 w-3" />
          </button>
        )}
      </div>
    );
  }

  return (
    <div className="inline-flex items-center gap-2 rounded-full border border-emerald-500/50 bg-emerald-500/10 px-3 py-1 text-sm text-emerald-400">
      <PlatformIcon platform={handle.platform} size={14} />
      <span className="truncate max-w-[200px] font-medium">{handle.handle}</span>
      {onRemove && (
        <button onClick={onRemove} className="ml-1 hover:text-emerald-300">
          <X className="h-3 w-3" />
        </button>
      )}
    </div>
  );
}
