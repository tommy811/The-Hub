// src/components/accounts/PlatformIcon.tsx — Reusable platform icon renderer
import { getPlatform } from "@/lib/platforms";
import { cn } from "@/lib/utils";
import React from "react";

interface PlatformIconProps {
  platform: string | null;
  size?: number;
  showLabel?: boolean;
  className?: string;
}

export function PlatformIcon({ platform, size = 16, showLabel = false, className }: PlatformIconProps) {
  const meta = getPlatform(platform);
  const Icon = meta.icon;

  return (
    <div className={cn("inline-flex items-center gap-2", className)}>
      <Icon style={{ color: meta.color, width: size, height: size }} />
      {showLabel && <span className="text-sm">{meta.label}</span>}
    </div>
  );
}
