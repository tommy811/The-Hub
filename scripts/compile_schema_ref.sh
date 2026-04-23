#!/usr/bin/env bash
# Generates docs/SCHEMA.md from the live Supabase DB.
# Run manually: bash scripts/compile_schema_ref.sh
# Or via npm:   npm run db:schema
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"
ENV_FILE="$SCRIPT_DIR/.env"
OUT_FILE="$ROOT_DIR/docs/SCHEMA.md"
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT

# ── Load .env ─────────────────────────────────────────────────────────────────
[[ -f "$ENV_FILE" ]] || { echo "ERROR: $ENV_FILE not found" >&2; exit 1; }
set -o allexport
# shellcheck source=/dev/null
source "$ENV_FILE"
set +o allexport

[[ -n "${SUPABASE_DB_URL:-}" ]] || {
  echo "ERROR: SUPABASE_DB_URL is not set in scripts/.env" >&2
  echo "  Get it from: Supabase Dashboard → Project Settings → Database" >&2
  echo "  Use the 'URI' connection string (direct, not pooler) — port 5432." >&2
  echo "  Example: postgresql://postgres:[password]@db.dbkddgwitqwzltuoxmfi.supabase.co:5432/postgres" >&2
  exit 1
}

command -v psql >/dev/null 2>&1 || {
  echo "ERROR: psql not found. Install with: brew install libpq" >&2
  echo "  Then add to PATH: export PATH=\"\$(brew --prefix libpq)/bin:\$PATH\"" >&2
  exit 1
}

mkdir -p "$ROOT_DIR/docs"

PROJ_ID="dbkddgwitqwzltuoxmfi"
ISO_DATE=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
SEP=$'\x01'  # ASCII unit separator — safe delimiter, won't appear in DB metadata

run_psql() {
  psql "$SUPABASE_DB_URL" --no-align --tuples-only -F "$SEP" -X -c "$1"
}

echo "Connecting to DB…"

# ── Query 1: columns + PK flags + FK refs ─────────────────────────────────────
run_psql "
SELECT
  c.table_name,
  c.column_name,
  CASE
    WHEN c.udt_schema = 'public' THEN c.udt_name
    ELSE c.data_type
  END                                                       AS col_type,
  c.is_nullable,
  COALESCE(c.column_default, '')                            AS col_default,
  COALESCE(
    pg_catalog.col_description(pc.oid, c.ordinal_position::int),
    ''
  )                                                         AS col_comment,
  CASE WHEN pk.column_name IS NOT NULL THEN 'PK' ELSE '' END AS is_pk,
  COALESCE(fk_info.fk_ref, '')                              AS fk_ref
FROM information_schema.columns c
JOIN pg_catalog.pg_class pc
  ON pc.relname = c.table_name AND pc.relkind = 'r'
JOIN pg_catalog.pg_namespace pn
  ON pn.oid = pc.relnamespace AND pn.nspname = 'public'
LEFT JOIN (
  SELECT kcu.table_name, kcu.column_name
  FROM information_schema.table_constraints tc
  JOIN information_schema.key_column_usage kcu
    ON  kcu.constraint_name = tc.constraint_name
    AND kcu.table_schema    = tc.table_schema
    AND kcu.table_name      = tc.table_name
  WHERE tc.constraint_type = 'PRIMARY KEY'
    AND tc.table_schema    = 'public'
) pk
  ON pk.table_name = c.table_name AND pk.column_name = c.column_name
LEFT JOIN (
  SELECT
    kcu.table_name,
    kcu.column_name,
    ccu.table_name || '.' || ccu.column_name AS fk_ref
  FROM information_schema.table_constraints tc
  JOIN information_schema.key_column_usage kcu
    ON  kcu.constraint_name = tc.constraint_name
    AND kcu.table_schema    = tc.table_schema
  JOIN information_schema.referential_constraints rc
    ON  rc.constraint_name    = tc.constraint_name
    AND rc.constraint_schema  = tc.table_schema
  JOIN information_schema.constraint_column_usage ccu
    ON  ccu.constraint_name   = rc.unique_constraint_name
    AND ccu.constraint_schema = rc.unique_constraint_schema
  WHERE tc.constraint_type = 'FOREIGN KEY'
    AND tc.table_schema    = 'public'
) fk_info
  ON fk_info.table_name = c.table_name AND fk_info.column_name = c.column_name
WHERE c.table_schema = 'public'
ORDER BY c.table_name, c.ordinal_position
" > "$TMP/cols.tsv"

# ── Query 2: enums ────────────────────────────────────────────────────────────
run_psql "
SELECT t.typname, e.enumlabel
FROM pg_catalog.pg_type t
JOIN pg_catalog.pg_enum e ON e.enumtypid = t.oid
JOIN pg_catalog.pg_namespace n ON n.oid = t.typnamespace AND n.nspname = 'public'
ORDER BY t.typname, e.enumsortorder
" > "$TMP/enums.tsv"

# ── Query 3: RLS policies ─────────────────────────────────────────────────────
run_psql "
SELECT tablename, policyname, cmd
FROM pg_catalog.pg_policies
WHERE schemaname = 'public'
ORDER BY tablename, policyname
" > "$TMP/rls.tsv"

echo "Queries done. Formatting…"

# ── Generate SCHEMA.md ────────────────────────────────────────────────────────
{
  printf '# SCHEMA.md — Generated %s\n' "$ISO_DATE"
  printf '> Source: live DB (%s). Regenerate via `npm run db:schema`.\n\n' "$PROJ_ID"

  # ── Tenant-Scoped Tables ────────────────────────────────────────────────────
  printf '## Tenant-Scoped Tables\n\n'
  awk -F'\x01' '$2 == "workspace_id" { print "- `" $1 "`" }' "$TMP/cols.tsv" | sort -u
  printf '\n'

  # ── Enums ───────────────────────────────────────────────────────────────────
  printf '## Enums\n\n'
  awk -F'\x01' '
    NF < 2 { next }
    {
      name = $1; val = $2
      if (name != cur) {
        if (cur != "") printf "- `%s`: %s\n", cur, line
        cur = name; line = val
      } else {
        line = line " | " val
      }
    }
    END { if (cur != "") printf "- `%s`: %s\n", cur, line }
  ' "$TMP/enums.tsv"
  printf '\n'

  # ── Tables ──────────────────────────────────────────────────────────────────
  printf '## Tables\n\n'

  # Build RLS lookup: one line per table, tab-separated: TABLE\tpol1(CMD), pol2(CMD)
  awk -F'\x01' '
    NF < 3 { next }
    {
      tbl=$1; pol=$2; cmd=$3
      entry = pol "(" cmd ")"
      if (tbl in rls) rls[tbl] = rls[tbl] ", " entry
      else rls[tbl] = entry
    }
    END { for (t in rls) printf "%s\t%s\n", t, rls[t] }
  ' "$TMP/rls.tsv" > "$TMP/rls_map.tsv"

  awk -F'\x01' -v rls_file="$TMP/rls_map.tsv" '
    BEGIN {
      while ((getline line < rls_file) > 0) {
        split(line, a, "\t")
        rls[a[1]] = a[2]
      }
    }
    NF < 4 { next }
    {
      tbl=$1; col=$2; typ=$3; nullable=$4; def=$5; comment=$6; pk=$7; fk=$8

      if (tbl != cur_tbl) {
        if (cur_tbl != "") {
          if (cur_tbl in rls) printf "\n_RLS: %s_\n", rls[cur_tbl]
          printf "\n"
        }
        cur_tbl = tbl
        printf "### %s\n\n", tbl
      }

      # Build markers
      markers = ""
      if (pk != "")                 markers = markers " PK"
      if (nullable == "NO" && pk == "") markers = markers " NN"
      if (fk != "")                 markers = markers " FK→" fk
      if (def != "") {
        d = (length(def) > 45) ? substr(def, 1, 42) "…" : def
        markers = markers " DEF " d
      }

      if (markers != "") printf "- **%s**: %s —%s\n", col, typ, markers
      else                printf "- **%s**: %s\n", col, typ
      if (comment != "")  printf "  ↳ %s\n", comment
    }
    END {
      if (cur_tbl != "") {
        if (cur_tbl in rls) printf "\n_RLS: %s_\n", rls[cur_tbl]
        printf "\n"
      }
    }
  ' "$TMP/cols.tsv"

  # ── Column Disambiguation ───────────────────────────────────────────────────
  printf '## Column Disambiguation\n\n'
  printf '_Column names appearing in 2 or more tables:_\n\n'
  awk -F'\x01' '
    NF < 2 { next }
    {
      col = $2; tbl = $1
      if (!(col in seen_in) || index(seen_in[col], "`" tbl "`") == 0) {
        seen_in[col] = (seen_in[col] != "") ? seen_in[col] ", `" tbl "`" : "`" tbl "`"
        count[col]++
      }
    }
    END {
      for (col in count)
        if (count[col] >= 2)
          printf "- **%s** — %s\n", col, seen_in[col]
    }
  ' "$TMP/cols.tsv" | sort

} > "$OUT_FILE"

TABLE_COUNT=$(awk -F'\x01' '
  NF >= 1 && $1 != cur { cur=$1; n++ }
  END { print n+0 }
' "$TMP/cols.tsv")

echo "✓ Generated $OUT_FILE"
echo "  Tables: $TABLE_COUNT  (expected 18)"
[[ "$TABLE_COUNT" -eq 18 ]] || echo "  WARNING: table count mismatch — expected 18, got $TABLE_COUNT"
