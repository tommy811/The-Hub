import { getCurrentWorkspaceId } from "@/lib/workspace"
import { getPlatformAccountsForWorkspace } from "@/lib/db/queries"
import { InstagramAccountsClient } from "./InstagramAccountsClient"
import type { PlatformAccountRow } from "@/lib/db/queries"

export type AccountRowData = PlatformAccountRow

export default async function InstagramAccountsPage({
  searchParams,
}: {
  searchParams: Promise<{ tracking?: string }>
}) {
  const wsId = await getCurrentWorkspaceId()
  const sp = await searchParams
  const activeTracking = sp?.tracking ?? "all"

  const accounts = await getPlatformAccountsForWorkspace(wsId, {
    platform: "instagram",
    accountType: "social",
  })

  return (
    <InstagramAccountsClient
      accounts={accounts}
      activeTracking={activeTracking}
    />
  )
}
