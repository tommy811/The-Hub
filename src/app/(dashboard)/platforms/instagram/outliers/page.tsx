export const dynamic = "force-dynamic"

import { PlatformOutliersPage } from "@/components/content/PlatformOutliersPage"

export default async function InstagramOutliers({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | string[] | undefined>>
}) {
  return <PlatformOutliersPage platform="instagram" title="Instagram" searchParams={await searchParams} />
}
