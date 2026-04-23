"use client"

import { useEffect } from "react"
import { ErrorState } from "@/components/ui/error-state"

export default function DashboardError({
  error,
  reset,
}: {
  error: Error & { digest?: string }
  reset: () => void
}) {
  useEffect(() => {
    console.error("Dashboard error boundary:", error)
  }, [error])

  return (
    <div className="p-6">
      <ErrorState message={error.message} onRetry={reset} />
    </div>
  )
}
