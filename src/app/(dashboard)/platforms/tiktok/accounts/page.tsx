import { getCurrentWorkspaceId } from "@/lib/workspace"
import { getPlatformAccountsForWorkspace } from "@/lib/db/queries"
import { TikTokAccountsClient } from "./TikTokAccountsClient"
import type { PlatformAccountRow } from "@/lib/db/queries"

export type AccountRowData = PlatformAccountRow

export default async function TikTokAccountsPage({
  searchParams,
}: {
  searchParams: { tracking?: string }
}) {
  const wsId = await getCurrentWorkspaceId()
  const activeTracking = searchParams?.tracking ?? "all"

  const accounts = await getPlatformAccountsForWorkspace(wsId, {
    platform: "tiktok",
    accountType: "social",
  })

  return (
    <TikTokAccountsClient
      accounts={accounts}
      activeTracking={activeTracking}
    />
  )
}
