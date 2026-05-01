// src/components/creators/BannerWithFallback.tsx
// Renders a creator banner image (banner_url overrides cover_image_url) with
// graceful fallback when the URL 404s or expires (IG-CDN URLs are short-lived).
// Uses a plain <img> instead of next/image because banners come from arbitrary
// external hosts and we don't want to maintain remotePatterns for each one.
"use client";

import { useState } from "react";

interface BannerWithFallbackProps {
  bannerUrl: string | null;
  coverImageUrl: string | null;
}

export function BannerWithFallback({ bannerUrl, coverImageUrl }: BannerWithFallbackProps) {
  const [imgError, setImgError] = useState(false);
  const src = bannerUrl || coverImageUrl;
  if (!src || imgError) return null;

  return (
    <div className="relative w-full h-32 -mt-4 -mx-4 rounded-t-xl overflow-hidden bg-muted/20">
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img
        src={src}
        alt=""
        className="w-full h-full object-cover"
        onError={() => setImgError(true)}
      />
      <div className="absolute inset-0 bg-gradient-to-t from-background/80 to-transparent" />
    </div>
  );
}
