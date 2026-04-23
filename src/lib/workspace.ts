// src/lib/workspace.ts
// Single source of truth for the active workspace ID.
// Cached per-request via React.cache() so multiple components in one render share one DB hit.

import { cache } from 'react'
import { createServiceClient } from '@/lib/supabase/server'

export const getCurrentWorkspaceId = cache(async (): Promise<string> => {
  // Phase 1: prefer DEFAULT_WORKSPACE_ID env var; fall back to oldest workspace in DB.
  // Phase 4-ish: replace with workspace_id derived from user session.
  const fromEnv = process.env.DEFAULT_WORKSPACE_ID
  if (fromEnv) return fromEnv

  const supabase = createServiceClient()
  const { data, error } = await supabase
    .from('workspaces')
    .select('id')
    .order('created_at', { ascending: true })
    .limit(1)
    .single()

  if (error) {
    throw new Error(`Failed to load default workspace: ${error.message}`)
  }
  if (!data) {
    throw new Error(
      'No workspace exists. Run `node scripts/init_workspace.js` to seed one, or set DEFAULT_WORKSPACE_ID in .env.local.'
    )
  }
  return data.id
})
