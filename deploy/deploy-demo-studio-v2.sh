#!/usr/bin/env bash
# Existing Debian poll.sh executes this on a new stable SHA; no new cron or stack.
set -Eeuo pipefail
umask 077
delivery="$(cd "$(dirname "$0")/.." && pwd)"
state=/home/aiops/.local/state/aiops-debian-agent
# A previous PASS cannot qualify a later failed or unexecuted job.
rm -f "$state/portal-deploy-result.json" "$state/portal-compose-result.json" "$state/portal-host-contracts.json"
status=0
/bin/bash "$delivery/deploy/debian-portal-deploy.sh" || status=$?
if [ "$status" -eq 0 ]; then
  /usr/bin/python3 "$delivery/deploy/debian-portal-canonicalize.py" || status=$?
fi
# Anonymous, read-only host tests run even if upgrade was blocked; never promote E2E.
/usr/bin/python3 "$delivery/deploy/debian-portal-host-contracts.py" || status=78
/usr/bin/python3 "$delivery/deploy/debian-portal-preflight.py" || status=78
exit "$status"
