// src/lib/db/result.ts
// Discriminated-union Result type used by every server action.

export type Result<T> =
  | { ok: true; data: T }
  | { ok: false; error: string; code?: string }

export function ok<T>(data: T): Result<T> {
  return { ok: true, data }
}

export function err<T = never>(error: string, code?: string): Result<T> {
  return { ok: false, error, code }
}

// Convenience: wrap a Supabase query response (`{data, error}`) into a Result.
export function fromSupabase<T>(
  resp: { data: T | null; error: { message: string; code?: string } | null }
): Result<T> {
  if (resp.error) return err(resp.error.message, resp.error.code)
  if (resp.data === null) return err('No data returned')
  return ok(resp.data)
}
