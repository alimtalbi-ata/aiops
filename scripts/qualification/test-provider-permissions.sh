#!/usr/bin/env bash
# Regresses the 2026-10-20 non-root source-permission outage.
# Never joins any AIOps Compose project/network.
set -euo pipefail
umask 077

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
TMP="$(mktemp -d)"
IMAGE="aiops2-test-provider-permissions:local-check"
CID=""
cleanup() {
  if [[ -n "$CID" ]]; then docker rm -f "$CID" >/dev/null 2>&1 || true; fi
  rm -rf "$TMP"
}
trap cleanup EXIT

mkdir -p "$TMP/test_provider"
cp "$ROOT/app/test_provider/Dockerfile" "$TMP/test_provider/Dockerfile"
cp "$ROOT/app/test_provider/main.py" "$TMP/test_provider/main.py"
chmod 600 "$TMP/test_provider/main.py"
chmod 700 "$TMP/test_provider"

docker build --quiet -f "$TMP/test_provider/Dockerfile" -t "$IMAGE" "$TMP" >/dev/null
CID="$(docker run -d --network none --read-only --cap-drop ALL --security-opt no-new-privileges "$IMAGE")"
docker exec "$CID" python - <<'PY'
import json
import time
import urllib.request
for retry in range(25):
    try:
        with urllib.request.urlopen("http://127.0.0.1:818/health", timeout=1) as r:
            obj = json.load(r)
            assert r.status == 200 and obj["status"] == "ok"
            assert obj["synthetic_only"] is True
            print("TEST_PROVIDER_NONROOT_UMASK077=PASS")
            break
    except Exception:
        if retry == 24:
            raise
        time.sleep(.2)
PY
