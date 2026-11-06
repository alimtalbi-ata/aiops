#!/usr/bin/env bash
set -euo pipefail
echo '===== FS.1006 | TWIN OBSERVATION NUMERIC TYPE FORENSICS ====='
echo 'MODE=READ_ONLY'
docker exec -i aiops2-rebuild-postgres psql -U aiops -d aiops -X -v ON_ERROR_STOP=1 -P pager=off -c "
SELECT
  node_id,
  metric,
  pg_typeof(value) AS postgres_type,
  value::text AS value_text,
  unit,
  status,
  observed_at,
  jsonb_typeof(payload) AS payload_type,
  payload->>'synthetic' AS synthetic,
  payload ? 'source' AS has_source,
  payload ? 'run_id' AS has_run_id
FROM aiops.observations
WHERE node_id = 'CI-FS-LAB-12M'
  AND metric = 'filesystem_used_percent'
ORDER BY observed_at DESC, known_at DESC
LIMIT 5;
" 2>&1 || {
  echo 'OBSERVATION_QUERY=UNAVAILABLE'
}
echo '===== PYTHON ADAPTER TYPE CHECK ====='
docker exec -i aiops2-rebuild-twin python - <<'PY'
from decimal import Decimal
from numbers import Number
import math
samples = [Decimal("87.5"), 87, 87.5, True, float("nan"), float("inf")]
for value in samples:
    print(
        "TYPE=" + type(value).__name__,
        "IS_NUMBER=" + str(isinstance(value, Number)),
        "FINITE=" + str(
            (not isinstance(value, float) or math.isfinite(value))
            and (not isinstance(value, Decimal) or value.is_finite())
        ),
    )
PY
echo '===== SAFETY ====='
echo 'HTTP_WRITES=0'
echo 'DATABASE_WRITES=0'
echo 'PRODUCTION_RESTARTED=NO'
echo '===== END FS.1006 ====='
