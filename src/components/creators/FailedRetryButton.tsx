// src/components/creators/FailedRetryButton.tsx
"use client"

import { useState } from "react"
import { useRouter } from "next/navigation"
import { Button } from "@/components/ui/button"
import { toast } from "sonner"
import { retryCreatorDiscovery } from "@/app/(dashboard)/creators/actions"

export function FailedRetryButton({ creatorId }: { creatorId: string }) {
  const router = useRouter()
  const [busy, setBusy] = useState(false)

  const handleClick = async () => {
    setBusy(true)
    const r = await retryCreatorDiscovery(creatorId)
    setBusy(false)
    if (!r.ok) {
      toast.error("Retry failed", { description: r.error })
      return
    }
    toast.success("Discovery re-queued")
    router.refresh()
  }

  return (
    <Button
      size="sm"
      variant="outline"
      disabled={busy}
      onClick={handleClick}
      className="border-red-900/50 hover:bg-red-900/20 text-red-400 shrink-0"
    >
      {busy ? "Retrying…" : "Retry"}
    </Button>
  )
}
