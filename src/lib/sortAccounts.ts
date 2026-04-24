// src/lib/sortAccounts.ts — Deterministic account-sort utility for the rendering layer.
//
// Sort key (in order):
//   1. is_primary desc        — primary account always first
//   2. sortPriority asc       — by platform-class priority (see src/lib/platforms.ts)
//   3. follower_count desc    — bigger reach first; nulls treated as -Infinity (sorted last)
//   4. handle asc             — final tie-break for stability
//
// Returns a NEW array; does not mutate the input. Callers can use this on any list of
// account-like objects (profiles rows, denormalized account DTOs, etc.) — the type
// constraint only requires `platform` (and optionally `is_primary`, `follower_count`,
// `handle`).

import { getSortPriority } from "./platforms";

interface SortableAccount {
  platform: string;
  is_primary?: boolean | null;
  follower_count?: number | null;
  handle?: string | null;
}

export function sortAccounts<T extends SortableAccount>(accounts: T[]): T[] {
  return [...accounts].sort((a, b) => {
    // 1. Primary first
    const aPrimary = a.is_primary ? 1 : 0;
    const bPrimary = b.is_primary ? 1 : 0;
    if (aPrimary !== bPrimary) return bPrimary - aPrimary;

    // 2. sortPriority asc
    const aPrio = getSortPriority(a.platform);
    const bPrio = getSortPriority(b.platform);
    if (aPrio !== bPrio) return aPrio - bPrio;

    // 3. follower_count desc (nulls last)
    const aFollowers = a.follower_count ?? -Infinity;
    const bFollowers = b.follower_count ?? -Infinity;
    if (aFollowers !== bFollowers) return bFollowers - aFollowers;

    // 4. handle asc (final tie-breaker)
    const aHandle = a.handle ?? "";
    const bHandle = b.handle ?? "";
    return aHandle.localeCompare(bHandle);
  });
}
