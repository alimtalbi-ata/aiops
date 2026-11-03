#!/usr/bin/env bash
# Existing Debian poll.sh executes this on a new stable SHA; no new cron or stack.
set -Eeuo pipefail
umask 077
delivery="$(cd "$(dirname "$0")/.." && pwd)"
state=/home/aiops/.local/state/aiops-debian-agent
# A previous PASS cannot qualify a later failed or unexecuted job.
rm -f "$state/portal-deploy-result.json" "$state/portal-compose-result.json" "$state/portal-host-contracts.json" "$state/acme-sim-e2e.json"
status=0
# An E2E-only stable SHA must not rebuild/recreate the already healthy portal.
# Portal deployment is an explicit, separately pinned release intent.
portal_enabled="$(/usr/bin/python3 - "$delivery/deploy/debian-portal-release.json" <<'PY'
import json,sys
try:
 print('yes' if json.load(open(sys.argv[1]))['enabled'] is True else 'no')
except (OSError,ValueError,KeyError,TypeError):
 print('invalid')
PY
)"
if [ "$portal_enabled" = yes ]; then
  /bin/bash "$delivery/deploy/debian-portal-deploy.sh" || status=$?
  if [ "$status" -eq 0 ]; then
    /usr/bin/python3 "$delivery/deploy/debian-portal-canonicalize.py" || status=$?
    if [ "$status" -eq 0 ]; then
      /usr/bin/python3 "$delivery/deploy/debian-portal-ux-contracts.py" || status=$?
    fi
  fi
elif [ "$portal_enabled" != no ]; then
  status=78
fi
# Anonymous, read-only host tests run even if upgrade was blocked; never promote E2E.
/usr/bin/python3 "$delivery/deploy/debian-portal-host-contracts.py" || status=78
# P0 T1: one-shot anonymous Chromium ON DEBIAN via the existing stable poller.
# This is read-only and non-blocking for Core/ACME; FAIL remains NO_GO in its
# private receipt and in the sanitized preflight report. Never upload PNGs.
if [ "$status" -eq 0 ]; then
  /usr/bin/timeout 180 /usr/bin/python3 "$delivery/deploy/debian-portal-playwright-snapshot.py" \
    --base-url http://127.0.0.1:7777 --assert-host SRV-DEB-05 \
    --output-dir "$state/portal-playwright" || echo "HOST_PLAYWRIGHT_NOT_VERIFIED"
fi
# Optional five-service ACME sandbox in-place upgrade. Default disabled.
acme_enabled="$(/usr/bin/python3 - "$delivery/deploy/debian-acme-sandbox-release.json" <<'PY'
import json,sys
try: print('yes' if json.load(open(sys.argv[1]))['enabled'] is True else 'no')
except (OSError,ValueError,KeyError,TypeError): print('invalid')
PY
)"
if [ "$acme_enabled" = yes ] && [ "$status" -eq 0 ]; then
  /bin/bash "$delivery/deploy/debian-acme-sandbox-upgrade.sh" || status=78
elif [ "$acme_enabled" = invalid ]; then
  status=78
fi
# Synthetic E2E uses only the existing containers and never calls real GLPI.
# Missing sandbox capabilities yield a BLOCKED receipt without any POST.
if [ "$status" -eq 0 ]; then
  /usr/bin/python3 "$delivery/deploy/debian-acme-sim-e2e.py" || status=78
fi
/usr/bin/python3 "$delivery/deploy/debian-portal-preflight.py" || status=78
exit "$status"
