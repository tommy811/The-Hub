// src/components/ui/error-state.tsx
"use client"

import { AlertCircle, RotateCw } from "lucide-react"
import { Button } from "@/components/ui/button"

export function ErrorState({
  title = "Something went wrong",
  message,
  onRetry,
}: {
  title?: string
  message?: string
  onRetry?: () => void
}) {
  return (
    <div className="flex flex-col items-center justify-center p-12 text-center border border-red-900/30 rounded-xl bg-red-950/10">
      <AlertCircle className="h-12 w-12 text-red-500/70 mb-3" />
      <h3 className="text-base font-semibold text-red-400">{title}</h3>
      {message && (
        <p className="text-sm text-muted-foreground mt-1.5 max-w-md font-mono">
          {message}
        </p>
      )}
      {onRetry && (
        <Button variant="outline" size="sm" onClick={onRetry} className="mt-4">
          <RotateCw className="h-3.5 w-3.5 mr-1.5" />
          Try again
        </Button>
      )}
    </div>
  )
}
