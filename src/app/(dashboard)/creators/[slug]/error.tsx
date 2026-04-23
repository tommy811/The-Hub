"use client"

import { useEffect } from "react"
import { ErrorState } from "@/components/ui/error-state"

export default function CreatorDetailError({
  error,
  reset,
}: {
  error: Error & { digest?: string }
  reset: () => void
}) {
  useEffect(() => {
    console.error("Creator detail error:", error)
  }, [error])

  return (
    <div className="p-6">
      <ErrorState
        title="Couldn't load creator"
        message={error.message}
        onRetry={reset}
      />
    </div>
  )
}
