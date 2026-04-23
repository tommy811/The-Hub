// src/lib/db/rpc.ts
// Typed RPC wrappers. App code calls these instead of supabase.rpc('name', args).
// Generated DB types provide arg/return shapes via RpcArgs<>/RpcReturns<>.

import { createServiceClient } from '@/lib/supabase/server'
import { fromSupabase, type Result } from '@/lib/db/result'
import type { RpcArgs, RpcReturns } from '@/types/db'

export async function commitDiscoveryResult(
  args: RpcArgs<'commit_discovery_result'>
): Promise<Result<RpcReturns<'commit_discovery_result'>>> {
  const supabase = createServiceClient()
  const resp = await supabase.rpc('commit_discovery_result', args)
  return fromSupabase(resp)
}

export async function markDiscoveryFailed(
  args: RpcArgs<'mark_discovery_failed'>
): Promise<Result<RpcReturns<'mark_discovery_failed'>>> {
  const supabase = createServiceClient()
  const resp = await supabase.rpc('mark_discovery_failed', args)
  return fromSupabase(resp)
}

export async function retryCreatorDiscovery(
  args: RpcArgs<'retry_creator_discovery'>
): Promise<Result<RpcReturns<'retry_creator_discovery'>>> {
  const supabase = createServiceClient()
  const resp = await supabase.rpc('retry_creator_discovery', args)
  return fromSupabase(resp)
}

export async function mergeCreators(
  args: RpcArgs<'merge_creators'>
): Promise<Result<RpcReturns<'merge_creators'>>> {
  const supabase = createServiceClient()
  const resp = await supabase.rpc('merge_creators', args)
  return fromSupabase(resp)
}

// bulkImportCreator is added in Task 15 after the migration lands.
