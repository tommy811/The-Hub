// src/lib/auth.ts
// Auth scaffold for Phase 1 — hardcoded SYSTEM_USER_ID env var.
// When real Supabase Auth is implemented (Phase 4-ish), only this file changes.

export function getCurrentUserId(): string {
  const id = process.env.SYSTEM_USER_ID
  if (!id) {
    throw new Error(
      'SYSTEM_USER_ID is not configured. Set it in .env.local to a real auth.users.id UUID. ' +
      'See docs/superpowers/specs/2026-04-23-phase-1-overhaul-design.md §6.1.'
    )
  }
  return id
}
