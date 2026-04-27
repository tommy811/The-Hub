export const dynamic = "force-dynamic"

import { PlatformOutliersPage } from "@/components/content/PlatformOutliersPage"

export default async function TikTokOutliers({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | string[] | undefined>>
}) {
  return <PlatformOutliersPage platform="tiktok" title="TikTok" searchParams={await searchParams} />
}
