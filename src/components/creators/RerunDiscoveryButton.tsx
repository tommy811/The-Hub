// src/components/creators/RerunDiscoveryButton.tsx
// Single source of truth for the "Re-run Discovery" action. Used by:
//   - The creator detail page header (variant="header")
//   - The failed-state inline banner on the same page (variant="failed-state")
// CreatorCard renders its own visually-distinct retry pill in the failed
// card body — see CreatorCard.tsx — but the *label* now matches.
"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";
import { retryCreatorDiscovery } from "@/app/(dashboard)/creators/actions";

type Variant = "header" | "failed-state";

export function RerunDiscoveryButton({
  creatorId,
  isProcessing = false,
  variant = "header",
}: {
  creatorId: string;
  isProcessing?: boolean;
  variant?: Variant;
}) {
  const [loading, setLoading] = useState(false);
  const router = useRouter();

  const handleClick = async () => {
    if (loading || isProcessing) return;
    setLoading(true);
    const r = await retryCreatorDiscovery(creatorId);
    setLoading(false);
    if (!r.ok) {
      toast.error("Re-run discovery failed", { description: r.error });
      return;
    }
    toast.success("Discovery re-queued");
    router.refresh();
  };

  const spinning = loading || isProcessing;

  const label = loading
    ? "Starting…"
    : isProcessing
    ? "Discovering…"
    : "Re-run Discovery";

  if (variant === "failed-state") {
    return (
      <Button
        size="sm"
        variant="outline"
        disabled={spinning}
        onClick={handleClick}
        className="border-red-900/50 hover:bg-red-900/20 text-red-400 shrink-0"
      >
        <RefreshCw className={`h-4 w-4 mr-2 ${spinning ? "animate-spin" : ""}`} />
        {label}
      </Button>
    );
  }

  return (
    <Button
      variant="outline"
      size="sm"
      disabled={spinning}
      onClick={handleClick}
      className="h-8"
    >
      <RefreshCw className={`h-4 w-4 mr-2 ${spinning ? "animate-spin" : ""}`} />
      {label}
    </Button>
  );
}
