import { createServerClient } from '@supabase/ssr'
import { createClient as createSupabaseClient } from '@supabase/supabase-js'
import { cookies } from 'next/headers'
import type { Database } from '@/types/database.types'

// Cookie-based anon client — used only when we need auth session context.
export async function createClient() {
  const cookieStore = await cookies()

  return createServerClient<Database>(
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
          } catch {
            // Called from a Server Component — safe to ignore.
          }
        },
      },
    }
  )
}

// Service-role client for server-side page fetches and mutations — bypasses RLS.
// Safe to use only in Server Components and server actions (never sent to the browser).
// Throws if SUPABASE_SERVICE_ROLE_KEY is not configured — no anon-key fallback.
export function createServiceClient() {
  const url = process.env.NEXT_PUBLIC_SUPABASE_URL
  const key = process.env.SUPABASE_SERVICE_ROLE_KEY

  if (!url) {
    throw new Error('NEXT_PUBLIC_SUPABASE_URL is not configured')
  }
  if (!key) {
    throw new Error(
      'SUPABASE_SERVICE_ROLE_KEY is not configured. The service client must use the service role key to bypass RLS — anon-key fallback would silently return empty results. Set SUPABASE_SERVICE_ROLE_KEY in .env.local.'
    )
  }

  return createSupabaseClient<Database>(url, key, {
    auth: { persistSession: false },
  })
}
