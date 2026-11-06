#!/usr/bin/env bash
set -euo pipefail
if [[ "${FS1085_EXPLICIT_APPROVAL:-}" != YES ]]; then
 echo "FS1085_NOT_AUTHORIZED"; exit 2
fi
echo "FS1085_MODE=EXPLICITLY_APPROVED_PRODUCTION_ROLLOUT"
exec python3 "$(dirname "$0")/fs1085_native_csp_deploy.py"
