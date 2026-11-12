#!/usr/bin/env bash
set -euo pipefail
echo '===== FS.1007 | TWIN OBSERVATION FILTER / DATA DISCOVERY ====='
echo 'MODE=READ_ONLY'
echo '===== ACTIVE MODULE FILTER CONSTANTS ====='
docker exec aiops2-rebuild-twin sh -lc "grep -nE '^(NODE_ID|METRIC|THRESHOLD)[[:space:]]*=' /app/twin/fs_observations.py || true"
echo '===== OBSERVATION INVENTORY (LATEST ROWS; NO PAYLOAD CONTENT) ====='
docker exec -i aiops2-rebuild-postgres psql -U aiops -d aiops -X -v ON_ERROR_STOP=1 -P pager=off <<'SQL'
BEGIN READ ONLY;
SELECT
  node_id,
  metric,
  unit,
  status,
  pg_typeof(value)::text AS value_type,
  value::text AS value,
  observed_at,
  payload->>'synthetic' AS synthetic,
  count(*) OVER (PARTITION BY node_id, metric) AS rows_for_pair
FROM aiops.observations
ORDER BY observed_at DESC NULLS LAST, known_at DESC
LIMIT 30;
SELECT
  count(*) AS total_observations,
  count(*) FILTER (WHERE payload->>'synthetic' = 'false') AS explicitly_real,
  count(*) FILTER (WHERE payload->>'synthetic' = 'true') AS explicitly_synthetic,
  count(*) FILTER (WHERE observed_at IS NULL) AS missing_timestamp
FROM aiops.observations;
ROLLBACK;
SQL
echo '===== SAFETY ====='
echo 'HTTP_WRITES=0'
echo 'DATABASE_WRITES=0'
echo 'PRODUCTION_RESTARTED=NO'
echo '===== END FS.1007 ====='
