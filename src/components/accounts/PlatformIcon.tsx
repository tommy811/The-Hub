// src/components/accounts/PlatformIcon.tsx — Reusable platform icon renderer
import { resolvePlatform } from "@/lib/platforms";
import { cn } from "@/lib/utils";
import React from "react";

interface PlatformIconProps {
  platform: string | null;
  /** Optional URL — enables hostname-based fallback when DB platform is 'other'
   *  (e.g. Reddit, Threads, Bluesky, Snapchat — platforms not in the Postgres enum). */
  url?: string | null;
  size?: number;
  showLabel?: boolean;
  className?: string;
}

export function PlatformIcon({ platform, url, size = 16, showLabel = false, className }: PlatformIconProps) {
  const meta = resolvePlatform(platform, url ?? null);
  const Icon = meta.icon;

  // Both lucide-react components and react-icons (Si*/Fa*) components accept
  // className + style. Setting width/height via style keeps the contract identical
  // across the two icon sources, and `color` flows through `currentColor` on the SVG.
  return (
    <div className={cn("inline-flex items-center gap-2", className)}>
      <Icon style={{ color: meta.color, width: size, height: size }} />
      {showLabel && <span className="text-sm">{meta.label}</span>}
    </div>
  );
}
