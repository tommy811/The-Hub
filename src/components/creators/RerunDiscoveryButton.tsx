"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { retryCreatorDiscovery } from "@/app/(dashboard)/creators/actions";

export function RerunDiscoveryButton({ creatorId, isProcessing }: { creatorId: string; isProcessing: boolean }) {
  const [loading, setLoading] = useState(false);
  const router = useRouter();

  const handleClick = async () => {
    if (loading || isProcessing) return;
    setLoading(true);
    try {
      await retryCreatorDiscovery(creatorId);
      router.refresh();
    } catch (e) {
      console.error("Re-run discovery failed:", e);
    } finally {
      setLoading(false);
    }
  };

  const spinning = loading || isProcessing;

  return (
    <Button variant="outline" size="sm" disabled={spinning} onClick={handleClick} className="h-8">
      <RefreshCw className={`h-4 w-4 mr-2 ${spinning ? 'animate-spin' : ''}`} />
      {loading ? 'Starting…' : isProcessing ? 'Discovering…' : 'Re-run Discovery'}
    </Button>
  );
}
