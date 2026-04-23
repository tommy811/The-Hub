// src/components/creators/CreatorsSearchSort.tsx
"use client"

import { useRouter, usePathname, useSearchParams } from "next/navigation"
import { useState, useTransition, useEffect } from "react"
import { Input } from "@/components/ui/input"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { Search } from "lucide-react"

export function CreatorsSearchSort({
  initialQ,
  initialSort,
}: {
  initialQ: string
  initialSort: string
}) {
  const router = useRouter()
  const pathname = usePathname()
  const searchParams = useSearchParams()
  const [q, setQ] = useState(initialQ)
  const [, startTransition] = useTransition()

  // Debounce search input
  useEffect(() => {
    const t = setTimeout(() => {
      const params = new URLSearchParams(searchParams.toString())
      if (q.trim().length === 0) params.delete("q")
      else params.set("q", q.trim())
      startTransition(() => {
        router.push(`${pathname}?${params.toString()}`)
      })
    }, 250)
    return () => clearTimeout(t)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [q])

  const handleSortChange = (sort: string | null) => {
    const params = new URLSearchParams(searchParams.toString())
    if (!sort || sort === "recently_added") params.delete("sort")
    else params.set("sort", sort)
    router.push(`${pathname}?${params.toString()}`)
  }

  return (
    <>
      <div className="relative">
        <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
        <Input
          placeholder="Search creators..."
          value={q}
          onChange={(e) => setQ(e.target.value)}
          className="pl-9 w-[250px] bg-background/50 border-border/50 focus-visible:ring-indigo-500 rounded-lg"
        />
      </div>
      <Select value={initialSort} onValueChange={handleSortChange}>
        <SelectTrigger className="w-[180px] bg-background/50 border-border/50 rounded-lg">
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="recently_added">Recently Added</SelectItem>
          <SelectItem value="name_asc">Name (A-Z)</SelectItem>
          <SelectItem value="platform">Primary Platform</SelectItem>
        </SelectContent>
      </Select>
    </>
  )
}
