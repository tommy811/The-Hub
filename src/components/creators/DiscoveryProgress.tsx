"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { getDiscoveryProgress } from "@/app/(dashboard)/creators/actions";

interface DiscoveryProgressProps {
  runId: string;
  pollIntervalMs?: number;
  className?: string;
}

// Polls discovery_runs every ~3s while a discovery pipeline is in flight.
// When the row's status flips out of pending/processing the parent route is
// refreshed so the card or HQ banner re-renders into its terminal state.
export function DiscoveryProgress({
  runId,
  pollIntervalMs = 3000,
  className,
}: DiscoveryProgressProps) {
  const [pct, setPct] = useState(0);
  const [label, setLabel] = useState<string | null>(null);
  const router = useRouter();
  const cancelled = useRef(false);

  useEffect(() => {
    cancelled.current = false;
    let timer: ReturnType<typeof setTimeout> | null = null;

    const tick = async () => {
      const r = await getDiscoveryProgress(runId);
      if (cancelled.current) return;
      if (r.ok) {
        setPct(r.data.progressPct);
        setLabel(r.data.progressLabel);
        if (r.data.status !== "pending" && r.data.status !== "processing") {
          router.refresh();
          return;
        }
      }
      timer = setTimeout(tick, pollIntervalMs);
    };

    tick();
    return () => {
      cancelled.current = true;
      if (timer) clearTimeout(timer);
    };
  }, [runId, pollIntervalMs, router]);

  return (
    <div className={`flex flex-col gap-1.5 w-full ${className ?? ""}`}>
      <div className="flex items-center justify-between gap-2 text-[10px] uppercase tracking-widest font-semibold text-indigo-400/80">
        <span>{label ?? "Queued"}</span>
        <span className="tabular-nums">{pct}%</span>
      </div>
      <div className="h-1 w-full rounded-full bg-indigo-500/10 overflow-hidden">
        <div
          className="h-full bg-indigo-500 transition-all duration-500 ease-out"
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  );
}
