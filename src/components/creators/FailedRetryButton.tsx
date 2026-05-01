// src/components/creators/FailedRetryButton.tsx
// Thin wrapper around RerunDiscoveryButton for the failed-state banner.
// Kept as a named export so existing imports don't break; the implementation
// lives in RerunDiscoveryButton (single source of truth).
"use client";

import { RerunDiscoveryButton } from "./RerunDiscoveryButton";

export function FailedRetryButton({ creatorId }: { creatorId: string }) {
  return <RerunDiscoveryButton creatorId={creatorId} variant="failed-state" />;
}
