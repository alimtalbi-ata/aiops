#!/usr/bin/env bash
set -euo pipefail
echo '===== FS.965 | PATCH-FS-001B PREFLIGHT ====='
REPO=/home/aiops/aiops2-v2-delivery
ROOT=/home/aiops/aiops2-patches/fs-portal-v30/build
PATCH=patches/fs/PATCH-FS-001B-worker-core-404.diff
COMMIT=d12020376f7bd9e85d24abf5ef2f3b9dd5a73bab
EXPECTED=d624369f6399f9a3a88521a359f9385eb6cf09ce710e2af402466a274fddbc2d
echo "$EXPECTED  $ROOT/app/worker/main.py" | sha256sum -c -
git -C "$REPO" show "$COMMIT:$PATCH" | git -C "$ROOT" apply --check -
echo 'PATCH_APPLY_CHECK=PASS'
echo 'DEPLOYMENT_EXECUTED=NO'
echo '===== END FS.965 ====='
