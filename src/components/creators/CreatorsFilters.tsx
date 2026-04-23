"use client"

import { StatusTabBar } from "@/components/creators/StatusTabBar"
import { TrackingTabBar } from "@/components/accounts/TrackingTabBar"
import { useRouter, usePathname, useSearchParams } from "next/navigation"
import { useCallback } from "react"
import type { Enums } from "@/types/db"

export type CreatorStatusCounts = Record<
  Enums<"onboarding_status"> | "all",
  number
>
export type CreatorTrackingCounts = Record<
  Enums<"tracking_type"> | "all",
  number
>

export function CreatorsFilters({
  counts,
  trackingCounts,
  activeStatus,
  activeTracking,
}: {
  counts: CreatorStatusCounts
  trackingCounts: CreatorTrackingCounts
  activeStatus: string
  activeTracking: string
}) {
  const router = useRouter()
  const pathname = usePathname()
  const searchParams = useSearchParams()

  const createQueryString = useCallback(
    (name: string, value: string) => {
      const params = new URLSearchParams(searchParams.toString())
      if (value === "all") {
        params.delete(name)
      } else {
        params.set(name, value)
      }
      return params.toString()
    },
    [searchParams]
  )

  const handleStatusChange = (status: string) => {
    router.push(pathname + "?" + createQueryString("status", status))
  }

  const handleTrackingChange = (tracking: string) => {
    router.push(pathname + "?" + createQueryString("tracking", tracking))
  }

  return (
    <div className="flex flex-col gap-3">
      <StatusTabBar
        counts={counts}
        activeStatus={activeStatus}
        onStatusChange={handleStatusChange}
      />
      <TrackingTabBar
        onTabChange={handleTrackingChange}
        activeTab={activeTracking}
        counts={trackingCounts}
      />
    </div>
  )
}
