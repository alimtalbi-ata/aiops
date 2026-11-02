#!/usr/bin/env bash
# Poller entrypoint: deploy pinned candidate, then publish independent read-only receipt.
set -Eeuo pipefail
umask 077
delivery="$(cd "$(dirname "$0")/.." && pwd)"
# Clear prior receipt: an early pre-mutation failure must never reuse an earlier PASS.
rm -f /home/aiops/.local/state/aiops-debian-agent/portal-deploy-result.json
status=0
/bin/bash "$delivery/deploy/debian-portal-deploy.sh" || status=$?
/usr/bin/python3 "$delivery/deploy/debian-portal-preflight.py" || status=78
exit "$status"
