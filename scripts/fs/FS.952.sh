#!/usr/bin/env bash
set -euo pipefail
# FS-001A operator-controlled deployment
# Review the patch and maintenance conditions before execution.
REPO=/home/aiops/aiops2-v2-delivery
ROOT=/home/aiops/aiops2-patches/fs-portal-v30/build
PATCH=patches/fs/PATCH-FS-001A-worker-execution-guard.diff
COMMIT=21fe30e5a3483ee431d234476ed5f7483688e8ef
EXPECTED=02e97de5621efb80bfeb279740d8fc3ab85d6b08a2977bb74b8250fcbd8f5b97
TARGET="$ROOT/app/worker/main.py"
[[ "${DEPLOY_FS_001A:-NO}" == YES ]] || { echo 'Set DEPLOY_FS_001A=YES to authorize'; exit 2; }
echo "$EXPECTED  $TARGET" | sha256sum -c -
git -C "$REPO" show "$COMMIT:$PATCH" | git -C "$ROOT" apply --check -
echo 'Preflight passed; deployment not executed by this script.'
