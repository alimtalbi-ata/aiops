#!/usr/bin/env bash
# Export a schema-only fingerprint from a PostgreSQL container. Never exports table rows.
set -Eeuo pipefail
umask 077

if [[ $# -ne 3 ]]; then
  echo "Usage: $0 <postgres-container> <database> <output.json>" >&2
  exit 64
fi

CONTAINER=$1
DATABASE=$2
OUTPUT=$3

command -v docker >/dev/null || { echo "ERROR: docker is required" >&2; exit 69; }
docker inspect "$CONTAINER" >/dev/null 2>&1 || {
  echo "ERROR: container not found: $CONTAINER" >&2
  exit 69
}
mkdir -p "$(dirname "$OUTPUT")"
TMP=$(mktemp)
trap 'rm -f "$TMP"' EXIT

SQL=$(cat <<'SQL'
WITH relations AS (
  SELECT c.oid, n.nspname AS schema_name, c.relname AS relation_name,
         c.relkind::text AS relation_kind
  FROM pg_class c
  JOIN pg_namespace n ON n.oid = c.relnamespace
  WHERE c.relkind IN ('r','p','v','m','f')
    AND n.nspname NOT IN ('pg_catalog','information_schema')
    AND n.nspname NOT LIKE 'pg_toast%'
    AND n.nspname NOT LIKE 'pg_temp_%'
),
payload AS (
  SELECT r.schema_name, r.relation_name, r.relation_kind,
    COALESCE((
      SELECT jsonb_agg(jsonb_build_object(
        'ordinal', a.attnum,
        'name', a.attname,
        'type', format_type(a.atttypid, a.atttypmod),
        'nullable', NOT a.attnotnull,
        'identity', a.attidentity,
        'generated', a.attgenerated
      ) ORDER BY a.attnum)
      FROM pg_attribute a
      WHERE a.attrelid = r.oid AND a.attnum > 0 AND NOT a.attisdropped
    ), '[]'::jsonb) AS columns,
    COALESCE((
      SELECT jsonb_agg(jsonb_build_object(
        'name', con.conname,
        'type', con.contype,
        'definition', pg_get_constraintdef(con.oid, true),
        'validated', con.convalidated
      ) ORDER BY con.conname)
      FROM pg_constraint con WHERE con.conrelid = r.oid
    ), '[]'::jsonb) AS constraints,
    COALESCE((
      SELECT jsonb_agg(jsonb_build_object(
        'name', idx.relname,
        'unique', i.indisunique,
        'primary', i.indisprimary,
        'valid', i.indisvalid,
        'definition', pg_get_indexdef(i.indexrelid)
      ) ORDER BY idx.relname)
      FROM pg_index i
      JOIN pg_class idx ON idx.oid = i.indexrelid
      WHERE i.indrelid = r.oid
    ), '[]'::jsonb) AS indexes
  FROM relations r
)
SELECT jsonb_pretty(jsonb_build_object(
  'format_version', 1,
  'database', current_database(),
  'server_version', current_setting('server_version'),
  'method', 'catalog-only-no-row-data',
  'relations', COALESCE(jsonb_agg(jsonb_build_object(
    'schema', schema_name,
    'name', relation_name,
    'kind', relation_kind,
    'columns', columns,
    'constraints', constraints,
    'indexes', indexes
  ) ORDER BY schema_name, relation_name), '[]'::jsonb)
))
FROM payload;
SQL
)

# SQL is schema metadata only: no row data, defaults, comments, credentials, or secrets.
printf '%s\n' "$SQL" | docker exec -i "$CONTAINER" sh -c '
  set -eu
  : "${POSTGRES_USER:?POSTGRES_USER is not set in the container}"
  exec psql -X -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$1" -At
' sh "$DATABASE" > "$TMP"

python3 - "$TMP" "$OUTPUT" <<'PY'
import json, os, sys
source, destination = sys.argv[1:]
with open(source, encoding="utf-8") as f:
    payload = json.load(f)
if payload.get("format_version") != 1 or not isinstance(payload.get("relations"), list):
    raise SystemExit("ERROR: schema fingerprint output failed validation")
with open(destination, "w", encoding="utf-8") as f:
    json.dump(payload, f, indent=2, sort_keys=True)
    f.write("\n")
os.chmod(destination, 0o600)
print(f"DATABASE={payload['database']}")
print(f"RELATIONS={len(payload['relations'])}")
print(f"OUTPUT={destination}")
print("ROW_DATA_EXPORTED=NO")
PY
