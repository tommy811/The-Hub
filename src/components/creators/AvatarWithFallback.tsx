"use client";

import Image from "next/image";
import { useState } from "react";
import { proxiedAvatarUrl } from "@/lib/avatar-url";
import { cn } from "@/lib/utils";

interface AvatarWithFallbackProps {
  avatarUrl: string | null;
  name: string;
  gradient: string;
  className?: string;
  textClassName?: string;
}

export function AvatarWithFallback({ avatarUrl, name, gradient, className, textClassName }: AvatarWithFallbackProps) {
  const [imgError, setImgError] = useState(false);
  const imageUrl = proxiedAvatarUrl(avatarUrl);
  const showFallback = !imageUrl || imgError;

  return (
    <div className={cn("relative flex items-center justify-center bg-gradient-to-br overflow-hidden", gradient, className)}>
      {!showFallback ? (
        <Image
          src={imageUrl}
          alt=""
          fill
          sizes="96px"
          unoptimized
          className="w-full h-full object-cover"
          onError={() => setImgError(true)}
        />
      ) : (
        <span className={cn("font-black text-white/90", textClassName)}>
          {name.substring(0, 2).toUpperCase()}
        </span>
      )}
    </div>
  );
}
