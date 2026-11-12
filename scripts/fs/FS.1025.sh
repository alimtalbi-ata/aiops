#!/usr/bin/env bash
set -Eeuo pipefail
echo '===== FS.1025 | CLEAN GIT SOURCE TWIN BUILD + OFFLINE CONTRACT ====='
REPO=/home/aiops/aiops2-v2-delivery
BRANCH=fix/fs-1009-twin-decimal-metrics
IMAGE=aiops2-twin:fs1025-clean-source-candidate-20261106
SOURCE_SHA=2cedd1ae5802c82f8d09f7fd7dd78280b3591c48929de4cc16a504487fe59edb
TWIN=aiops2-rebuild-twin
CORE=aiops2-rebuild-core
test -d "$REPO/.git"
command -v docker >/dev/null
test "$(docker inspect -f '{{.State.Running}}' "$TWIN")" = true
test "$(docker inspect -f '{{.State.Running}}' "$CORE")" = true
TWIN_BEFORE="$(docker inspect -f '{{.Id}}|{{.Image}}|{{.State.StartedAt}}' "$TWIN")"
CORE_BEFORE="$(docker inspect -f '{{.Id}}|{{.Image}}|{{.State.StartedAt}}' "$CORE")"
TMP="$(mktemp -d /tmp/fs1025.XXXXXXXX)"
chmod 700 "$TMP"
cleanup(){ git -C "$REPO" worktree remove --force "$TMP/source" >/dev/null 2>&1 || true; rm -rf "$TMP"; }
trap cleanup EXIT
echo '===== FETCH + DETACHED CLEAN WORKTREE ====='
git -C "$REPO" fetch origin "$BRANCH"
git -C "$REPO" worktree add --detach "$TMP/source" "origin/$BRANCH" >/dev/null
COMMIT="$(git -C "$TMP/source" rev-parse HEAD)"
echo "SOURCE_COMMIT=$COMMIT"
test "$(sha256sum "$TMP/source/app/twin/fs_observations.py" | awk '{print $1}')" = "$SOURCE_SHA" || { echo 'NO_GO=SOURCE_SHA_MISMATCH'; exit 1; }
python3 - "$TMP/source/app/twin/main.py" <<'PY'
import ast,sys
s=open(sys.argv[1]).read();ast.parse(s)
assert 'app.include_router(fs_observations_router)' in s
print('ROUTER_REGISTRATION=PASS')
PY
echo '===== BUILD ONLY FROM GIT CHECKOUT ====='
docker build --pull=false -f "$TMP/source/app/twin/Dockerfile" -t "$IMAGE" "$TMP/source/app"
echo '===== PURE OFFLINE TESTS IN ISOLATED IMAGE ====='
docker run --rm -i --network none --read-only --tmpfs /tmp:rw,noexec,nosuid,size=16m --cap-drop ALL --security-opt no-new-privileges --pids-limit 128 --memory 512m -e AIOPS_ADMIN_TOKEN=fs1025-isolated-test-token --entrypoint python "$IMAGE" -B - <<'PY'
from decimal import Decimal
from twin.fs_observations import _validated_fs_percent
from twin.main import app
routes={getattr(r,'path','') for r in app.routes}
for path in ('/metrics','/api/twin/fs-lab/metrics','/api/twin/observations'):
 assert path in routes,path
print('TWIN_ROUTE_REGISTRATION=PASS')
accepted=[(Decimal('92'),92.),(Decimal('0'),0.),(Decimal('100'),100.),(0,0.),(100,100.),(92.5,92.5)]
for value,expected in accepted:
 assert _validated_fs_percent(value)==expected,(value,expected)
for value in (True,False,Decimal('NaN'),Decimal('Infinity'),Decimal('-Infinity'),float('nan'),float('inf'),float('-inf'),Decimal('-0.01'),Decimal('100.01'),-1,101,'92',None):
 try:_validated_fs_percent(value)
 except (ValueError,TypeError,OverflowError):pass
 else:raise AssertionError('unexpectedly accepted '+repr(value))
print('DECIMAL_CONTRACT=PASS')
print('CONTRACT_CASES=20')
PY
echo '===== SOURCE SHA INSIDE CLEAN IMAGE ====='
test "$(docker run --rm --network none --entrypoint sha256sum "$IMAGE" /app/twin/fs_observations.py | awk '{print $1}')" = "$SOURCE_SHA"
echo 'IMAGE_SOURCE_SHA256=PASS'
test "$(docker inspect -f '{{.Id}}|{{.Image}}|{{.State.StartedAt}}' "$TWIN")" = "$TWIN_BEFORE"
test "$(docker inspect -f '{{.Id}}|{{.Image}}|{{.State.StartedAt}}' "$CORE")" = "$CORE_BEFORE"
echo "CANDIDATE_IMAGE=$IMAGE"
docker image inspect --format 'CANDIDATE_IMAGE_ID={{.Id}}' "$IMAGE"
echo 'PRODUCTION_RESTARTED=NO'
echo 'PRODUCTION_CONTAINERS_CHANGED=NO'
echo 'DATABASE_WRITES=0'
echo 'HTTP_WRITES=0'
echo 'E2E_DB_METRICS=NOT_TESTED'
echo 'IMAGE_BYTE_EQUIVALENCE_WITH_PRODUCTION=NOT_CLAIMED'
echo 'FS1025_RESULT=PASS'
