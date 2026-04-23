// src/components/shared/ComingSoon.tsx
import { Sparkles } from "lucide-react"

export function ComingSoon({
  phase,
  feature,
  description,
}: {
  phase: 2 | 3 | 4
  feature: string
  description?: string
}) {
  return (
    <div className="flex flex-col items-center justify-center min-h-[60vh] text-center px-6">
      <div className="bg-indigo-500/10 border border-indigo-500/20 rounded-2xl p-2 mb-4">
        <Sparkles className="h-6 w-6 text-indigo-400" />
      </div>
      <h2 className="text-xl font-bold tracking-tight">{feature}</h2>
      <p className="text-sm text-muted-foreground mt-2 max-w-md">
        {description ?? `Coming in Phase ${phase}.`}
      </p>
      <span className="text-[10px] uppercase tracking-widest font-bold text-indigo-400 mt-4 bg-indigo-500/10 px-2 py-1 rounded-md">
        Phase {phase}
      </span>
    </div>
  )
}
