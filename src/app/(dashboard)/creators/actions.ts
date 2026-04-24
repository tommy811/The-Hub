// src/app/(dashboard)/creators/actions.ts
// Server actions for the Creators surface. Returns Result<T> on every action.

"use server"

import { revalidatePath } from "next/cache"
import { createServiceClient } from "@/lib/supabase/server"
import { getCurrentUserId } from "@/lib/auth"
import { getCurrentWorkspaceId } from "@/lib/workspace"
import {
  bulkImportCreator,
  retryCreatorDiscovery as rpcRetryCreatorDiscovery,
  mergeCreators,
} from "@/lib/db/rpc"
import { ok, err, type Result } from "@/lib/db/result"
import { parseHandles } from "@/lib/handleParser"
import type { Enums } from "@/types/db"

// ---------- bulkImportCreators ----------

export type BulkImportSummary = {
  imported: number
  skipped: number
  errors: Array<{ handle: string; error: string }>
}

export async function bulkImportCreators(
  rawText: string,
  trackingType: Enums<"tracking_type">,
  tagsCsv: string,
  assignedPlatforms: Record<string, string> = {}
): Promise<Result<BulkImportSummary>> {
  try {
    const userId = getCurrentUserId()
    const wsId = await getCurrentWorkspaceId()

    const parsed = parseHandles(rawText)
    const tags = tagsCsv
      ? tagsCsv.split(",").map((t) => t.trim()).filter(Boolean)
      : []

    const errors: BulkImportSummary["errors"] = []
    let imported = 0
    let skipped = 0

    for (let i = 0; i < parsed.length; i++) {
      const ph = parsed[i]
      if (ph.isDuplicate) {
        skipped++
        continue
      }
      const finalPlatform = assignedPlatforms[String(i)] || ph.platform
      if (!finalPlatform || finalPlatform === "unknown") {
        errors.push({ handle: ph.handle ?? "(unknown)", error: "Missing platform" })
        continue
      }
      if (!ph.handle) {
        errors.push({ handle: "(unknown)", error: "Empty handle" })
        continue
      }

      const res = await bulkImportCreator({
        p_handle: ph.handle,
        p_platform_hint: finalPlatform as Enums<"platform">,
        p_tracking_type: trackingType,
        p_tags: tags,
        p_user_id: userId,
        p_workspace_id: wsId,
      })
      if (!res.ok) {
        errors.push({ handle: ph.handle, error: res.error })
        continue
      }
      imported++
    }

    revalidatePath("/creators")
    return ok({ imported, skipped, errors })
  } catch (e: any) {
    return err(e?.message ?? "Bulk import failed")
  }
}

// ---------- importSingleCreator ----------

export async function importSingleCreator(
  platform: Enums<"platform">,
  handle: string,
  url?: string
): Promise<Result<{ creatorId: string }>> {
  try {
    if (!handle || handle.trim().length === 0) {
      return err("Handle is required")
    }
    const userId = getCurrentUserId()
    const wsId = await getCurrentWorkspaceId()

    const res = await bulkImportCreator({
      p_handle: handle.trim().replace(/^@/, ""),
      p_platform_hint: platform,
      p_tracking_type: "unreviewed",
      p_tags: [],
      p_user_id: userId,
      p_workspace_id: wsId,
    })
    if (!res.ok) return err(res.error)

    // New bulk_import_creator returns jsonb {bulk_import_id, creator_id, run_id}.
    const payload = res.data as { creator_id: string } | null
    if (!payload?.creator_id) return err("bulk_import_creator did not return a creator_id")

    // url is informational at the action layer; discovery will use it.
    revalidatePath("/creators")
    return ok({ creatorId: payload.creator_id })
  } catch (e: any) {
    return err(e?.message ?? "Single import failed")
  }
}

// ---------- retryCreatorDiscovery ----------

export async function retryCreatorDiscovery(
  creatorId: string
): Promise<Result<{ runId: string | null }>> {
  try {
    const userId = getCurrentUserId()
    const res = await rpcRetryCreatorDiscovery({
      p_creator_id: creatorId,
      p_user_id: userId,
    })
    if (!res.ok) return err(res.error)

    // Non-blocking edge function trigger — Python worker polls anyway.
    if (res.data) {
      fetch(
        `${process.env.NEXT_PUBLIC_SUPABASE_URL}/functions/v1/trigger-discovery`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${process.env.SUPABASE_SERVICE_ROLE_KEY}`,
          },
          body: JSON.stringify({ run_id: res.data }),
        }
      ).catch(() => {
        // Fire-and-forget — worker polls fallback path
      })
    }

    revalidatePath("/creators")
    revalidatePath(`/creators/${creatorId}`)
    return ok({ runId: (res.data as string | null) ?? null })
  } catch (e: any) {
    return err(e?.message ?? "Retry failed")
  }
}

// ---------- dismissMergeCandidate ----------

export async function dismissMergeCandidate(
  candidateId: string
): Promise<Result<void>> {
  try {
    const wsId = await getCurrentWorkspaceId()
    const supabase = createServiceClient()
    const { error } = await supabase
      .from("creator_merge_candidates")
      .update({ status: "dismissed" })
      .eq("id", candidateId)
      .eq("workspace_id", wsId)
    if (error) return err(error.message)
    revalidatePath("/creators")
    return ok(undefined)
  } catch (e: any) {
    return err(e?.message ?? "Dismiss failed")
  }
}

// ---------- mergeCandidateCreators ----------

export async function mergeCandidateCreators(
  keepId: string,
  mergeId: string,
  candidateId: string
): Promise<Result<void>> {
  try {
    const userId = getCurrentUserId()
    const res = await mergeCreators({
      p_keep_id: keepId,
      p_merge_id: mergeId,
      p_resolver_id: userId,
      p_candidate_id: candidateId,
    })
    if (!res.ok) return err(res.error)
    revalidatePath("/creators")
    return ok(undefined)
  } catch (e: any) {
    return err(e?.message ?? "Merge failed")
  }
}

// ---------- addAccountToCreator ----------

export async function addAccountToCreator(
  creatorId: string,
  data: {
    platform: Enums<"platform">
    handle: string
    accountType: Enums<"account_type">
    url?: string
    displayName?: string
    runDiscovery?: boolean
  }
): Promise<Result<{ profileId: string; runId: string | null }>> {
  try {
    const userId = getCurrentUserId()
    const wsId = await getCurrentWorkspaceId()
    const supabase = createServiceClient()
    const cleanHandle = data.handle.replace(/^@/, "")
    const { data: row, error } = await supabase
      .from("profiles")
      .insert({
        workspace_id: wsId,
        creator_id: creatorId,
        platform: data.platform,
        handle: cleanHandle,
        account_type: data.accountType,
        url: data.url ?? null,
        display_name: data.displayName ?? null,
        discovery_confidence: 1.0,
        discovery_reason: "manual_add",
        is_primary: false,
        added_by: userId,
      })
      .select("id")
      .single()
    if (error) return err(error.message)

    // Optional: queue a discovery run so the worker fans out from this account.
    let runId: string | null = null
    if (data.runDiscovery !== false) {
      const { data: runRow, error: runErr } = await supabase
        .from("discovery_runs")
        .insert({
          workspace_id: wsId,
          creator_id: creatorId,
          input_handle: cleanHandle,
          input_platform_hint: data.platform,
          status: "pending",
          attempt_number: 1,
          source: "manual_add",
          bulk_import_id: null,
          initiated_by: userId,
          started_at: new Date().toISOString(),
        })
        .select("id")
        .single()
      if (runErr) {
        // Non-fatal: profile is saved; user can retry discovery from the row.
        console.error("[addAccountToCreator] discovery_runs insert failed:", runErr.message)
      } else {
        runId = runRow.id
      }
    }

    revalidatePath(`/creators/${creatorId}`)
    return ok({ profileId: row.id, runId })
  } catch (e: any) {
    return err(e?.message ?? "Add account failed")
  }
}
