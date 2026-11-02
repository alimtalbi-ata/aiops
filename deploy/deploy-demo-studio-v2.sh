#!/usr/bin/env bash
# One-shot V2 install. Does not change other containers.
set -Eeuo pipefail
# Hard stop until a separately qualified in-place Compose upgrade is approved.
# Historical installer contains docker stop/rename/run and must NEVER replace
# the healthy aiops2-rebuild-portal, even when Compose labels are absent.
echo "BLOCKED: legacy standalone portal replacement disabled; use reviewed Compose in-place upgrade" >&2
exit 78
SRC="${SRC:-/home/aiops/aiops-v28-demo}"
DELIVERY="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV=/home/aiops/aiops-v28-test-venv/bin/python
OLD=aiops2-rebuild-portal
BACKUP=aiops2-portal-rollback-v2-20261028
IMAGE=aiops2-portal:demo-studio-v2-20261028
TOKEN_FILE=""
started=0
cleanup() { if [[ -n "$TOKEN_FILE" ]]; then rm -f "$TOKEN_FILE"; fi; }
rollback() {
  code=$?
  trap - ERR
  if (( started )); then
    echo "Deployment failed: restoring previous portal..."
    docker rm -f "$OLD" >/dev/null 2>&1 || true
    docker rename "$BACKUP" "$OLD"
    docker start "$OLD"
  fi
  cleanup
  exit "$code"
}
trap rollback ERR
trap cleanup EXIT
test -f "$SRC/app/portal/main.py"
test -x "$VENV"
docker inspect "$OLD" >/dev/null
# Safety gate: the live DEV portal is Compose-owned. Do not replace it with
# a standalone docker run container; that would discard its network/env contract.
# A targeted Compose update requires an explicit, separately reviewed procedure.
owner="$(docker inspect "$OLD" --format '{{index .Config.Labels "com.docker.compose.project"}}')"
if [[ -n "$owner" && "$owner" != "<no value>" ]]; then
  echo "BLOCKED: $OLD belongs to Compose project $owner; standalone replacement forbidden" >&2
  exit 78
fi
if docker inspect "$BACKUP" >/dev/null 2>&1; then
  echo "Rollback container already exists; refusing deployment" >&2
  exit 1
fi
if ss -ltn | grep -qE '(^|[[:space:]])[^[:space:]]*:7777[[:space:]]'; then
  # Expected current portal is already bound to 7777.
  current="$(docker inspect "$OLD" --format '{{json .HostConfig.PortBindings}}')"
  [[ "$current" == *'"HostPort":"7777"'* ]] || { echo "7777 occupied by another service"; exit 1; }
fi
echo "Installing V2 module (preserving local portal changes)..."
cp "$DELIVERY/app/portal/demo_v2.py" "$SRC/app/portal/demo_v2.py"
cp "$DELIVERY/tests/test_demo_v2.py" "$SRC/tests/test_demo_v2.py"
"$VENV" - "$SRC/app/portal/main.py" <<'PY'
from pathlib import Path
import sys
p=Path(sys.argv[1])
s=p.read_text()
anchor='    body+=panel("État canonique du run",pretty(detail))'
inject='    from portal.demo_v2 import render_demo_v2\n    body+=render_demo_v2(detail,ledger,gate)\n'
if 'body+=render_demo_v2(detail,ledger,gate)' not in s:
    assert s.count(anchor)==1, "Unexpected portal layout: no modification made"
    s=s.replace(anchor,inject+anchor)
    p.write_text(s)
print("V2 integrated")
PY
echo "Running regression tests..."
(cd "$SRC" && PYTHONPATH=app "$VENV" -m unittest tests.test_v28_portal_ui tests.test_demo_status_reliability tests.test_demo_v2 -q)
echo "Building image..."
docker build -f "$SRC/app/portal/Dockerfile" -t "$IMAGE" "$SRC/app"
TOKEN_FILE="$(mktemp /home/aiops/.aiops-v2-token.XXXXXX)"
chmod 600 "$TOKEN_FILE"
docker inspect "$OLD" --format '{{range .Config.Env}}{{println .}}{{end}}' | grep '^AIOPS_INTERNAL_TOKEN=' > "$TOKEN_FILE"
test -s "$TOKEN_FILE"
echo "Switching only portal (brief interruption)..."
docker stop "$OLD"
docker rename "$OLD" "$BACKUP"
started=1
docker run -d --name "$OLD" --restart unless-stopped \
  --network aiops2-rebuild-control --network-alias aiops2-portal \
  -p 10.79.94.202:7777:777 \
  -e CORE_URL=http://aiops2-core:810 \
  -e TWIN_URL=http://aiops2-twin:811 \
  -e COPILOT_URL=http://aiops2-copilot:814 \
  -e AIOPS_DEMO_LAUNCH_ENABLED=false \
  --env-file "$TOKEN_FILE" \
  --health-cmd="python -c \"import urllib.request; urllib.request.urlopen('http://127.0.0.1:777/health')\"" \
  --health-interval=5s --health-timeout=3s --health-retries=20 \
  "$IMAGE" >/dev/null
docker network connect --alias aiops2-portal aiops2-rebuild-public "$OLD"
healthy=0
for i in $(seq 1 30); do
  state="$(docker inspect "$OLD" --format '{{.State.Health.Status}}')"
  if [[ "$state" == healthy ]]; then healthy=1; break; fi
  sleep 2
done
[[ "$healthy" == 1 ]]
curl --fail --silent --show-error --max-time 15 http://10.79.94.202:7777/demo-studio >/dev/null
curl --fail --silent --show-error --max-time 15 http://10.79.94.202:7777/demo-studio/run/RUN-818D2B05974AE5F8 | grep -q 'Mission Control V2'
started=0
echo "SUCCESS: http://10.79.94.202:7777/demo-studio"
echo "Rollback container retained: $BACKUP"
echo "Local changes remain uncommitted; review before git push."
