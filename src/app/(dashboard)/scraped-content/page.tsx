export const dynamic = "force-dynamic"

import { ScrapedContentLibraryPage } from "@/components/content/ScrapedContentLibraryPage"

export default async function ScrapedContentPage({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | string[] | undefined>>
}) {
  return <ScrapedContentLibraryPage searchParams={await searchParams} />
}
