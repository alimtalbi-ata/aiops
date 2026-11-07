#!/usr/bin/env bash
# FS621 — build and qualify a candidate without changing running containers.
set -Eeuo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASE_IMAGE="${BASE_IMAGE:-aiops2-portal:fs563-glpi-ownership-candidate-20261106}"
CANDIDATE_IMAGE="${CANDIDATE_IMAGE:-aiops2-portal:fs621-explorers-candidate}"
docker image inspect "$BASE_IMAGE" >/dev/null
docker build --pull=false --build-arg "BASE_IMAGE=$BASE_IMAGE" \
  -f "$ROOT/Dockerfile" -t "$CANDIDATE_IMAGE" "$ROOT"
echo "=== VERIFY CANDIDATE MODULE ==="
docker run --rm --entrypoint python3 "$CANDIDATE_IMAGE" -m py_compile \
  /app/portal/main.py /app/portal/explorer_api.py
docker run --rm -e AIOPS_INTERNAL_TOKEN=fs621-build-only-not-a-runtime-secret --entrypoint python3 "$CANDIDATE_IMAGE" -c \
  'from portal.main import app; p=[r.path for r in app.routes]; assert "/explorer/{page}" in p; assert "/api/explorer/observability/{service}/{operation}" in p; print("ROUTES_OK",len(p))'
docker run --rm --entrypoint python3 "$CANDIDATE_IMAGE" -c \
  'from portal.explorer_api import _safe_query; from fastapi import HTTPException; assert _safe_query("SELECT 1")=="SELECT 1"; exec("try:\n _safe_query(\x27DELETE FROM t\x27)\n raise AssertionError(\x27unsafe SQL accepted\x27)\nexcept HTTPException:\n pass"); print("READ_ONLY_GUARD_OK")'
echo "CANDIDATE_IMAGE=$CANDIDATE_IMAGE"
echo "DEPLOYMENT=NOT_PERFORMED"
