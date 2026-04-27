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
import type { ContentFilters } from "@/lib/content-filtering"
import { Search, X } from "lucide-react"

export function ContentFiltersBar({
  filters,
  fixedPlatform,
  outliersOnly,
}: {
  filters: ContentFilters
  fixedPlatform?: "instagram" | "tiktok"
  outliersOnly?: boolean
}) {
  const router = useRouter()
  const pathname = usePathname()
  const searchParams = useSearchParams()
  const [q, setQ] = useState(filters.q)
  const [, startTransition] = useTransition()

  const updateParam = (key: string, value: string | null, defaultValue?: string) => {
    const next = new URLSearchParams(searchParams.toString())
    if (!value || value === defaultValue) next.delete(key)
    else next.set(key, value)
    startTransition(() => router.push(`${pathname}?${next.toString()}`))
  }

  useEffect(() => {
    const t = setTimeout(() => {
      updateParam("q", q.trim() || null)
    }, 250)
    return () => clearTimeout(t)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [q])

  const setParam = (key: string, value: string | null, defaultValue?: string) => {
    const next = new URLSearchParams(searchParams.toString())
    if (!value || value === defaultValue) next.delete(key)
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
          placeholder="Search posts, profiles, audio..."
          value={q}
          onChange={(event) => setQ(event.target.value)}
          className="h-9 rounded-lg border-border/50 bg-background/60 pl-9"
        />
      </div>

      <div className="flex flex-wrap items-center gap-2">
        {!fixedPlatform && (
          <Select value={filters.platform} onValueChange={(value) => setParam("platform", value, "all")}>
            <SelectTrigger className="h-9 w-[130px] rounded-lg border-border/50 bg-background/60">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All platforms</SelectItem>
              <SelectItem value="instagram">Instagram</SelectItem>
              <SelectItem value="tiktok">TikTok</SelectItem>
            </SelectContent>
          </Select>
        )}

        <Select
          value={outliersOnly ? (filters.scope === "all" ? "outliers" : filters.scope) : filters.scope}
          onValueChange={(value) => setParam("scope", value, outliersOnly ? "outliers" : "all")}
        >
          <SelectTrigger className="h-9 w-[145px] rounded-lg border-border/50 bg-background/60">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {!outliersOnly && <SelectItem value="all">All content</SelectItem>}
            <SelectItem value="outliers">Outliers</SelectItem>
            <SelectItem value="audio">Has audio</SelectItem>
            <SelectItem value="trended">Repeat audio</SelectItem>
            <SelectItem value="untrended">No trend</SelectItem>
            <SelectItem value="review">Needs review</SelectItem>
          </SelectContent>
        </Select>

        {outliersOnly && (
          <Select
            value={filters.minMultiplier ? String(filters.minMultiplier) : "all"}
            onValueChange={(value) => setParam("min", value, "all")}
          >
            <SelectTrigger className="h-9 w-[120px] rounded-lg border-border/50 bg-background/60">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">Any lift</SelectItem>
              <SelectItem value="3">3x+</SelectItem>
              <SelectItem value="5">5x+</SelectItem>
              <SelectItem value="10">10x+</SelectItem>
            </SelectContent>
          </Select>
        )}

        <Select value={filters.sort} onValueChange={(value) => setParam("sort", value, "recent")}>
          <SelectTrigger className="h-9 w-[145px] rounded-lg border-border/50 bg-background/60">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="recent">Recent</SelectItem>
            <SelectItem value="views">Views</SelectItem>
            <SelectItem value="engagement">Engagement</SelectItem>
            <SelectItem value="outlier">Outlier lift</SelectItem>
            <SelectItem value="trend_usage">Trend usage</SelectItem>
            <SelectItem value="profile">Profile</SelectItem>
          </SelectContent>
        </Select>

        <Button variant="ghost" size="sm" className="h-9 px-2" onClick={clearFilters} aria-label="Clear filters">
          <X className="h-4 w-4" />
        </Button>
      </div>
    </div>
  )
}
