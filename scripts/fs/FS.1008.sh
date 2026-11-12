#!/usr/bin/env bash
set -euo pipefail
echo '===== FS.1008 | TWIN RUNTIME OBSERVATION TYPE CONFIRMATION ====='
echo 'MODE=READ_ONLY'
echo '===== EXECUTE THE EXACT ACTIVE FILTER ====='
docker exec -i aiops2-rebuild-twin python - <<'PY'
from decimal import Decimal
from twin.fs_observations import db, NODE_ID, METRIC, THRESHOLD
print(f"FILTER_NODE_ID={NODE_ID}")
print(f"FILTER_METRIC={METRIC}")
print(f"THRESHOLD={THRESHOLD}")
with db() as conn:
    with conn.cursor() as cur:
        cur.execute("""
            SELECT value, observed_at, payload, unit, status
            FROM aiops.observations
            WHERE node_id = %s
              AND metric = %s
              AND payload->>'synthetic' = 'false'
            ORDER BY observed_at DESC, known_at DESC
            LIMIT 1
        """, (NODE_ID, METRIC))
        row = cur.fetchone()
if row is None:
    print("EXACT_FILTER_ROW=NONE")
else:
    value, observed_at, payload, unit, status = row
    print(f"VALUE_PYTHON_TYPE={type(value).__name__}")
    print(f"VALUE_IS_DECIMAL={isinstance(value, Decimal)}")
    print(f"VALUE_TEXT={str(value)}")
    print(f"OBSERVED_AT_PRESENT={observed_at is not None}")
    print(f"PAYLOAD_PYTHON_TYPE={type(payload).__name__}")
    print(f"UNIT={unit}")
    print(f"STATUS={status}")
    print(f"VALUE_IN_RANGE={isinstance(value, (int, float, Decimal)) and not isinstance(value, bool) and (value.is_finite() if isinstance(value, Decimal) else __import__('math').isfinite(value)) and 0 <= value <= 100}")
try:
    from twin.fs_observations import fs_lab_metrics
    result = fs_lab_metrics()
    body = result.body.decode("utf-8") if hasattr(result, "body") else str(result)
    print("METRICS_CALL=PASS")
    print("METRICS_CONTENT_TYPE=" + getattr(result, "media_type", "unknown"))
    for line in body.splitlines():
        if line.startswith("aiops_twin_fs_lab_"):
            print("METRIC_LINE=" + line)
except Exception as exc:
    print("METRICS_CALL=FAIL")
    print("METRICS_EXCEPTION=" + type(exc).__name__)
    print("METRICS_DETAIL=" + str(getattr(exc, "detail", "")))
PY
echo '===== PROMETHEUS TARGET SNAPSHOT ====='
docker exec aiops2-rebuild-prometheus wget -qO- http://127.0.0.1:9090/api/v1/targets | python3 -c '
import json,sys
d=json.load(sys.stdin)
for t in d.get("data",{}).get("activeTargets",[]):
 if t.get("labels",{}).get("job") in ("aiops2-twin","aiops2-core"):
  print("JOB="+t["labels"].get("job","")+" HEALTH="+t.get("health","")+" ERROR="+t.get("lastError",""))
'
echo '===== SAFETY ====='
echo 'HTTP_WRITES=0'
echo 'DATABASE_WRITES=0'
echo 'PRODUCTION_RESTARTED=NO'
echo '===== END FS.1008 ====='
