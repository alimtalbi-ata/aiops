#!/usr/bin/env bash
set -Eeuo pipefail
[[ "${CONFIRM_RETIRE:-NO}" == YES ]] || { echo 'BLOCKED|CONFIRM_RETIRE=YES'; exit 2; }
[[ -f "${QUALIFICATION_MARKER:-/home/aiops/backups/aiops2/QUALIFIED}" ]] || { echo 'BLOCKED|RUNTIME_NOT_QUALIFIED'; exit 3; }
echo 'PASS|RETIREMENT_GATE'
