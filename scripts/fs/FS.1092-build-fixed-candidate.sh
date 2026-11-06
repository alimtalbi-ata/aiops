#!/usr/bin/env bash
set -euo pipefail
ROOT="$(git -C "$(dirname "$0")" rev-parse --show-toplevel)"
IMAGE=aiops2-portal:fs1092-history-fixed-candidate
echo "FS1092_MODE=NONPRODUCTION_BUILD_AND_IMPORT"
docker image inspect aiops2-portal:fs1073-csp-candidate >/dev/null
docker build -f "$ROOT/scripts/fs/Dockerfile.fs1092" -t "$IMAGE" "$ROOT"
docker run --rm --entrypoint python "$IMAGE" -c 'import sys;sys.path.insert(0,"/app");from portal.main import app;from portal.fs1051_visual import router as old;assert len(old.routes)==3,len(old.routes);paths=[r.path for r in app.routes];assert paths.count("/api/fs1089/prometheus/history")==1;assert paths.count("/explorer/visual")==1;print("FS1092_APP_IMPORT=PASS");print("FS1092_FS1051_ROUTES=3");print("FS1092_HISTORY_ROUTE=PASS")'
echo "FS1092_IMAGE=$IMAGE"
echo "FS1092_PRODUCTION_DEPLOY=NOT_PERFORMED"
echo "FS1092_RESULT=PASS"
