#!/usr/bin/env bash
set -euo pipefail
REPO_ROOT="$(git -C "$(dirname "$0")" rev-parse --show-toplevel)"
IMAGE="aiops2-portal:fs1089-history-candidate"
echo "FS1089_MODE=NONPRODUCTION_BUILD_ONLY"
docker image inspect aiops2-portal:fs1073-csp-candidate >/dev/null
docker build -f "$REPO_ROOT/scripts/fs/Dockerfile.fs1089" -t "$IMAGE" "$REPO_ROOT"
docker run --rm --entrypoint python "$IMAGE" -c 'import sys;sys.path.insert(0,"/app");from portal.fs1051_visual import router;paths=[r.path for r in router.routes];assert paths.count("/api/fs1089/prometheus/history")==1;print("FS1089_ROUTE=PASS")'
echo "FS1089_IMAGE=$IMAGE"
echo "FS1089_PRODUCTION_DEPLOY=NOT_PERFORMED"
echo "FS1089_RESULT=PASS"
