#!/usr/bin/env bash
# One-shot V2 install. Does not change other containers.
set -Eeuo pipefail
SRC="${SRC:-/home/aiops/aiops-v28-demo}"
DELIVERY="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV=/home/aiops/aiops-v28-test-venv/bin/python
OLD=aiops2-rebuild-portal
BACKUP="aiops2-portal-rollback-v2-$(date -u +%Y%m%dT%H%M%SZ)-$"
IMAGE=aiops2-portal:demo-studio-v2-20261028
TOKEN_FILE=""
started=0
ORIGINAL_CONTAINER_ID=""
FILES_BACKUP=""
FILES_MODIFIED=0

cleanup() {
  if [[ -n "$TOKEN_FILE" ]]; then rm -f "$TOKEN_FILE"; fi
}

backup_sources() {
  FILES_BACKUP="$(mktemp -d /home/aiops/.aiops-v2-sources.XXXXXX)"
  mkdir -p "$FILES_BACKUP/app/portal" "$FILES_BACKUP/tests"

  for rel in app/portal/main.py app/portal/demo_v2.py tests/test_demo_v2.py; do
    if [[ -e "$SRC/$rel" ]]; then
      cp -p "$SRC/$rel" "$FILES_BACKUP/$rel"
    else
      touch "$FILES_BACKUP/$rel.absent"
    fi
  done
}

restore_sources() {
  local failed=0
  [[ -n "$FILES_BACKUP" && -d "$FILES_BACKUP" ]] || return 1

  for rel in app/portal/main.py app/portal/demo_v2.py tests/test_demo_v2.py; do
    if [[ -f "$FILES_BACKUP/$rel.absent" ]]; then
      rm -f "$SRC/$rel" || failed=1
    elif [[ -f "$FILES_BACKUP/$rel" ]]; then
      cp -p "$FILES_BACKUP/$rel" "$SRC/$rel" || failed=1
    else
      echo "CRITICAL: missing backup for $rel" >&2
      failed=1
    fi
  done

  (( failed == 0 ))
}

rollback() {
  local code=${1:-$?}
  local recovery_failed=0
  trap - ERR INT TERM EXIT

  if (( FILES_MODIFIED )); then
    echo "Restoring previous source files..."
    if ! restore_sources; then
      echo "CRITICAL: source restoration failed" >&2
      recovery_failed=1
    fi
  fi

  if (( started )); then
    echo "Restoring previous Docker portal..."

    local docker_recovered=1

    if docker inspect "$BACKUP" >/dev/null 2>&1; then
      # Never destroy the backup if removing the new container fails.
      if docker inspect "$OLD" >/dev/null 2>&1; then
        current_id=""
        if ! current_id="$(docker inspect "$OLD" --format '{{.Id}}')"; then
          echo "CRITICAL: cannot identify current portal" >&2
          recovery_failed=1
          docker_recovered=0
        elif [[ -z "$ORIGINAL_CONTAINER_ID" || -z "$current_id" ]]; then
          echo "CRITICAL: missing container identity" >&2
          recovery_failed=1
          docker_recovered=0
        elif [[ "$current_id" == "$ORIGINAL_CONTAINER_ID" ]]; then
          echo "CRITICAL: refusing to remove original container" >&2
          recovery_failed=1
          docker_recovered=0
        elif ! docker rm -f "$OLD" >/dev/null 2>&1; then
          echo "CRITICAL: cannot remove failed portal" >&2
          recovery_failed=1
          docker_recovered=0
        fi
      fi

      if (( docker_recovered )); then
        if ! docker rename "$BACKUP" "$OLD"; then
          recovery_failed=1
          docker_recovered=0
        fi
      fi
    fi

    if (( docker_recovered )); then
      if ! docker start "$OLD" >/dev/null 2>&1; then
        recovery_failed=1
        docker_recovered=0
      fi
    fi

    if (( docker_recovered )); then
      local restored_healthy=0
      local state
      local i

      for i in $(seq 1 15); do
        state="$(docker inspect "$OLD" --format '{{.State.Health.Status}}' 2>/dev/null)" || state=""
        if [[ "$state" == healthy ]]; then
          restored_healthy=1
          break
        fi
        sleep 2
      done

      if (( ! restored_healthy )); then
        echo "CRITICAL: restored portal is not healthy" >&2
        recovery_failed=1
      fi
    fi
  fi

  if (( recovery_failed )); then
    echo "CRITICAL: rollback incomplete; deployment blocked" >&2
    mkdir -p /home/aiops/aiops2-auto-deploy
    printf '%s\n' "rollback incomplete; manual intervention required" > /home/aiops/aiops2-auto-deploy/DEPLOYMENT_BLOCKED
  fi

  cleanup
  exit "$code"
}
# One recovery path: all failures are handled by the EXIT trap.
trap 'exit 130' INT
trap 'exit 143' TERM
on_exit() {
  local code=$?
  trap - ERR INT TERM EXIT
  if (( code != 0 )); then
    rollback "$code"
  else
    cleanup
  fi
}
trap on_exit EXIT
test -f "$SRC/app/portal/main.py"
test -x "$VENV"
docker inspect "$OLD" >/dev/null
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
backup_sources
FILES_MODIFIED=1
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
ORIGINAL_CONTAINER_ID="$(docker inspect "$OLD" --format '{{.Id}}')"
[[ -n "$ORIGINAL_CONTAINER_ID" ]]
started=1
docker stop "$OLD"
docker rename "$OLD" "$BACKUP"
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
page="$(curl --fail --silent --show-error --max-time 15 http://10.79.94.202:7777/demo-studio/run/RUN-818D2B05974AE5F8)"
grep -q 'Mission Control V2' <<< "$page"
started=0
FILES_MODIFIED=0
echo "SUCCESS: http://10.79.94.202:7777/demo-studio"
echo "Rollback container retained: $BACKUP"
echo "Local changes remain uncommitted; review before git push."
