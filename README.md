# The Hub — Creator Intelligence Platform

Internal tool for a creator management agency. Not a SaaS. The Creator is the source of truth — every module orbits the creator entity and the relational graph of everything they own and do online.

## Tech Stack

- **Frontend:** Next.js 14 (App Router), TypeScript strict, Tailwind, shadcn/ui, Recharts, framer-motion
- **Backend:** Supabase (Postgres 17, Auth, RLS, Realtime, Storage, Edge Functions)
- **Pipeline:** Python 3.11+, `supabase-py`, `apify-client`, `google-generativeai`, `anthropic`, `pydantic v2`
- **Supabase project:** Content OS (`dbkddgwitqwzltuoxmfi`, us-east-1)

## Local Development

**Prerequisites:** Node.js 18+, Python 3.11+

```bash
npm install
npm run dev
```

Copy `.env.local.example` to `.env.local` and fill in:
```
NEXT_PUBLIC_SUPABASE_URL=
NEXT_PUBLIC_SUPABASE_ANON_KEY=
```

For the Python pipeline, copy `scripts/.env.example` to `scripts/.env` and fill in:
```
SUPABASE_URL=
SUPABASE_SERVICE_ROLE_KEY=
GEMINI_API_KEY=
ANTHROPIC_API_KEY=
APIFY_TOKEN=
```

## Project Structure

```
src/
  app/(dashboard)/     Next.js App Router pages
  components/          Shared UI components
  lib/                 Supabase client, utilities
scripts/
  discover_creator.py  Gemini discovery pipeline
  worker.py            Background worker (polls discovery_runs)
  apify_scraper.py     Apify content ingestion
  common.py            Shared DB + API client helpers
supabase/
  migrations/          SQL migration files
  functions/           Edge Functions
```

## Architecture Reference

See `PROJECT_STATE.md` for the full technical reference: schema, enums, RPCs, routes, LLM routing, and build order.

For the complete product vision: `01-Product/Full Product Vision.md` in the Obsidian vault.
