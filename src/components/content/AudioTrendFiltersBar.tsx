"use client"

import { usePathname, useRouter, useSearchParams } from "next/navigation"
import { useEffect, useState, useTransition } from "react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import type { AudioTrendFilters } from "@/lib/content-filtering"
import { Search, X } from "lucide-react"

export function AudioTrendFiltersBar({ filters }: { filters: AudioTrendFilters }) {
  const router = useRouter()
  const pathname = usePathname()
  const searchParams = useSearchParams()
  const [q, setQ] = useState(filters.q)
  const [, startTransition] = useTransition()

  useEffect(() => {
    const t = setTimeout(() => {
      const next = new URLSearchParams(searchParams.toString())
      if (q.trim()) next.set("q", q.trim())
      else next.delete("q")
      startTransition(() => router.push(`${pathname}?${next.toString()}`))
    }, 250)
    return () => clearTimeout(t)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [q])

  const setParam = (key: string, value: string, defaultValue: string) => {
    const next = new URLSearchParams(searchParams.toString())
    if (value === defaultValue) next.delete(key)
    else next.set(key, value)
    router.push(`${pathname}?${next.toString()}`)
  }

  const clearFilters = () => {
    setQ("")
    router.push(pathname)
  }

  return (
    <div className="flex flex-col gap-3 rounded-lg border border-border/50 bg-card/40 p-3 md:flex-row md:items-center md:justify-between">
      <div className="relative min-w-0 md:w-[280px]">
        <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
        <Input
          placeholder="Search audio, artist, signature..."
          value={q}
          onChange={(event) => setQ(event.target.value)}
          className="h-9 rounded-lg border-border/50 bg-background/60 pl-9"
        />
      </div>

      <div className="flex flex-wrap items-center gap-2">
        <Select value={String(filters.minUsage)} onValueChange={(value) => setParam("minUsage", value ?? "2", "2")}>
          <SelectTrigger className="h-9 w-[135px] rounded-lg border-border/50 bg-background/60">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="2">2+ posts</SelectItem>
            <SelectItem value="3">3+ posts</SelectItem>
            <SelectItem value="5">5+ posts</SelectItem>
            <SelectItem value="10">10+ posts</SelectItem>
          </SelectContent>
        </Select>

        <Select value={String(filters.minCreators)} onValueChange={(value) => setParam("minCreators", value ?? "1", "1")}>
          <SelectTrigger className="h-9 w-[145px] rounded-lg border-border/50 bg-background/60">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="1">Any creators</SelectItem>
            <SelectItem value="2">2+ creators</SelectItem>
            <SelectItem value="3">3+ creators</SelectItem>
            <SelectItem value="5">5+ creators</SelectItem>
          </SelectContent>
        </Select>

        <Select value={filters.sort} onValueChange={(value) => setParam("sort", value ?? "usage", "usage")}>
          <SelectTrigger className="h-9 w-[135px] rounded-lg border-border/50 bg-background/60">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="usage">Usage</SelectItem>
            <SelectItem value="creators">Creators</SelectItem>
            <SelectItem value="name">Name</SelectItem>
            <SelectItem value="recent">Recently linked</SelectItem>
          </SelectContent>
        </Select>

        <Button variant="ghost" size="sm" className="h-9 px-2" onClick={clearFilters} aria-label="Clear filters">
          <X className="h-4 w-4" />
        </Button>
      </div>
    </div>
  )
}
