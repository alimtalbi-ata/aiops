#!/usr/bin/env bash
set -Eeuo pipefail
cd "$(dirname "$0")/.."
python3 -m compileall -q app
bash tests/runtime-contract.sh
grep -q 'OUTBOX_WORKER_ID' app/core/main.py
grep -q 'lease expired' app/core/main.py
grep -q 'for update' app/core/main.py
! find . -type d -name __pycache__ -print -quit | grep -q .
echo REGRESSION_CONTRACT=PASS
