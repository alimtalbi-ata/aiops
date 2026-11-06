#!/usr/bin/env bash
set -euo pipefail
echo '===== FS.1010 | ISOLATED TWIN CANDIDATE METRICS RUNTIME ====='
SOURCE_CONTAINER=aiops2-rebuild-twin
IMAGE=aiops2-twin:fs1009-decimal-metrics-candidate-20261106
EXPECTED_SHA256=2cedd1ae5802c82f8d09f7fd7dd78280b3591c48929de4cc16a504487fe59edb
TMP="$(mktemp -d /tmp/fs1010.XXXXXXXX)"
chmod 700 "$TMP"
trap 'rm -rf "$TMP"' EXIT
echo 'MODE=ISOLATED_CANDIDATE_READ_ONLY'
docker inspect "$SOURCE_CONTAINER" >/dev/null
docker image inspect "$IMAGE" >/dev/null
BEFORE_ID="$(docker inspect --format '{{.Image}}' "$SOURCE_CONTAINER")"
echo '===== CANDIDATE SOURCE INTEGRITY ====='
ACTUAL_SHA="$(docker run --rm --network none --entrypoint sha256sum "$IMAGE" /app/twin/fs_observations.py | awk '{print $1}')"
test "$ACTUAL_SHA" = "$EXPECTED_SHA256" || { echo 'SOURCE_SHA256=FAIL'; exit 1; }
echo 'SOURCE_SHA256=PASS'
echo "PATCHED_SOURCE_SHA256=$ACTUAL_SHA"

echo '===== COPY CONTAINER ENVIRONMENT WITHOUT PRINTING SECRETS ====='
docker inspect --format '{{json .Config.Env}}' "$SOURCE_CONTAINER" | python3 -c '
import json,sys
env=json.load(sys.stdin)
with open(sys.argv[1],"w") as out:
 for item in env:
  if "=" not in item: continue
  key,value=item.split("=",1)
  if not key or any(c in key for c in "\n\r= "):continue
  if "\n" in value or "\r" in value:raise SystemExit("multiline env unsupported")
  out.write(key+"="+value+"\n")
' "$TMP/container.env"
chmod 600 "$TMP/container.env"

echo '===== REAL DB READ AND ROUTE INVOCATION IN EPHEMERAL CANDIDATE ====='
docker run --rm -i \
  --network "container:$SOURCE_CONTAINER" \
  --env-file "$TMP/container.env" \
  --read-only --tmpfs /tmp:rw,noexec,nosuid,size=16m \
  --cap-drop ALL --security-opt no-new-privileges \
  --pids-limit 128 --memory 512m \
  --entrypoint python "$IMAGE" -B - <<'PY'
import asyncio
from decimal import Decimal
from twin.fs_observations import db, NODE_ID, METRIC, THRESHOLD, fs_lab_metrics

print("FILTER_NODE_ID="+str(NODE_ID))
print("FILTER_METRIC="+str(METRIC))
print("THRESHOLD="+str(THRESHOLD))
with db() as conn:
    with conn.cursor() as cur:
        cur.execute("""
            SELECT value, observed_at, payload, unit, status
            FROM aiops.observations
            WHERE node_id = %s AND metric = %s
              AND payload->>'synthetic' = 'false'
            ORDER BY observed_at DESC, known_at DESC
            LIMIT 1
        """, (NODE_ID, METRIC))
        row = cur.fetchone()
assert row is not None, "REAL_OBSERVATION_NOT_FOUND"
value, observed_at, payload, unit, status = row
assert isinstance(value, Decimal), f"unexpected DB value type {type(value).__name__}"
assert value.is_finite() and Decimal(0) <= value <= Decimal(100)
assert observed_at is not None
print("REAL_OBSERVATION_TYPE=Decimal")
print("REAL_OBSERVATION_VALUE="+str(value))
print("REAL_OBSERVATION_TIMESTAMP="+str(observed_at))
print("REAL_OBSERVATION_STATUS="+str(status))

result = fs_lab_metrics()
body = result.body.decode("utf-8") if hasattr(result, "body") else str(result)
media_type = getattr(result, "media_type", None)
assert media_type in ("text/plain", "text/plain; version=0.0.4"), f"invalid media type {media_type!r}"
lines = [line for line in body.splitlines() if line.startswith("aiops_twin_fs_lab_")]
assert lines, "missing FS lab metrics"
for line in lines: print("METRIC_LINE="+line)
used = [line for line in lines if line.startswith("aiops_twin_fs_lab_used_percent")]
assert len(used) == 1, "expected one FS used percent metric"
assert float(used[0].split()[-1]) == float(value), "DB/metric mismatch"
print("METRICS_DIRECT_CALL=PASS")
print("METRICS_MEDIA_TYPE="+media_type)
print("METRICS_DB_VALUE_MATCH=PASS")

# Exercise the real ASGI endpoint if it is registered in the candidate application.
from twin.main import app
routes = [getattr(r, "path", "") for r in app.routes]
if "/metrics" not in routes:
    raise AssertionError("TWIN_MAIN_METRICS_ROUTE_MISSING")
try:
    import httpx
except ImportError as exc:
    raise AssertionError("httpx unavailable for ASGI E2E") from exc
async def probe():
    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transport, base_url="http://candidate.invalid") as client:
        response = await client.get("/metrics")
    print("HTTP_STATUS="+str(response.status_code))
    print("HTTP_CONTENT_TYPE="+str(response.headers.get("content-type","")))
    assert response.status_code == 200, "candidate /metrics HTTP failure"
    assert response.headers.get("content-type","").startswith("text/plain"), "candidate /metrics not text/plain"
    assert "aiops_twin_nodes " in response.text, "base Twin metric missing"
    return response
asyncio.run(probe())
print("CANDIDATE_HTTP_METRICS=PASS")
PY

AFTER_ID="$(docker inspect --format '{{.Image}}' "$SOURCE_CONTAINER")"
test "$BEFORE_ID" = "$AFTER_ID"
echo 'SOURCE_CONTAINER_IMAGE_UNCHANGED=YES'
echo 'PRODUCTION_RESTARTED=NO'
echo 'PRODUCTION_CONTAINERS_REPLACED=NO'
echo 'DATABASE_WRITES_BY_TEST=0'
echo 'HTTP_WRITES_BY_TEST=0'
echo 'PROMETHEUS_TARGET_UP=NOT_VERIFIED'
echo '===== END FS.1010 ====='
echo 'FS1010_RESULT=PASS'
