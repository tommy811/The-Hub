// src/components/creators/MergeBannerActions.tsx
"use client"

import { useState } from "react"
import { useRouter } from "next/navigation"
import { Button } from "@/components/ui/button"
import { toast } from "sonner"
import {
  dismissMergeCandidate,
  mergeCandidateCreators,
} from "@/app/(dashboard)/creators/actions"

export function MergeBannerActions({
  candidateId,
  keepId,
  mergeId,
  keepLabel,
}: {
  candidateId: string
  keepId: string
  mergeId: string
  keepLabel: string
}) {
  const router = useRouter()
  const [busy, setBusy] = useState<"none" | "dismiss" | "merge">("none")

  const handleDismiss = async () => {
    setBusy("dismiss")
    const r = await dismissMergeCandidate(candidateId)
    setBusy("none")
    if (!r.ok) {
      toast.error("Could not dismiss", { description: r.error })
      return
    }
    toast.success("Marked as different person")
    router.refresh()
  }

  const handleMerge = async () => {
    setBusy("merge")
    const r = await mergeCandidateCreators(keepId, mergeId, candidateId)
    setBusy("none")
    if (!r.ok) {
      toast.error("Merge failed", { description: r.error })
      return
    }
    toast.success(`Merged into ${keepLabel}`)
    router.refresh()
  }

  return (
    <div className="flex gap-2">
      <Button
        size="sm"
        variant="outline"
        disabled={busy !== "none"}
        onClick={handleDismiss}
        className="h-7 text-xs border-amber-500/30 hover:bg-amber-500/20 text-amber-500"
      >
        {busy === "dismiss" ? "Dismissing…" : "Not the same person"}
      </Button>
      <Button
        size="sm"
        disabled={busy !== "none"}
        onClick={handleMerge}
        className="h-7 text-xs bg-amber-500 hover:bg-amber-400 text-amber-950 font-bold"
      >
        {busy === "merge" ? "Merging…" : `Merge: Keep ${keepLabel}`}
      </Button>
    </div>
  )
}
