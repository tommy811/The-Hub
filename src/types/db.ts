// src/types/db.ts
// Typed re-exports from generated database types. App code imports from here, not from database.types.ts directly.

import type { Database } from './database.types'

export type DB = Database

export type Tables<T extends keyof Database['public']['Tables']> =
  Database['public']['Tables'][T]['Row']

export type Inserts<T extends keyof Database['public']['Tables']> =
  Database['public']['Tables'][T]['Insert']

export type Updates<T extends keyof Database['public']['Tables']> =
  Database['public']['Tables'][T]['Update']

export type Enums<T extends keyof Database['public']['Enums']> =
  Database['public']['Enums'][T]

export type RpcArgs<T extends keyof Database['public']['Functions']> =
  Database['public']['Functions'][T]['Args']

export type RpcReturns<T extends keyof Database['public']['Functions']> =
  Database['public']['Functions'][T]['Returns']
