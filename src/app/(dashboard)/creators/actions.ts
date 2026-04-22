// src/app/(dashboard)/creators/actions.ts — Server actions for Creators Hub
"use server"

import { createServerClient } from '@supabase/ssr'
import { cookies } from 'next/headers'
import { ParsedHandle } from '@/lib/handleParser'

function getSupabase() {
  const cookieStore = cookies()
  return createServerClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
    {
      cookies: {
        getAll() {
          return cookieStore.getAll()
        },
        setAll(cookiesToSet) {
          try {
            cookiesToSet.forEach(({ name, value, options }) =>
              cookieStore.set(name, value, options)
            )
          } catch (error) {
            // Context called from a Server Component
          }
        },
      },
    }
  )
}

export async function bulkImportCreators(handles: ParsedHandle[], trackingType: string, tags: string[]) {
  const supabase = getSupabase()
  
  // Logic stub for bulk import
  // 1. Derive slug
  // 2. Insert creator
  // 3. Insert profile
  // 4. Insert discovery run
  // 5. triggerDiscovery(runId)
  
  return { imported: handles.length, skipped: 0, errors: [] }
}

export async function triggerDiscovery(runId: string) {
  // Use service role key to trigger edge function
  try {
    const res = await fetch(`${process.env.NEXT_PUBLIC_SUPABASE_URL}/functions/v1/trigger-discovery`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Authorization": `Bearer ${process.env.SUPABASE_SERVICE_ROLE_KEY}`
      },
      body: JSON.stringify({ run_id: runId })
    });
    return await res.json()
  } catch (error) {
    console.error("Failed to trigger discovery", error)
  }
}

export async function dismissMergeCandidate(candidateId: string) {
  const supabase = getSupabase()
  await supabase.from('creator_merge_candidates').update({ status: 'dismissed' }).eq('id', candidateId)
}

export async function mergeCandidateCreators(keepId: string, mergeId: string, candidateId: string) {
  const supabase = getSupabase()
  // TODO: resolver_id will be null until Supabase Auth session is wired — anon key has no auth.uid()
  await supabase.rpc('merge_creators', {
    p_keep_id: keepId,
    p_merge_id: mergeId,
    p_resolver_id: (await supabase.auth.getUser()).data.user?.id,
    p_candidate_id: candidateId
  })
}

export async function retry_creator_discovery(creatorId: string) {
  const supabase = getSupabase()
  // TODO: p_user_id will be null until Supabase Auth session is wired — anon key has no auth.uid()
  const res = await supabase.rpc('retry_creator_discovery', {
    p_creator_id: creatorId,
    p_user_id: (await supabase.auth.getUser()).data.user?.id
  })
  
  if (res.data) {
     triggerDiscovery(res.data) // non-blocking
  }
}
